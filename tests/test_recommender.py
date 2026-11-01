import subprocess
import sys
from pathlib import Path

import pytest

from src import recommender
from src.main import EXTENSION_PROFILES
from src.recommender import (
    Song, UserProfile, Recommender, clean_prefs, load_songs, recommend_songs, score_song,
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
