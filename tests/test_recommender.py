import pytest

from src.recommender import Song, UserProfile, Recommender, load_songs, recommend_songs

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
