import math
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from src import recommender
from src.main import ADVERSARIAL_PROFILES, EXTENSION_PROFILES, PROFILES
from src.recommender import (
    ARTIST_PENALTY, GENRE_PENALTY, MODES, ScoringMode, Song, UserProfile, Recommender, check_penalty, clean_prefs,
    load_songs, recommend_songs, resolve_mode, score_song,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

def make_small_recommender() -> Recommender:
    songs = [
        Song(
            id=1,
            title="Test Pop Track",
            artist="Test Artist",
            genre="pop",
            mood="happy",
            energy=0.8,
            tempo_bpm=120,
            valence=0.9,
            danceability=0.8,
            acousticness=0.2,
        ),
        Song(
            id=2,
            title="Chill Lofi Loop",
            artist="Test Artist",
            genre="lofi",
            mood="chill",
            energy=0.4,
            tempo_bpm=80,
            valence=0.6,
            danceability=0.5,
            acousticness=0.9,
        ),
    ]
    return Recommender(songs)


def test_recommend_returns_songs_sorted_by_score():
    user = UserProfile(
        favorite_genre="pop",
        favorite_mood="happy",
        target_energy=0.8,
        likes_acoustic=False,
    )
    rec = make_small_recommender()
    results = rec.recommend(user, k=2)

    assert len(results) == 2
    # Starter expectation: the pop, happy, high energy song should score higher
    assert results[0].genre == "pop"
    assert results[0].mood == "happy"


def test_explain_recommendation_returns_non_empty_string():
    user = UserProfile(
        favorite_genre="pop",
        favorite_mood="happy",
        target_energy=0.8,
        likes_acoustic=False,
    )
    rec = make_small_recommender()
    song = rec.songs[0]

    explanation = rec.explain_recommendation(user, song)
    assert isinstance(explanation, str)
    assert explanation.strip() != ""


def make_user() -> UserProfile:
    return UserProfile(
        favorite_genre="pop",
        favorite_mood="happy",
        target_energy=0.8,
        likes_acoustic=False,
    )


def test_recommend_best_song_first_when_input_reversed():
    rec = make_small_recommender()
    reversed_rec = Recommender(list(reversed(rec.songs)))
    results = reversed_rec.recommend(make_user(), k=2)

    assert [s.title for s in results] == ["Test Pop Track", "Chill Lofi Loop"]


def test_recommender_matches_functional_api_on_real_catalog():
    rows = load_songs("data/songs.csv")
    songs = [Song(**row) for row in rows]
    user = UserProfile(
        favorite_genre="lofi",
        favorite_mood="chill",
        target_energy=0.4,
        likes_acoustic=True,
        target_valence=0.6,
    )
    prefs = {"genre": "lofi", "mood": "chill", "energy": 0.4, "valence": 0.6}

    expected = [row["id"] for row, _, _ in recommend_songs(prefs, rows, k=5)]
    actual = [s.id for s in Recommender(songs).recommend(user, k=5)]

    assert actual == expected


def test_explanation_mentions_scoring_details():
    rec = make_small_recommender()
    explanation = rec.explain_recommendation(make_user(), rec.songs[0])

    assert "energy" in explanation
    assert "genre match: pop" in explanation
    assert "mood match: happy" in explanation


def test_recommend_handles_k_zero_and_k_larger_than_catalog():
    rows = load_songs("data/songs.csv")
    rec = Recommender([Song(**row) for row in rows])
    user = make_user()

    assert rec.recommend(user, k=0) == []
    assert len(rec.recommend(user, k=len(rows) + 10)) == len(rows)
    assert Recommender([]).recommend(user, k=3) == []


def test_numbers_given_as_text_are_accepted():
    rows = load_songs("data/songs.csv")
    as_text = {"genre": "pop", "mood": "happy", "energy": "0.8", "valence": "0.8"}
    as_numbers = {"genre": "pop", "mood": "happy", "energy": 0.8, "valence": 0.8}

    assert recommend_songs(as_text, rows, k=5) == recommend_songs(as_numbers, rows, k=5)


def test_labels_ignore_capital_letters_and_extra_spaces():
    rows = load_songs("data/songs.csv")
    messy = {"genre": " Pop", "mood": "HAPPY ", "energy": 0.8}
    clean = {"genre": "pop", "mood": "happy", "energy": 0.8}

    assert recommend_songs(messy, rows, k=5) == recommend_songs(clean, rows, k=5)


def test_out_of_range_targets_are_clamped_and_scores_stay_in_range():
    rows = load_songs("data/songs.csv")
    wild = {"genre": "pop", "mood": "happy", "energy": 1.5, "valence": -1.0}
    clamped = {"genre": "pop", "mood": "happy", "energy": 1.0, "valence": 0.0}

    results = recommend_songs(wild, rows, k=len(rows))

    assert results == recommend_songs(clamped, rows, k=len(rows))
    assert all(0.0 <= score <= 8.0 for _, score, _ in results)


def test_non_numeric_target_raises_a_clear_error():
    rows = load_songs("data/songs.csv")

    with pytest.raises(ValueError, match="energy"):
        recommend_songs({"genre": "pop", "energy": "loud"}, rows)


def test_empty_profile_raises_a_clear_error():
    rows = load_songs("data/songs.csv")

    with pytest.raises(ValueError, match="at least one"):
        recommend_songs({}, rows)


# --- Extension attributes (popularity, decade, mood tags, ...) ---

BASE_PREFS = {"genre": "pop", "mood": "happy", "energy": 0.8, "valence": 0.8}


def song_by_title(title):
    return next(row for row in load_songs("data/songs.csv") if row["title"] == title)


def test_load_songs_returns_extension_fields_with_correct_types():
    rows = load_songs("data/songs.csv")

    assert len(rows) == 20
    for row in rows:
        assert isinstance(row["popularity"], int) and 0 <= row["popularity"] <= 100
        assert isinstance(row["release_decade"], int) and row["release_decade"] % 10 == 0
        assert isinstance(row["mood_tags"], list) and 2 <= len(row["mood_tags"]) <= 3
        assert all(tag == tag.strip().lower() and tag for tag in row["mood_tags"])
        assert isinstance(row["instrumentalness"], float) and 0.0 <= row["instrumentalness"] <= 1.0
        assert isinstance(row["speechiness"], float) and 0.0 <= row["speechiness"] <= 1.0
        assert isinstance(row["language"], str) and row["language"] == row["language"].lower()
    assert song_by_title("Sunrise City")["mood_tags"] == ["uplifting", "bright", "energetic"]


def test_song_dataclass_accepts_every_catalog_row_and_old_style_construction():
    rows = load_songs("data/songs.csv")
    songs = [Song(**row) for row in rows]

    assert [s.mood_tags for s in songs] == [row["mood_tags"] for row in rows]
    old_style = make_small_recommender().songs[0]
    assert old_style.popularity is None and old_style.mood_tags == []
    # the Recommender class still works with the new fields on the dataclass
    assert len(Recommender(songs).recommend(make_user(), k=5)) == 5


def test_profiles_without_new_keys_score_exactly_as_before():
    song = song_by_title("Sunrise City")
    old_style = {k: v for k, v in song.items() if k in (
        "id", "title", "artist", "genre", "mood", "energy", "tempo_bpm",
        "valence", "danceability", "acousticness")}

    assert score_song(BASE_PREFS, song) == score_song(BASE_PREFS, old_style)
    score, reasons = score_song(BASE_PREFS, song)
    assert score == pytest.approx(7.95, abs=0.01)  # energy 3.99 + mood 2 + valence 0.96 + genre 1
    assert len(reasons) == 4


def test_mood_tags_term_scales_with_fraction_of_requested_tags_matched():
    song = song_by_title("Dust Road Home")  # nostalgic, warm, sentimental
    base, _ = score_song(BASE_PREFS, song)

    for tags, expected in ((["nostalgic", "warm", "sentimental"], 1.5),
                           ("Nostalgic| WARM", 1.5),
                           ("nostalgic,gritty", 0.75),
                           (["gritty", "dark"], 0.0)):
        score, reasons = score_song({**BASE_PREFS, "mood_tags": tags}, song)
        assert score - base == pytest.approx(expected)
        assert any(r.startswith("mood tags matched") for r in reasons) == (expected > 0)


def test_decade_term_accepts_int_or_text_and_fades_with_distance():
    song = song_by_title("Dust Road Home")  # 1990
    base, _ = score_song(BASE_PREFS, song)

    for target, expected in ((1990, 1.0), ("1990s", 1.0), (1994, 1.0), ("2000s", 0.8), (2040, 0.0)):
        score, reasons = score_song({**BASE_PREFS, "decade": target}, song)
        assert score - base == pytest.approx(expected)
        assert any(r.startswith("decade 1990s vs target") for r in reasons)
    _, reasons = score_song({**BASE_PREFS, "decade": "2000s"}, song)
    assert "decade 1990s vs target 2000s (+0.80)" in reasons


def test_popularity_term_uses_closeness_and_clamps_the_target():
    song = song_by_title("Paper Boats")  # popularity 22
    base, _ = score_song(BASE_PREFS, song)

    score, reasons = score_song({**BASE_PREFS, "popularity": 22}, song)
    assert score - base == pytest.approx(1.0)
    assert "popularity 22 vs target 22 (+1.00)" in reasons
    score, _ = score_song({**BASE_PREFS, "popularity": 72}, song)
    assert score - base == pytest.approx(0.5)
    assert score_song({**BASE_PREFS, "popularity": 500}, song) == score_song(
        {**BASE_PREFS, "popularity": 100}, song)


def test_instrumentalness_speechiness_and_language_terms():
    song = song_by_title("Concrete Crown")  # speechiness 0.46, instrumentalness 0.0, en
    base, _ = score_song(BASE_PREFS, song)

    score, reasons = score_song({**BASE_PREFS, "speechiness": 0.46}, song)
    assert score - base == pytest.approx(0.5)
    assert "speechiness 0.46 vs target 0.46 (+0.50)" in reasons
    score, reasons = score_song({**BASE_PREFS, "instrumentalness": 1.0}, song)
    assert score - base == pytest.approx(0.0)
    assert "instrumentalness 0.00 vs target 1.00 (+0.00)" in reasons
    score, reasons = score_song({**BASE_PREFS, "language": " EN "}, song)
    assert score - base == pytest.approx(0.5)
    assert "language match: en (+0.50)" in reasons
    score, reasons = score_song({**BASE_PREFS, "language": "es"}, song)
    assert score == base and not any("language" in r for r in reasons)


def test_extension_only_profile_is_accepted_and_ranks_by_the_new_key():
    rows = load_songs("data/songs.csv")
    top = recommend_songs({"popularity": 88}, rows, k=1)[0]

    assert top[0]["title"] == "Gym Hero"
    assert "popularity 88 vs target 88" in top[2]


def test_clean_prefs_normalises_extension_keys_and_is_idempotent():
    cleaned = clean_prefs({"mood_tags": " Warm|Cozy,warm ", "decade": "1990s", "language": " EN ",
                           "popularity": "150", "instrumentalness": -2, "speechiness": "0.3"})

    assert cleaned["mood_tags"] == ["warm", "cozy"]
    assert cleaned["decade"] == 1990 and cleaned["language"] == "en"
    assert cleaned["popularity"] == 100.0 and cleaned["instrumentalness"] == 0.0
    assert cleaned["speechiness"] == 0.3
    assert clean_prefs(cleaned) == cleaned


@pytest.mark.parametrize("prefs, message", [
    ({"popularity": "famous"}, "popularity"),
    ({"instrumentalness": "lots"}, "instrumentalness"),
    ({"speechiness": float("nan")}, "speechiness"),
    ({"decade": "the nineties"}, "decade"),
    ({"decade": 90}, "decade"),
    ({"mood_tags": 5}, "mood_tags"),
])
def test_bad_extension_values_raise_a_clear_error(prefs, message):
    with pytest.raises(ValueError, match=message):
        clean_prefs({"genre": "pop", **prefs})


def test_profile_needs_at_least_one_key_and_blank_extension_keys_do_not_count():
    with pytest.raises(ValueError, match="mood_tags"):
        clean_prefs({})
    with pytest.raises(ValueError, match="at least one"):
        clean_prefs({"mood_tags": "", "language": "  "})
    assert clean_prefs({"language": "es"})["language"] == "es"


def test_song_missing_the_new_fields_still_scores_without_error():
    bare = {"id": 99, "title": "Bare", "artist": "X", "genre": "pop", "mood": "happy",
            "energy": 0.8, "tempo_bpm": 120, "valence": 0.8, "danceability": 0.5, "acousticness": 0.2}
    prefs = {**BASE_PREFS, "mood_tags": "warm", "decade": 1990, "popularity": 50,
             "instrumentalness": 0.5, "speechiness": 0.5, "language": "en"}

    assert score_song(prefs, bare) == score_song(BASE_PREFS, bare)
    assert len(recommend_songs(prefs, [bare], k=1)) == 1
    with_none_fields = {**bare, "popularity": None, "release_decade": None, "mood_tags": [],
                        "instrumentalness": None, "speechiness": None, "language": None}
    assert score_song(prefs, with_none_fields) == score_song(BASE_PREFS, bare)


def test_extension_weights_are_named_constants_and_total_five_points():
    total = (recommender.TAG_WEIGHT + recommender.DECADE_WEIGHT + recommender.POPULARITY_WEIGHT
             + recommender.INSTRUMENTALNESS_WEIGHT + recommender.SPEECHINESS_WEIGHT
             + recommender.LANGUAGE_WEIGHT)
    assert total == pytest.approx(5.0)


def test_instrumentalness_and_speechiness_weights_give_partial_credit():
    song = song_by_title("Focus Flow")  # instrumentalness 0.90, speechiness 0.03
    base, _ = score_song(BASE_PREFS, song)

    score, reasons = score_song({**BASE_PREFS, "instrumentalness": 0.95}, song)
    assert score - base == pytest.approx(0.475)  # 0.5 * (1 - 0.05)
    assert "instrumentalness 0.90 vs target 0.95 (+0.48)" in reasons
    score, reasons = score_song({**BASE_PREFS, "speechiness": 0.10}, song)
    assert score - base == pytest.approx(0.465)  # 0.5 * (1 - 0.07)
    assert any(r.startswith("speechiness 0.03 vs target 0.10") for r in reasons)


def test_load_songs_reads_decade_text_like_a_profile_does(tmp_path):
    header = ("id,title,artist,genre,mood,energy,tempo_bpm,valence,danceability,acousticness,"
              "popularity,release_decade,mood_tags,instrumentalness,speechiness,language\n")
    rows = ["1,A,X,pop,happy,0.5,100,0.5,0.5,0.5,50,1990s,warm,0.1,0.1,en\n",
            "2,B,X,pop,happy,0.5,100,0.5,0.5,0.5,50,1994,warm,0.1,0.1,en\n",
            "3,C,X,pop,happy,0.5,100,0.5,0.5,0.5,50, ,warm,0.1,0.1,en\n"]
    path = tmp_path / "songs.csv"
    path.write_text(header + "".join(rows), encoding="utf-8")

    assert [row["release_decade"] for row in load_songs(str(path))] == [1990, 1990, None]

    path.write_text(header + "4,D,X,pop,happy,0.5,100,0.5,0.5,0.5,50,nineties,warm,0.1,0.1,en\n",
                    encoding="utf-8")
    with pytest.raises(ValueError, match="decade"):
        load_songs(str(path))


def test_blank_extension_values_are_treated_as_absent():
    cleaned = clean_prefs({"genre": "pop", "popularity": "  ", "decade": "", "instrumentalness": " ",
                           "speechiness": "", "mood_tags": "", "language": " "})

    for key in ("popularity", "decade", "instrumentalness", "speechiness", "mood_tags", "language"):
        assert cleaned[key] is None
    rows = load_songs("data/songs.csv")
    assert recommend_songs({"genre": "pop", "popularity": " ", "decade": ""}, rows) == \
        recommend_songs({"genre": "pop"}, rows)
    with pytest.raises(ValueError, match="at least one"):
        clean_prefs({"popularity": "", "decade": " "})


@pytest.mark.parametrize("key", ["popularity", "instrumentalness", "speechiness", "decade"])
def test_booleans_are_rejected_for_extension_numbers(key):
    with pytest.raises(ValueError, match=key):
        clean_prefs({"genre": "pop", key: True})


def test_original_keys_are_cleaned_exactly_as_before():
    assert clean_prefs({"genre": " Pop ", "energy": "0.5", "valence": 2}) == {
        "genre": "pop", "energy": 0.5, "valence": 1.0}
    with pytest.raises(ValueError, match="energy"):
        clean_prefs({"genre": "pop", "energy": ""})


def test_user_profile_extension_fields_default_to_none_and_change_nothing():
    user = make_user()
    for key in ("mood_tags", "decade", "popularity", "instrumentalness", "speechiness", "language"):
        assert getattr(user, key) is None
    assert Recommender._prefs(user) == {"genre": "pop", "mood": "happy", "energy": 0.8}
    assert Recommender._prefs(UserProfile("pop", "happy", 0.8, False, 0.7)) == {
        "genre": "pop", "mood": "happy", "energy": 0.8, "valence": 0.7}


def test_recommender_passes_extension_preferences_through_to_scoring():
    user = UserProfile("country", "nostalgic", 0.55, True, 0.65,
                       mood_tags=["nostalgic", "warm"], decade=1990, popularity=44,
                       instrumentalness=0.0, speechiness=0.04, language="en")
    assert Recommender._prefs(user) == {
        "genre": "country", "mood": "nostalgic", "energy": 0.55, "valence": 0.65,
        "mood_tags": ["nostalgic", "warm"], "decade": 1990, "popularity": 44,
        "instrumentalness": 0.0, "speechiness": 0.04, "language": "en"}  # 0.0 is kept, not dropped

    rows = load_songs("data/songs.csv")
    rec = Recommender([Song(**row) for row in rows])
    expected = [row["id"] for row, _, _ in recommend_songs(Recommender._prefs(user), rows, k=5)]
    assert [s.id for s in rec.recommend(user, k=5)] == expected
    assert rec.recommend(user, k=1)[0].title == "Dust Road Home"
    assert "decade 1990s vs target 1990s" in rec.explain_recommendation(user, rec.songs[12])


def test_recommender_matches_recommend_songs_for_an_extension_profile():
    prefs = EXTENSION_PROFILES["ext-90s-nostalgia"]
    user = UserProfile(prefs["genre"], prefs["mood"], prefs["energy"], prefs["likes_acoustic"],
                       prefs["valence"], mood_tags=prefs["mood_tags"], decade=prefs["decade"])
    rows = load_songs("data/songs.csv")

    expected = [row["id"] for row, _, _ in recommend_songs(prefs, rows, k=5)]
    assert [s.id for s in Recommender([Song(**row) for row in rows]).recommend(user, k=5)] == expected


@pytest.mark.parametrize("name", list(EXTENSION_PROFILES))
def test_every_extension_profile_scores_without_error(name):
    rows = load_songs("data/songs.csv")
    results = recommend_songs(EXTENSION_PROFILES[name], rows, k=5)

    assert len(results) == 5
    assert [score for _, score, _ in results] == sorted((s for _, s, _ in results), reverse=True)
    assert all(0.0 <= score <= 13.0 for _, score, _ in results)


def test_extensions_cli_keyword_prints_every_extension_profile():
    result = subprocess.run([sys.executable, "-m", "src.main", "extensions"],
                            cwd=REPO_ROOT, capture_output=True, text=True)

    assert result.returncode == 0
    assert "Loaded songs: 20" in result.stdout
    for name in EXTENSION_PROFILES:
        assert f"for profile: {name}" in result.stdout


# --- Scoring modes ---

BASE_PROFILES = {**PROFILES, **ADVERSARIAL_PROFILES}
NON_DEFAULT_MODES = [name for name in MODES if name != "balanced"]


def titles(prefs, mode=None, k=5):
    return [song["title"] for song, _, _ in recommend_songs(prefs, load_songs("data/songs.csv"), k, mode)]


@pytest.mark.parametrize("name", list(BASE_PROFILES))
def test_default_mode_equals_no_mode_on_every_base_profile(name):
    rows = load_songs("data/songs.csv")
    plain = recommend_songs(BASE_PROFILES[name], rows, k=20)

    assert recommend_songs(BASE_PROFILES[name], rows, k=20, mode="balanced") == plain
    assert recommend_songs(BASE_PROFILES[name], rows, k=20, mode=MODES["balanced"]) == plain
    for song in rows:
        assert score_song(BASE_PROFILES[name], song, "balanced") == score_song(BASE_PROFILES[name], song)


def test_balanced_mode_uses_the_original_module_constants():
    balanced = MODES["balanced"]

    assert (balanced.energy_weight, balanced.mood_weight, balanced.valence_weight, balanced.genre_weight) == (
        recommender.ENERGY_WEIGHT, recommender.MOOD_WEIGHT, recommender.VALENCE_WEIGHT, recommender.GENRE_WEIGHT)
    assert balanced.energy_sigma == recommender.ENERGY_SIGMA
    assert balanced.partial_mood_credit == recommender.PARTIAL_MOOD_CREDIT


@pytest.mark.parametrize("name", list(MODES))
def test_every_mode_has_all_weights_and_a_stated_maximum(name):
    mode = MODES[name]

    assert mode.name == name and mode.description
    for weight in (mode.energy_weight, mode.mood_weight, mode.valence_weight, mode.genre_weight):
        assert weight >= 0
    assert mode.energy_sigma > 0 and 0 <= mode.partial_mood_credit <= 1
    assert mode.max_score == pytest.approx(MODES["balanced"].max_score)  # every mode keeps the same base scale


@pytest.mark.parametrize("name", list(MODES))
def test_a_perfect_match_scores_the_modes_maximum(name):
    perfect = {"genre": "r&b", "mood": "romantic", "energy": 0.48, "valence": 0.62}
    song = song_by_title("Velvet Hours")

    assert score_song(perfect, song, name)[0] == pytest.approx(MODES[name].max_score)


@pytest.mark.parametrize("name", NON_DEFAULT_MODES)
def test_reasons_show_the_active_modes_weights(name):
    mode = MODES[name]
    song = song_by_title("Sunrise City")  # pop, happy, energy 0.82, valence 0.84
    _, reasons = score_song(PROFILES["pop/happy"], song, name)

    assert f"mood match: happy (+{mode.mood_weight:.2f})" in reasons
    assert f"genre match: pop (+{mode.genre_weight:.2f})" in reasons
    energy_points = mode.energy_weight * recommender.math.exp(-(0.02 ** 2) / (2 * mode.energy_sigma ** 2))
    assert any(r.startswith("energy 0.82 vs target 0.80") and f"(+{energy_points:.2f})" in r for r in reasons)
    valence_points = mode.valence_weight * (1 - 0.04)
    assert any(r.startswith("valence 0.84") and f"(+{valence_points:.2f})" in r for r in reasons)


def test_partial_mood_credit_scales_with_the_modes_mood_weight():
    song = song_by_title("Sunrise City")  # mood happy
    _, reasons = score_song({"mood": "playful"}, song, "mood-first")

    assert "similar mood: happy is close to playful (+2.00)" in reasons  # 4.0 * 0.5


def test_energy_focused_mode_lets_a_loud_song_beat_the_label_match():
    prefs = BASE_PROFILES["adv-conflict-sad"]  # classical + melancholy, but energy 0.95
    assert titles(prefs, "balanced")[0] == "Iron Tide"
    assert titles(prefs, "energy-focused")[:3] == ["Iron Tide", "Storm Runner", "Gym Hero"]
    # genre-first and mood-first both hand #1 to the quiet classical piece that matches the labels
    assert titles(prefs, "genre-first")[0] == "Moonlit Sonata"
    assert titles(prefs, "mood-first")[0] == "Moonlit Sonata"
    assert song_by_title("Moonlit Sonata")["energy"] < 0.3


def test_modes_disagree_on_the_top_three_for_a_pop_listener_who_wants_euphoria():
    prefs = BASE_PROFILES["high-energy pop"]  # pop genre, euphoric mood, energy 0.95
    top3 = {name: titles(prefs, name, k=3) for name in ("balanced", "genre-first", "mood-first", "energy-focused")}

    assert top3["balanced"] == ["Pulse Garden", "Sunrise City", "Gym Hero"]
    assert top3["genre-first"] == ["Sunrise City", "Gym Hero", "Pulse Garden"]  # both pop songs jump ahead
    assert top3["mood-first"] == ["Pulse Garden", "Sunrise City", "Sabor de Noche"]  # Gym Hero (intense) drops out
    assert top3["energy-focused"] == ["Pulse Garden", "Gym Hero", "Sunrise City"]  # Gym Hero is near the energy target
    assert len({tuple(order) for order in top3.values()}) == len(top3)


def test_label_modes_pick_a_calm_song_for_calm_labels_with_high_energy():
    prefs = BASE_PROFILES["adv-calm-labels-high-energy"]  # ambient + chill, energy 0.92

    assert titles(prefs, "balanced")[0] == "Pulse Garden"
    assert titles(prefs, "energy-focused")[0] == "Pulse Garden"
    assert titles(prefs, "genre-first")[0] == "Spacewalk Thoughts"  # the only ambient song
    assert titles(prefs, "mood-first")[0] == "Spacewalk Thoughts"


def test_extension_terms_keep_their_weights_in_every_mode():
    prefs = {**BASE_PREFS, "decade": 1990, "popularity": 50, "language": "en"}
    song = song_by_title("Sunrise City")

    def extension_points(mode):
        with_ext, _ = score_song(prefs, song, mode)
        without, _ = score_song(BASE_PREFS, song, mode)
        return with_ext - without

    assert all(extension_points(name) == pytest.approx(extension_points("balanced")) for name in MODES)


def test_unknown_mode_raises_value_error_listing_valid_modes():
    row = load_songs("data/songs.csv")[0]
    for call in (
        lambda: score_song(BASE_PREFS, row, "turbo"),
        lambda: recommend_songs(BASE_PREFS, [row], 1, "turbo"),
        lambda: Recommender([], mode="turbo"),
    ):
        with pytest.raises(ValueError) as error:
            call()
        assert "turbo" in str(error.value)
        for name in MODES:
            assert name in str(error.value)


def test_mode_names_ignore_capital_letters_and_extra_spaces():
    assert resolve_mode("  Mood-First ") is MODES["mood-first"]
    assert resolve_mode(None) is MODES["balanced"]


def test_a_custom_mode_object_can_be_passed_without_registering_it():
    custom = ScoringMode("tiny", "only energy", 1.0, 0.0, 0.0, 0.0)
    rows = load_songs("data/songs.csv")
    score, reasons = score_song({"energy": 0.5, "genre": "pop"}, rows[0], custom)

    assert score <= 1.0 and "genre match: pop (+0.00)" in reasons
    assert "tiny" not in MODES


@pytest.mark.parametrize("name", list(MODES))
def test_recommender_with_a_mode_matches_recommend_songs_with_that_mode(name):
    rows = load_songs("data/songs.csv")
    user = UserProfile("pop", "euphoric", 0.95, False, target_valence=0.85)
    expected = [row["id"] for row, _, _ in recommend_songs(Recommender._prefs(user), rows, 5, name)]
    rec = Recommender([Song(**row) for row in rows], mode=name)

    assert [song.id for song in rec.recommend(user, k=5)] == expected
    top = rec.recommend(user, k=1)[0]
    _, reasons = score_song(Recommender._prefs(user), asdict(top), name)
    assert rec.explain_recommendation(user, top) == "; ".join(reasons)


def test_recommender_without_a_mode_is_balanced():
    assert make_small_recommender().mode is MODES["balanced"]


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "src.main", *args],
                          cwd=REPO_ROOT, capture_output=True, text=True)


def test_cli_mode_prints_one_extra_header_line_and_uses_the_modes_weights():
    plain = run_cli("pop/happy")
    result = run_cli("pop/happy", "--mode", "mood-first")

    assert result.returncode == 0
    assert " Mode: mood-first" in result.stdout.splitlines()
    assert "mood match: happy (+4.00)" in result.stdout
    assert [line for line in result.stdout.splitlines() if line != " Mode: mood-first"][:4] == plain.stdout.splitlines()[:4]
    assert "Mode:" not in plain.stdout


def test_cli_explicit_balanced_mode_is_identical_to_no_mode():
    for args in (["pop/happy"], ["all"], ["adversarial"]):
        assert run_cli(*args, "--mode", "balanced").stdout == run_cli(*args).stdout


def test_cli_list_modes_prints_every_mode_and_exits_zero():
    result = run_cli("--list-modes")

    assert result.returncode == 0
    for name, mode in MODES.items():
        assert name in result.stdout and mode.description in result.stdout
    assert "(default)" in result.stdout and "Loaded songs" not in result.stdout
    assert result.stdout.count("(base max ") == len(MODES) and "(max " not in result.stdout


def test_cli_unknown_mode_fails_with_a_clear_message():
    result = run_cli("pop/happy", "--mode", "turbo")

    assert result.returncode == 2
    assert "turbo" in result.stderr and "balanced" in result.stderr and result.stdout == ""


def test_cli_unknown_profile_message_and_exit_code_are_unchanged():
    result = run_cli("nope")

    assert result.returncode == 1
    assert result.stderr.startswith("Unknown profile 'nope'. Choose from: all, adversarial, extensions, pop/happy")


WEIGHT_TABLE = {  # energy, mood, valence, genre
    "balanced": (4.0, 2.0, 1.0, 1.0),
    "genre-first": (2.0, 1.5, 0.5, 4.0),
    "mood-first": (2.0, 4.0, 1.0, 1.0),
    "energy-focused": (5.5, 1.0, 1.0, 0.5),
}


@pytest.mark.parametrize("name", list(WEIGHT_TABLE))
def test_the_four_shipped_modes_keep_their_exact_weights(name):
    mode = MODES[name]

    assert (mode.energy_weight, mode.mood_weight, mode.valence_weight, mode.genre_weight) == WEIGHT_TABLE[name]
    assert (mode.energy_sigma, mode.partial_mood_credit) == (0.25, 0.5)


def test_energy_sigma_and_partial_mood_credit_change_the_numbers():
    song = song_by_title("Sunrise City")  # pop, happy, energy 0.82
    wide = ScoringMode("wide", "x", 4.0, 2.0, 1.0, 1.0, energy_sigma=0.5, partial_mood_credit=0.25)
    prefs = {"energy": 0.62, "mood": "playful"}  # gap 0.20, same-cluster mood

    score, reasons = score_song(prefs, song, wide)
    energy_points = 4.0 * recommender.math.exp(-(0.2 ** 2) / (2 * 0.5 ** 2))
    assert score == pytest.approx(energy_points + 2.0 * 0.25)
    assert f"energy 0.82 vs target 0.62 (+{energy_points:.2f})" in reasons
    assert "similar mood: happy is close to playful (+0.50)" in reasons
    assert score != pytest.approx(score_song(prefs, song)[0])


def tied_songs():
    base = {"artist": "x", "genre": "pop", "mood": "happy", "tempo_bpm": 100.0, "valence": 0.5,
            "danceability": 0.5, "acousticness": 0.5}
    return [
        {**base, "id": 1, "title": "Beta", "energy": 0.75},
        {**base, "id": 2, "title": "Alpha", "energy": 0.25},
    ]


@pytest.mark.parametrize("name", list(MODES))
def test_equal_scores_and_gaps_are_broken_by_title_in_every_mode(name):
    ranked = recommend_songs({"energy": 0.5, "mood": "happy"}, tied_songs(), 2, name)

    assert ranked[0][1] == ranked[1][1]  # a real tie, so the title decides
    assert [song["title"] for song, _, _ in ranked] == ["Alpha", "Beta"]


def test_equal_scores_are_broken_by_the_smaller_energy_gap_before_the_title():
    flat = ScoringMode("flat", "energy worth nothing", 0.0, 2.0, 1.0, 1.0)  # scores tie whatever the energy
    songs = [{**tied_songs()[1], "title": "Alpha", "energy": 0.25}, {**tied_songs()[0], "title": "Zulu", "energy": 0.6}]
    ranked = recommend_songs({"energy": 0.5, "mood": "happy"}, songs, 2, flat)

    assert ranked[0][1] == ranked[1][1]
    assert [song["title"] for song, _, _ in ranked] == ["Zulu", "Alpha"]  # gap 0.1 beats gap 0.25


@pytest.mark.parametrize("name", list(MODES))
@pytest.mark.parametrize("profile", ["adv-conflict-sad", "high-energy pop", "adv-energy-only"])
def test_ranking_is_sorted_by_score_then_energy_gap_then_title_in_every_mode(name, profile):
    prefs = BASE_PROFILES[profile]
    rows = load_songs("data/songs.csv")
    ranked = recommend_songs(prefs, rows, k=len(rows), mode=name)
    target = prefs.get("energy")

    def key(item):
        song, score, _ = item
        return (-score, 0.0 if target is None else abs(song["energy"] - target), song["title"])

    assert [key(item) for item in ranked] == sorted(key(item) for item in ranked)
    assert [score for _, score, _ in ranked] == [score_song(prefs, song, name)[0] for song, _, _ in ranked]


@pytest.mark.parametrize("bad", [
    {"energy_weight": -0.1},
    {"mood_weight": float("nan")},
    {"valence_weight": float("inf")},
    {"genre_weight": -1.0},
    {"energy_sigma": 0.0},
    {"energy_sigma": -0.25},
    {"energy_sigma": float("inf")},
    {"partial_mood_credit": -0.1},
    {"partial_mood_credit": 1.5},
])
def test_scoring_mode_rejects_bad_numbers(bad):
    fields = {"energy_weight": 1.0, "mood_weight": 1.0, "valence_weight": 1.0, "genre_weight": 1.0, **bad}

    with pytest.raises(ValueError, match="mode 'bad'"):
        ScoringMode("bad", "x", **fields)


def test_scoring_mode_accepts_zero_weights_and_the_credit_limits():
    ScoringMode("zeros", "x", 0.0, 0.0, 0.0, 0.0, partial_mood_credit=0.0)
    ScoringMode("full", "x", 1.0, 1.0, 1.0, 1.0, partial_mood_credit=1.0)


# --- Diversity penalty ---

ALL_PROFILES = {**BASE_PROFILES, **EXTENSION_PROFILES}


def diverse_song(id, title, artist, genre, energy=0.5, mood="happy"):
    return {"id": id, "title": title, "artist": artist, "genre": genre, "mood": mood, "energy": energy,
            "tempo_bpm": 100.0, "valence": 0.5, "danceability": 0.5, "acousticness": 0.5}


# Mood is the only scored term, so base scores are exact: 2.0 for "happy", 1.0 for "playful" (same cluster)
MOOD_ONLY = ScoringMode("mood-only", "mood only", 0.0, 2.0, 0.0, 0.0)
MOOD_PREFS = {"energy": 0.5, "mood": "happy"}


def test_diversity_constants_are_the_documented_defaults():
    assert (ARTIST_PENALTY, GENRE_PENALTY) == (1.0, 0.5)


@pytest.mark.parametrize("name", list(ALL_PROFILES))
@pytest.mark.parametrize("mode", list(MODES))
def test_zero_penalties_equal_todays_result_on_every_profile_and_mode(name, mode):
    rows = load_songs("data/songs.csv")
    plain = recommend_songs(ALL_PROFILES[name], rows, k=20, mode=mode)

    assert recommend_songs(ALL_PROFILES[name], rows, 20, mode, 0.0, 0.0) == plain
    assert recommend_songs(ALL_PROFILES[name], rows, 20, mode, artist_penalty=0, genre_penalty=0) == plain
    assert recommend_songs(ALL_PROFILES[name], rows, 5, mode, 0, 0) == plain[:5]
    assert not any("diversity" in explanation for _, _, explanation in plain)


@pytest.mark.parametrize("name", list(ALL_PROFILES))
@pytest.mark.parametrize("mode", list(MODES))
def test_every_pick_is_its_base_score_minus_one_penalty_per_earlier_repeat(name, mode):
    prefs = ALL_PROFILES[name]
    rows = load_songs("data/songs.csv")
    ranked = recommend_songs(prefs, rows, 20, mode, ARTIST_PENALTY, GENRE_PENALTY)

    assert len(ranked) == len(rows) and len({song["id"] for song, _, _ in ranked}) == len(rows)
    for position, (song, score, explanation) in enumerate(ranked):
        earlier = [other for other, _, _ in ranked[:position]]
        same_artist = sum(other["artist"] == song["artist"] for other in earlier)
        same_genre = sum(other["genre"] == song["genre"] for other in earlier)
        base, reasons = score_song(prefs, song, mode)
        assert score == pytest.approx(base - ARTIST_PENALTY * same_artist - GENRE_PENALTY * same_genre)
        assert explanation.split("; ")[:len(reasons)] == reasons
        assert explanation.count("diversity penalty: artist") == same_artist
        assert explanation.count("diversity penalty: genre") == same_genre


@pytest.mark.parametrize("name", list(ALL_PROFILES))
@pytest.mark.parametrize("mode", list(MODES))
@pytest.mark.parametrize("penalties", [(ARTIST_PENALTY, GENRE_PENALTY), (100, 100), (0.0, 0.3), (2.5, 0.0)])
def test_reported_scores_never_increase_down_the_list(name, mode, penalties):
    rows = load_songs("data/songs.csv")
    scores = [score for _, score, _ in recommend_songs(ALL_PROFILES[name], rows, 20, mode, *penalties)]

    assert scores == sorted(scores, reverse=True)


def test_first_pick_is_unchanged_and_unpenalized():
    rows = load_songs("data/songs.csv")
    for name, prefs in ALL_PROFILES.items():
        plain = recommend_songs(prefs, rows, 1)
        assert recommend_songs(prefs, rows, 1, None, ARTIST_PENALTY, GENRE_PENALTY) == plain, name


def test_an_artist_repeat_loses_exactly_the_artist_penalty_per_earlier_song():
    songs = [diverse_song(1, "A1", "Neon Echo", "pop"), diverse_song(2, "A2", "Neon Echo", "rock"),
             diverse_song(3, "A3", "Neon Echo", "jazz"), diverse_song(4, "B1", "Other", "folk", mood="playful")]
    ranked = recommend_songs(MOOD_PREFS, songs, 4, MOOD_ONLY, artist_penalty=0.4)
    by_title = {song["title"]: (score, explanation) for song, score, explanation in ranked}

    assert by_title["A1"][0] == pytest.approx(2.0) and "diversity" not in by_title["A1"][1]
    assert by_title["A2"][0] == pytest.approx(1.6)
    assert by_title["A2"][1].endswith("diversity penalty: artist Neon Echo already recommended (-0.40)")
    assert by_title["A3"][0] == pytest.approx(1.2)
    assert by_title["A3"][1].count("diversity penalty: artist Neon Echo already recommended (-0.40)") == 2
    assert "diversity penalty: genre" not in by_title["A3"][1]


def test_a_genre_repeat_loses_exactly_the_genre_penalty_per_earlier_song():
    songs = [diverse_song(1, "A1", "One", "lofi"), diverse_song(2, "A2", "Two", "lofi"),
             diverse_song(3, "A3", "Three", "lofi"), diverse_song(4, "B1", "Four", "folk", mood="playful")]
    ranked = recommend_songs(MOOD_PREFS, songs, 4, MOOD_ONLY, genre_penalty=0.3)
    by_title = {song["title"]: (score, explanation) for song, score, explanation in ranked}

    assert by_title["A1"][0] == pytest.approx(2.0) and "diversity" not in by_title["A1"][1]
    assert by_title["A2"][0] == pytest.approx(1.7)
    assert by_title["A2"][1].endswith("diversity penalty: genre lofi already recommended (-0.30)")
    assert by_title["A3"][0] == pytest.approx(1.4)
    assert by_title["A3"][1].count("diversity penalty: genre lofi already recommended (-0.30)") == 2
    assert "diversity penalty: artist" not in by_title["A3"][1]


def test_artist_and_genre_penalties_stack_with_their_default_sizes():
    songs = [diverse_song(1, "First", "Neon Echo", "lofi", energy=0.5),
             diverse_song(2, "Second", "Neon Echo", "lofi", energy=0.6)]
    ranked = recommend_songs(MOOD_PREFS, songs, 2, MOOD_ONLY, ARTIST_PENALTY, GENRE_PENALTY)

    assert [song["title"] for song, _, _ in ranked] == ["First", "Second"]
    assert ranked[1][1] == pytest.approx(2.0 - 1.0 - 0.5)
    assert ranked[1][2].split("; ")[-2:] == [
        "diversity penalty: artist Neon Echo already recommended (-1.00)",
        "diversity penalty: genre lofi already recommended (-0.50)",
    ]


def test_a_song_with_no_repeated_artist_or_genre_gets_no_penalty_reason():
    songs = [diverse_song(1, "One", "A", "pop"), diverse_song(2, "Two", "B", "rock"), diverse_song(3, "Three", "C", "jazz")]
    ranked = recommend_songs(MOOD_PREFS, songs, 3, MOOD_ONLY, ARTIST_PENALTY, GENRE_PENALTY)

    assert [score for _, score, _ in ranked] == [2.0, 2.0, 2.0]
    assert all("diversity" not in explanation for _, _, explanation in ranked)
    assert ranked == recommend_songs(MOOD_PREFS, songs, 3, MOOD_ONLY)


def test_a_penalty_can_reorder_the_list_and_the_dropped_song_comes_back_later():
    songs = [diverse_song(1, "Top", "Neon Echo", "pop", energy=0.5),
             diverse_song(2, "Twin", "Neon Echo", "rock", energy=0.5001),
             diverse_song(3, "Fresh", "Other", "jazz", mood="playful")]

    assert [s["title"] for s, _, _ in recommend_songs(MOOD_PREFS, songs, 3, MOOD_ONLY)] == ["Top", "Twin", "Fresh"]
    ranked = recommend_songs(MOOD_PREFS, songs, 3, MOOD_ONLY, artist_penalty=1.5)
    assert [s["title"] for s, _, _ in ranked] == ["Top", "Fresh", "Twin"]
    assert [score for _, score, _ in ranked] == pytest.approx([2.0, 1.0, 0.5])


@pytest.mark.parametrize("mode", list(MODES))
@pytest.mark.parametrize("name", list(ALL_PROFILES))
def test_a_huge_artist_penalty_gives_five_different_artists(name, mode):
    rows = load_songs("data/songs.csv")
    assert len({song["artist"] for song in rows}) >= 5
    top = [song["artist"] for song, _, _ in recommend_songs(ALL_PROFILES[name], rows, 5, mode, artist_penalty=100)]

    assert len(set(top)) == 5


@pytest.mark.parametrize("name", list(ALL_PROFILES))
def test_a_huge_genre_penalty_gives_five_different_genres(name):
    rows = load_songs("data/songs.csv")
    top = [song["genre"] for song, _, _ in recommend_songs(ALL_PROFILES[name], rows, 5, None, genre_penalty=100)]

    assert len(set(top)) == 5


def test_ties_on_adjusted_score_go_to_the_smaller_energy_gap_then_the_title():
    songs = [
        diverse_song(1, "Lead", "X", "g1", energy=0.5),                        # 2.0, picked first
        diverse_song(2, "Aaa", "X", "g2", energy=0.8),                         # 2.0 - 1.0 = 1.0, gap 0.3
        diverse_song(3, "Zed", "Y", "g1", energy=0.4),                         # 2.0 - 1.0 = 1.0, gap 0.1
        diverse_song(4, "Alpha", "Z", "g3", energy=0.6, mood="playful"),       # 1.0, gap 0.1
    ]
    # on base scores the three 2.0 songs would rank Lead, Zed, Aaa and "playful" would be last
    assert [s["title"] for s, _, _ in recommend_songs(MOOD_PREFS, songs, 4, MOOD_ONLY)] == ["Lead", "Zed", "Aaa", "Alpha"]

    ranked = recommend_songs(MOOD_PREFS, songs, 4, MOOD_ONLY, 1.0, 1.0)
    assert [score for _, score, _ in ranked] == pytest.approx([2.0, 1.0, 1.0, 1.0])
    assert [s["title"] for s, _, _ in ranked] == ["Lead", "Alpha", "Zed", "Aaa"]  # gap 0.1 (title Alpha < Zed), then gap 0.3


def test_ties_without_an_energy_target_fall_back_to_the_title():
    songs = [diverse_song(1, "Lead", "X", "g1"), diverse_song(2, "Beta", "X", "g2"), diverse_song(3, "Alpha", "Y", "g3")]
    ranked = recommend_songs({"mood": "happy"}, songs, 3, MOOD_ONLY, artist_penalty=1.0)

    assert [s["title"] for s, _, _ in ranked] == ["Alpha", "Beta", "Lead"]  # all tie at 2.0, so Alpha then Beta by title; Lead is then charged for Beta
    assert [score for _, score, _ in ranked] == pytest.approx([2.0, 2.0, 1.0])


def test_k_edge_cases_with_diversity_on():
    rows = load_songs("data/songs.csv")
    prefs = PROFILES["lofi/chill"]
    full = recommend_songs(prefs, rows, 20, None, ARTIST_PENALTY, GENRE_PENALTY)

    for bad_k in (0, -1, -20):
        assert recommend_songs(prefs, rows, bad_k, None, ARTIST_PENALTY, GENRE_PENALTY) == []
    assert recommend_songs(prefs, rows, 100, None, ARTIST_PENALTY, GENRE_PENALTY) == full and len(full) == len(rows)
    assert recommend_songs(prefs, rows, 5, None, ARTIST_PENALTY, GENRE_PENALTY) == full[:5]
    assert recommend_songs(prefs, [], 5, None, ARTIST_PENALTY, GENRE_PENALTY) == []


@pytest.mark.parametrize("keyword", ["artist_penalty", "genre_penalty"])
@pytest.mark.parametrize("bad", [-0.1, -1, math.nan, math.inf, -math.inf, True, False, "1.0", None, [1.0]])
def test_bad_penalties_raise_a_clear_value_error(keyword, bad):
    rows = load_songs("data/songs.csv")

    with pytest.raises(ValueError, match=f"{keyword} must be a finite number >= 0"):
        recommend_songs(BASE_PROFILES["pop/happy"], rows, 5, **{keyword: bad})
    with pytest.raises(ValueError, match=keyword):
        Recommender([Song(**row) for row in rows], **{keyword: bad})


def test_integer_and_zero_penalties_are_accepted():
    rows = load_songs("data/songs.csv")

    assert recommend_songs(BASE_PROFILES["pop/happy"], rows, 5, artist_penalty=1, genre_penalty=0)


@pytest.mark.parametrize("mode", list(MODES))
@pytest.mark.parametrize("name", ["lofi/chill", "pop/happy", "adv-energy-only", "ext-instrumental-focus"])
def test_recommender_passes_the_penalties_through_to_recommend(name, mode):
    rows = load_songs("data/songs.csv")
    prefs = ALL_PROFILES[name]
    user = UserProfile(prefs.get("genre"), prefs.get("mood"), prefs.get("energy"), False, prefs.get("valence"),
                       **{key: prefs[key] for key in ("mood_tags", "instrumentalness", "speechiness", "language") if key in prefs})
    songs = [Song(**row) for row in rows]
    rec = Recommender(songs, mode, ARTIST_PENALTY, GENRE_PENALTY)
    expected = recommend_songs(Recommender._prefs(user), rows, 5, mode, ARTIST_PENALTY, GENRE_PENALTY)

    assert [song.id for song in rec.recommend(user)] == [song["id"] for song, _, _ in expected]
    assert (rec.artist_penalty, rec.genre_penalty) == (ARTIST_PENALTY, GENRE_PENALTY)
    plain = Recommender(songs, mode)
    assert (plain.artist_penalty, plain.genre_penalty) == (0.0, 0.0)
    assert [s.id for s in plain.recommend(user)] == [s["id"] for s, _, _ in recommend_songs(Recommender._prefs(user), rows, 5, mode)]


def test_recommender_explanations_do_not_need_diversity_text():
    rows = load_songs("data/songs.csv")
    rec = Recommender([Song(**row) for row in rows], None, ARTIST_PENALTY, GENRE_PENALTY)
    user = make_user()

    assert "diversity" not in rec.explain_recommendation(user, rec.recommend(user)[0])


def test_the_catalog_with_diversity_on_has_a_real_effect_for_lofi_chill():
    rows = load_songs("data/songs.csv")
    prefs = PROFILES["lofi/chill"]
    before = [s["title"] for s, _, _ in recommend_songs(prefs, rows, 5)]
    after = [s["title"] for s, _, _ in recommend_songs(prefs, rows, 5, None, ARTIST_PENALTY, GENRE_PENALTY)]

    assert before != after and len(set(before)) == len(set(after)) == 5


def test_cli_diverse_adds_one_header_line_and_penalty_reasons():
    plain = run_cli("lofi/chill")
    result = run_cli("lofi/chill", "--diverse")
    header = " Diversity: on (artist -1.00, genre -0.50)"

    assert result.returncode == 0 and "Diversity" not in plain.stdout
    lines = result.stdout.splitlines()
    plain_lines = plain.stdout.splitlines()
    assert lines[3] == header and lines[:3] == plain_lines[:3] and lines[4:5] == plain_lines[3:4]  # the Targets line follows
    assert lines.count(header) == 1
    assert "diversity penalty: genre lofi already recommended (-0.50)" in result.stdout
    assert result.stdout != plain.stdout


def test_cli_without_diverse_prints_no_diversity_text():
    for args in (["pop/happy"], ["all"], ["adversarial"], ["extensions"], ["lofi/chill", "--mode", "mood-first"]):
        result = run_cli(*args)
        assert result.returncode == 0 and "Diversity" not in result.stdout and "diversity penalty" not in result.stdout


def test_cli_diverse_combines_with_modes_and_profile_groups():
    header = " Diversity: on (artist -1.00, genre -0.50)"
    result = run_cli("lofi/chill", "--mode", "genre-first", "--diverse")

    assert result.returncode == 0
    lines = result.stdout.splitlines()
    assert lines[3] == " Mode: genre-first" and lines[4] == header  # the mode line comes first
    for group in ("all", "adversarial", "extensions"):
        grouped = run_cli(group, "--diverse")
        assert grouped.returncode == 0
        assert grouped.stdout.count(header) == grouped.stdout.count(" Top 5 recommendations for profile:") > 0
    for mode in MODES:
        assert run_cli("all", "--mode", mode, "--diverse").returncode == 0


def test_cli_diverse_scores_match_the_library_call():
    rows = load_songs("data/songs.csv")
    expected = recommend_songs(PROFILES["lofi/chill"], rows, 5, None, ARTIST_PENALTY, GENRE_PENALTY)
    out = run_cli("lofi/chill", "--diverse").stdout

    for rank, (song, score, _) in enumerate(expected, start=1):
        assert f"{rank}. {song['title']} by {song['artist']}" in out
        assert f"Score: {score:.2f}" in out


def test_cli_existing_errors_are_unchanged_with_diverse():
    result = run_cli("nope", "--diverse")

    assert result.returncode == 1 and result.stderr.startswith("Unknown profile 'nope'")
    assert run_cli("pop/happy", "--mode", "turbo", "--diverse").returncode == 2


# --- Validation of k, huge penalties and missing artist or genre ---

BOTH_PATHS = [{}, {"artist_penalty": ARTIST_PENALTY, "genre_penalty": GENRE_PENALTY}]


@pytest.mark.parametrize("penalties", BOTH_PATHS)
@pytest.mark.parametrize("k", [0, -1, -5])
def test_k_of_zero_or_less_returns_an_empty_list_on_both_paths(k, penalties):
    rows = load_songs("data/songs.csv")

    assert recommend_songs(PROFILES["lofi/chill"], rows, k, **penalties) == []


@pytest.mark.parametrize("penalties", BOTH_PATHS)
@pytest.mark.parametrize("bad", [None, 2.5, 3.0, "3", True, False, [3]])
def test_k_must_be_a_whole_number_on_both_paths(bad, penalties):
    rows = load_songs("data/songs.csv")

    with pytest.raises(ValueError, match="k must be a whole number"):
        recommend_songs(PROFILES["lofi/chill"], rows, bad, **penalties)


@pytest.mark.parametrize("penalties", BOTH_PATHS)
def test_integer_like_k_values_are_accepted_on_both_paths(penalties):
    rows = load_songs("data/songs.csv")
    prefs = PROFILES["lofi/chill"]

    assert len(recommend_songs(prefs, rows, 3, **penalties)) == 3
    assert recommend_songs(prefs, rows, 3, **penalties) == recommend_songs(prefs, rows, True * 3, **penalties)
    assert len(recommend_songs(prefs, rows, 10**30, **penalties)) == len(rows)


def test_recommender_rejects_a_bad_k_and_returns_nothing_for_a_negative_k():
    rows = load_songs("data/songs.csv")
    user = make_user()

    for rec in (Recommender([Song(**row) for row in rows]),
                Recommender([Song(**row) for row in rows], None, ARTIST_PENALTY, GENRE_PENALTY)):
        assert rec.recommend(user, k=-3) == []
        with pytest.raises(ValueError, match="k must be a whole number"):
            rec.recommend(user, k=2.5)


@pytest.mark.parametrize("keyword", ["artist_penalty", "genre_penalty"])
@pytest.mark.parametrize("huge", [2**2000, -(2**2000), 10**400])
def test_a_huge_integer_penalty_raises_value_error_not_overflow_error(keyword, huge):
    rows = load_songs("data/songs.csv")

    with pytest.raises(ValueError, match=f"{keyword} must be a finite number >= 0"):
        check_penalty(keyword, huge)
    with pytest.raises(ValueError, match=keyword):
        recommend_songs(BASE_PROFILES["pop/happy"], rows, 5, **{keyword: huge})


def test_a_large_but_finite_integer_penalty_is_accepted():
    assert check_penalty("p", 10**300) == 1e300


def test_a_song_without_an_artist_key_works_with_diversity_on():
    songs = [diverse_song(1, "A", "X", "g1"), diverse_song(2, "B", "X", "g2"), diverse_song(3, "C", "Y", "g3")]
    del songs[1]["artist"]
    ranked = recommend_songs(MOOD_PREFS, songs, 3, MOOD_ONLY, artist_penalty=1.0)

    assert [score for _, score, _ in ranked] == pytest.approx([2.0, 2.0, 2.0])
    assert not any("diversity" in explanation for _, _, explanation in ranked)


def test_none_artists_and_none_genres_are_never_the_same():
    songs = [diverse_song(1, "A", None, None), diverse_song(2, "B", None, None), diverse_song(3, "C", "X", "g")]
    ranked = recommend_songs(MOOD_PREFS, songs, 3, MOOD_ONLY, artist_penalty=5.0, genre_penalty=5.0)

    assert [score for _, score, _ in ranked] == pytest.approx([2.0, 2.0, 2.0])
    assert not any("diversity" in explanation for _, _, explanation in ranked)


def test_a_none_artist_is_not_the_same_as_a_named_artist_but_real_repeats_still_count():
    songs = [diverse_song(1, "A", "X", "g1"), diverse_song(2, "B", None, "g2"), diverse_song(3, "C", "X", "g3")]
    ranked = recommend_songs(MOOD_PREFS, songs, 3, MOOD_ONLY, artist_penalty=1.0)

    assert [(s["title"], score) for s, score, _ in ranked] == [("A", 2.0), ("B", 2.0), ("C", 1.0)]
