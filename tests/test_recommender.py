import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from src import recommender
from src.main import ADVERSARIAL_PROFILES, EXTENSION_PROFILES, PROFILES
from src.recommender import (
    MODES, ScoringMode, Song, UserProfile, Recommender, clean_prefs, load_songs, recommend_songs,
    resolve_mode, score_song,
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
