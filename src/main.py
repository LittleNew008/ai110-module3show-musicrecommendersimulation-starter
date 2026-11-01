"""
Command line runner for the Music Recommender Simulation.

Usage (from the project root):
    python -m src.main              # default pop/happy profile
    python -m src.main lofi/chill   # any profile name from PROFILES
    python -m src.main all          # run every profile in PROFILES
    python -m src.main adversarial  # run the edge-case profiles
    python -m src.main extensions   # run the profiles that use the extra song attributes
    python -m src.main pop/happy --mode mood-first   # rank with another scoring mode
    python -m src.main --list-modes                  # show the scoring modes
    python -m src.main lofi/chill --diverse          # penalize repeated artists and genres in the top 5
"""

import argparse
import sys

from src.recommender import (
    ARTIST_PENALTY, DEFAULT_MODE, EXTENSION_KEYS, GENRE_PENALTY, MODES,
    load_songs, recommend_songs, resolve_mode,
)

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
    # A workout listener who wants loud, upbeat, danceable pop
    "high-energy pop": {
        "genre": "pop",
        "mood": "euphoric",
        "energy": 0.95,
        "valence": 0.85,
        "likes_acoustic": False,
    },
    # A listener who wants heavy, dark, aggressive music
    "deep intense rock": {
        "genre": "rock",
        "mood": "intense",
        "energy": 0.95,
        "valence": 0.25,
        "likes_acoustic": False,
    },
}
# Edge cases designed to trick the scoring logic (see "Stress Test" in README.md)
ADVERSARIAL_PROFILES = {
    # Conflicting: wants sad, dark music at very high energy
    "adv-conflict-sad": {
        "genre": "classical", "mood": "melancholy",
        "energy": 0.95, "valence": 0.20, "likes_acoustic": True,
    },
    # Genre and mood labels that do not exist in the catalog
    "adv-ghost-labels": {
        "genre": "k-pop", "mood": "aggressive",
        "energy": 0.70, "valence": 0.70, "likes_acoustic": False,
    },
    # Extreme numeric targets, but labels that point at loud, bright songs
    "adv-extreme-zero": {
        "genre": "pop", "mood": "happy",
        "energy": 0.0, "valence": 0.0, "likes_acoustic": True,
    },
    # Calm labels with a very high energy target
    "adv-calm-labels-high-energy": {
        "genre": "ambient", "mood": "chill",
        "energy": 0.92, "valence": 0.85, "likes_acoustic": True,
    },
    # Thin profile: only an energy target
    "adv-energy-only": {"energy": 0.5},
    # A mood that is in no mood cluster, with a perfect catalog match
    "adv-romantic-rnb": {
        "genre": "r&b", "mood": "romantic",
        "energy": 0.48, "valence": 0.62, "likes_acoustic": False,
    },
}
# Profiles that also use the extension attributes (mood_tags, decade, popularity, ...)
EXTENSION_PROFILES = {
    # Wants warm, wistful 1990s songs; popularity does not matter
    "ext-90s-nostalgia": {
        "genre": "country", "mood": "nostalgic",
        "energy": 0.55, "valence": 0.65, "likes_acoustic": True,
        "mood_tags": ["nostalgic", "warm", "sentimental"], "decade": 1990,
    },
    # Wants quiet, little-known music from the back of the catalog
    "ext-hidden-gems": {
        "genre": "folk", "mood": "wistful",
        "energy": 0.33, "valence": 0.40, "likes_acoustic": True,
        "popularity": 15, "mood_tags": "melancholic|warm",
    },
    # Wants vocal-free music to work to
    "ext-instrumental-focus": {
        "genre": "lofi", "mood": "focused",
        "energy": 0.40, "valence": 0.60, "likes_acoustic": True,
        "instrumentalness": 0.95, "speechiness": 0.0, "language": "instrumental",
        "mood_tags": ["calm", "steady"],
    },
    # Wants loud, sung-along pop hits
    "ext-chart-hits": {
        "genre": "pop", "mood": "happy",
        "energy": 0.85, "valence": 0.80, "likes_acoustic": False,
        "popularity": 90, "decade": "2010s", "language": "en",
    },
}
ALL_PROFILES = {**PROFILES, **ADVERSARIAL_PROFILES, **EXTENSION_PROFILES}
DEFAULT_PROFILE = "pop/happy"
WIDTH = 64


def print_recommendations(
    profile_name: str, user_prefs: dict, recommendations: list, mode_name: str = DEFAULT_MODE, diverse: bool = False
) -> None:
    print("=" * WIDTH)
    print(f" Top {len(recommendations)} recommendations for profile: {profile_name}")
    if mode_name != DEFAULT_MODE:
        print(f" Mode: {mode_name}")
    if diverse:
        print(f" Diversity: on (artist -{ARTIST_PENALTY:.2f}, genre -{GENRE_PENALTY:.2f})")
    targets = ", ".join(
        f"{key}={user_prefs[key]:.2f}" if isinstance(user_prefs[key], float) else f"{key}={user_prefs[key]}"
        for key in ("genre", "mood", "energy", "valence")
        if key in user_prefs
    )
    extras = ", ".join(
        f"{key}={'|'.join(user_prefs[key]) if isinstance(user_prefs[key], (list, tuple)) else user_prefs[key]}"
        for key in EXTENSION_KEYS
        if key in user_prefs
    )
    if extras:
        targets += f", {extras}"

    print(f" Targets: {targets}")
    print("=" * WIDTH)

    for rank, (song, score, explanation) in enumerate(recommendations, start=1):
        print(f"\n{rank}. {song['title']} by {song['artist']}")
        print(f"   Score: {score:.2f}   ({song['genre']}, {song['mood']})")
        print("   Why:")
        for reason in explanation.split("; "):
            print(f"     - {reason}")
    print()


def print_modes() -> None:
    for mode in MODES.values():
        default = " (default)" if mode.name == DEFAULT_MODE else ""
        print(f"{mode.name}{default}: {mode.description}")
        print(
            f"    energy {mode.energy_weight:g}, mood {mode.mood_weight:g}, "
            f"valence {mode.valence_weight:g}, genre {mode.genre_weight:g} (base max {mode.max_score:g})"
        )


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="python -m src.main", description="Music Recommender Simulation")
    parser.add_argument(
        "profile", nargs="?", default=DEFAULT_PROFILE,
        help=f"a profile name, or all, adversarial, extensions (default: {DEFAULT_PROFILE})",
    )
    parser.add_argument("--mode", metavar="MODE", help=f"scoring mode: {', '.join(MODES)} (default: {DEFAULT_MODE})")
    parser.add_argument("--list-modes", action="store_true", help="show the scoring modes and exit")
    parser.add_argument(
        "--diverse", action="store_true",
        help=f"penalize repeated artists (-{ARTIST_PENALTY:.2f}) and genres (-{GENRE_PENALTY:.2f}) in the top results",
    )
    args = parser.parse_args(argv)

    if args.list_modes:
        print_modes()
        return

    arg = args.profile
    if arg == "all":
        profile_names = list(PROFILES)
    elif arg == "adversarial":
        profile_names = list(ADVERSARIAL_PROFILES)
    elif arg == "extensions":
        profile_names = list(EXTENSION_PROFILES)
    elif arg in ALL_PROFILES:
        profile_names = [arg]
    else:
        sys.exit(
            f"Unknown profile '{arg}'. Choose from: all, adversarial, extensions, {', '.join(ALL_PROFILES)}"
        )
    try:
        mode = resolve_mode(args.mode)
    except ValueError as error:
        parser.error(str(error))

    penalties = {"artist_penalty": ARTIST_PENALTY, "genre_penalty": GENRE_PENALTY} if args.diverse else {}

    songs = load_songs("data/songs.csv")
    print(f"Loaded songs: {len(songs)}")

    for profile_name in profile_names:
        user_prefs = ALL_PROFILES[profile_name]
        recommendations = recommend_songs(user_prefs, songs, k=5, mode=mode, **penalties)
        print_recommendations(profile_name, user_prefs, recommendations, mode.name, args.diverse)


if __name__ == "__main__":
    main()
