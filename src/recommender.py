import csv
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field, asdict
import math
import re

# Algorithm Recipe weights (maximum score is 8.0)
ENERGY_WEIGHT = 4.0
MOOD_WEIGHT = 2.0
VALENCE_WEIGHT = 1.0
GENRE_WEIGHT = 1.0
ENERGY_SIGMA = 0.25
PARTIAL_MOOD_CREDIT = 0.5  # fraction of MOOD_WEIGHT for a same-cluster mood

# Optional extension terms: each one only counts when the profile has its key
# (a profile using all of them can score up to 5.0 extra points on top of the 8.0 above)
TAG_WEIGHT = 1.5
DECADE_WEIGHT = 1.0
DECADE_SPAN = 50  # years apart at which decade closeness reaches 0
POPULARITY_WEIGHT = 1.0
INSTRUMENTALNESS_WEIGHT = 0.5
SPEECHINESS_WEIGHT = 0.5
LANGUAGE_WEIGHT = 0.5

MOOD_CLUSTERS = [
    {"chill", "relaxed", "focused", "dreamy"},
    {"melancholy", "wistful", "nostalgic", "moody"},
    {"happy", "uplifting", "playful", "euphoric"},
    {"intense", "angry", "confident"},
]

@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float
    # Extension attributes (invented values); optional so the original 10 fields still work
    popularity: Optional[int] = None
    release_decade: Optional[int] = None
    mood_tags: List[str] = field(default_factory=list)
    instrumentalness: Optional[float] = None
    speechiness: Optional[float] = None
    language: Optional[str] = None

@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py
    """
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool
    target_valence: Optional[float] = None
    # Optional extension preferences (same meaning as the profile keys of the same name)
    mood_tags: Optional[List[str]] = None
    decade: Optional[int] = None
    popularity: Optional[float] = None
    instrumentalness: Optional[float] = None
    speechiness: Optional[float] = None
    language: Optional[str] = None

class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py
    """
    def __init__(self, songs: List[Song]):
        self.songs = songs

    @staticmethod
    def _prefs(user: UserProfile) -> Dict:
        """Map a UserProfile to the prefs dict used by score_song."""
        prefs = {
            "genre": user.favorite_genre,
            "mood": user.favorite_mood,
            "energy": user.target_energy,
        }
        if user.target_valence is not None:
            prefs["valence"] = user.target_valence
        for key in EXTENSION_KEYS:
            if getattr(user, key) is not None:
                prefs[key] = getattr(user, key)
        return prefs

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        """Return the top k songs for the user, best first, reusing recommend_songs."""
        by_id = {song.id: song for song in self.songs}
        rows = [asdict(song) for song in self.songs]
        ranked = recommend_songs(self._prefs(user), rows, k)
        return [by_id[row["id"]] for row, _, _ in ranked]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        """Explain why a song fits the user, reusing the reasons from score_song."""
        _, reasons = score_song(self._prefs(user), asdict(song))
        return "; ".join(reasons) or "No preferences were given, so this song was not scored."

def load_songs(csv_path: str) -> List[Dict]:
    """Load songs from a CSV file as dicts, converting numeric columns to int or float."""
    int_fields = ("id",)
    float_fields = ("energy", "tempo_bpm", "valence", "danceability", "acousticness")
    # Extension columns may be missing from older files; a blank cell becomes None
    optional_int_fields = ("popularity",)
    optional_float_fields = ("instrumentalness", "speechiness")

    songs: List[Dict] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for name in int_fields:
                row[name] = int(row[name])
            for name in float_fields:
                row[name] = float(row[name])
            for name in optional_int_fields:
                if name in row:
                    row[name] = int(row[name]) if row[name].strip() else None
            for name in optional_float_fields:
                if name in row:
                    row[name] = float(row[name]) if row[name].strip() else None
            if "release_decade" in row:
                row["release_decade"] = parse_decade(row["release_decade"]) if row["release_decade"].strip() else None
            if "mood_tags" in row:
                row["mood_tags"] = split_tags(row["mood_tags"])
            if "language" in row:
                row["language"] = row["language"].strip().lower() or None
            songs.append(row)
    return songs

def split_tags(tags) -> List[str]:
    """Turn a list or a 'a|b' / 'a,b' string into a list of unique trimmed lowercase tags."""
    if tags is None:
        return []
    parts = re.split(r"[|,]", tags) if isinstance(tags, str) else tags
    unique: List[str] = []
    for tag in parts:
        tag = str(tag).strip().lower()
        if tag and tag not in unique:
            unique.append(tag)
    return unique

def parse_decade(value) -> int:
    """Turn 1994, '1990' or '1990s' into its decade (1990); raise ValueError otherwise."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    match = re.fullmatch(r"(\d{4})s?", str(value).strip().lower())
    if match is None:
        raise ValueError(f"'decade' must be a year like 1990 or '1990s', got {value!r}")
    return int(match.group(1)) // 10 * 10

TEXT_PREFS = ("genre", "mood")
NUMBER_RANGES = {"energy": 1.0, "valence": 1.0}
NUMBER_PREFS = tuple(NUMBER_RANGES)
EXTENSION_NUMBER_RANGES = {"popularity": 100.0, "instrumentalness": 1.0, "speechiness": 1.0}
EXTENSION_KEYS = ("mood_tags", "decade", "language") + tuple(EXTENSION_NUMBER_RANGES)

def clean_prefs(user_prefs: Dict) -> Dict:
    """Return a cleaned copy of a profile: trimmed lowercase text, numbers clamped to their range."""
    cleaned = dict(user_prefs)
    for key in TEXT_PREFS + ("language",):
        if cleaned.get(key) is not None:
            cleaned[key] = str(cleaned[key]).strip().lower() or None
    # Extension keys: blank text counts as absent, and True/False is not a number
    for key in ("decade",) + tuple(EXTENSION_NUMBER_RANGES):
        if isinstance(cleaned.get(key), str) and not cleaned[key].strip():
            cleaned[key] = None
    for key in EXTENSION_NUMBER_RANGES:
        if isinstance(cleaned.get(key), bool):
            raise ValueError(f"'{key}' must be a number, got {cleaned[key]!r}")
    for key, top in {**NUMBER_RANGES, **EXTENSION_NUMBER_RANGES}.items():
        if cleaned.get(key) is not None:
            try:
                value = float(cleaned[key])
            except (TypeError, ValueError):
                value = math.nan
            if math.isnan(value):
                raise ValueError(f"'{key}' must be a number between 0 and {top:g}, got {cleaned[key]!r}")
            cleaned[key] = min(max(value, 0.0), top)
    if cleaned.get("mood_tags") is not None:
        if not isinstance(cleaned["mood_tags"], (str, list, tuple, set)):
            raise ValueError(f"'mood_tags' must be a list or a 'a|b' string, got {cleaned['mood_tags']!r}")
        cleaned["mood_tags"] = split_tags(cleaned["mood_tags"]) or None
    if cleaned.get("decade") is not None:
        cleaned["decade"] = parse_decade(cleaned["decade"])
    if all(cleaned.get(key) is None for key in TEXT_PREFS + NUMBER_PREFS + EXTENSION_KEYS):
        raise ValueError(
            "profile needs at least one of: genre, mood, energy, valence, "
            + ", ".join(EXTENSION_KEYS)
        )
    return cleaned

def score_song(user_prefs: Dict, song: Dict) -> Tuple[float, List[str]]:
    """Score one song against user preferences, returning (score, list of reasons)."""
    user_prefs = clean_prefs(user_prefs)
    score = 0.0
    reasons: List[str] = []

    target_energy = user_prefs.get("energy")
    if target_energy is not None:
        gap = abs(song["energy"] - target_energy)
        points = ENERGY_WEIGHT * math.exp(-(gap ** 2) / (2 * ENERGY_SIGMA ** 2))
        score += points
        reasons.append(
            f"energy {song['energy']:.2f} vs target {target_energy:.2f} (+{points:.2f})"
        )

    user_mood = user_prefs.get("mood")
    if user_mood is not None:
        if song["mood"] == user_mood:
            score += MOOD_WEIGHT
            reasons.append(f"mood match: {song['mood']} (+{MOOD_WEIGHT:.2f})")
        elif any(user_mood in c and song["mood"] in c for c in MOOD_CLUSTERS):
            points = MOOD_WEIGHT * PARTIAL_MOOD_CREDIT
            score += points
            reasons.append(
                f"similar mood: {song['mood']} is close to {user_mood} (+{points:.2f})"
            )

    target_valence = user_prefs.get("valence")
    if target_valence is not None:
        points = VALENCE_WEIGHT * (1 - abs(song["valence"] - target_valence))
        score += points
        reasons.append(
            f"valence {song['valence']:.2f} vs target {target_valence:.2f} (+{points:.2f})"
        )

    if song["genre"] == user_prefs.get("genre"):
        score += GENRE_WEIGHT
        reasons.append(f"genre match: {song['genre']} (+{GENRE_WEIGHT:.2f})")

    # Extension terms: skipped when the profile lacks the key or the song lacks the field
    wanted_tags = user_prefs.get("mood_tags")
    song_tags = split_tags(song.get("mood_tags"))
    if wanted_tags and song_tags:
        matched = [tag for tag in wanted_tags if tag in song_tags]
        if matched:
            points = TAG_WEIGHT * len(matched) / len(wanted_tags)
            score += points
            reasons.append(
                f"mood tags matched {len(matched)} of {len(wanted_tags)} requested: "
                f"{', '.join(matched)} (+{points:.2f})"
            )

    target_decade = user_prefs.get("decade")
    if target_decade is not None and song.get("release_decade") is not None:
        gap = abs(song["release_decade"] - target_decade)
        points = DECADE_WEIGHT * max(0.0, 1 - gap / DECADE_SPAN)
        score += points
        reasons.append(
            f"decade {song['release_decade']}s vs target {target_decade}s (+{points:.2f})"
        )

    target_popularity = user_prefs.get("popularity")
    if target_popularity is not None and song.get("popularity") is not None:
        points = POPULARITY_WEIGHT * (1 - abs(song["popularity"] - target_popularity) / 100)
        score += points
        reasons.append(
            f"popularity {song['popularity']} vs target {target_popularity:.0f} (+{points:.2f})"
        )

    for key, weight in (
        ("instrumentalness", INSTRUMENTALNESS_WEIGHT),
        ("speechiness", SPEECHINESS_WEIGHT),
    ):
        target = user_prefs.get(key)
        if target is not None and song.get(key) is not None:
            points = weight * (1 - abs(song[key] - target))
            score += points
            reasons.append(f"{key} {song[key]:.2f} vs target {target:.2f} (+{points:.2f})")

    user_language = user_prefs.get("language")
    song_language = song.get("language")
    if user_language is not None and song_language is not None:
        if str(song_language).strip().lower() == user_language:
            score += LANGUAGE_WEIGHT
            reasons.append(f"language match: {user_language} (+{LANGUAGE_WEIGHT:.2f})")

    return score, reasons

def recommend_songs(user_prefs: Dict, songs: List[Dict], k: int = 5) -> List[Tuple[Dict, float, str]]:
    """Score every song and return the top k as (song, score, explanation), best first."""
    prefs = clean_prefs(user_prefs)
    scored = [(song, *score_song(prefs, song)) for song in songs]
    target_energy = prefs.get("energy")

    def rank_key(item):
        song, score, _ = item
        energy_gap = 0.0 if target_energy is None else abs(song["energy"] - target_energy)
        return (-score, energy_gap, song["title"])

    ranked = sorted(scored, key=rank_key)
    return [(song, score, "; ".join(reasons)) for song, score, reasons in ranked[:k]]
