"""
Command line runner for the Music Recommender Simulation.

Usage (from the project root):
    python -m src.main              # default pop/happy profile
    python -m src.main lofi/chill   # any profile name from PROFILES
"""

import sys

from src.recommender import load_songs, recommend_songs

PROFILES = {
    "pop/happy": {
        "genre": "pop",
        "mood": "happy",
        "energy": 0.80,
        "valence": 0.80,
        "likes_acoustic": False,
    },
    # A late-night study listener who wants calm, mostly acoustic music
    "lofi/chill": {
        "genre": "lofi",
        "mood": "chill",
        "energy": 0.40,
        "valence": 0.60,
        "likes_acoustic": True,
    },
}
DEFAULT_PROFILE = "pop/happy"
WIDTH = 64


def print_recommendations(profile_name: str, user_prefs: dict, recommendations: list) -> None:
    print("=" * WIDTH)
    print(f" Top {len(recommendations)} recommendations for profile: {profile_name}")
    print(
        f" Targets: genre={user_prefs['genre']}, mood={user_prefs['mood']}, "
        f"energy={user_prefs['energy']:.2f}, valence={user_prefs['valence']:.2f}"
    )
    print("=" * WIDTH)

    for rank, (song, score, explanation) in enumerate(recommendations, start=1):
        print(f"\n{rank}. {song['title']} by {song['artist']}")
        print(f"   Score: {score:.2f}   ({song['genre']}, {song['mood']})")
        print("   Why:")
        for reason in explanation.split("; "):
            print(f"     - {reason}")
    print()


def main() -> None:
    profile_name = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROFILE
    if profile_name not in PROFILES:
        sys.exit(f"Unknown profile '{profile_name}'. Choose from: {', '.join(PROFILES)}")
    user_prefs = PROFILES[profile_name]

    songs = load_songs("data/songs.csv")
    print(f"Loaded songs: {len(songs)}")

    recommendations = recommend_songs(user_prefs, songs, k=5)
    print_recommendations(profile_name, user_prefs, recommendations)


if __name__ == "__main__":
    main()
