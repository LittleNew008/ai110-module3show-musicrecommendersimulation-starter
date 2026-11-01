import csv
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
import math

# Algorithm Recipe weights (maximum score is 8.0)
ENERGY_WEIGHT = 4.0
MOOD_WEIGHT = 2.0
VALENCE_WEIGHT = 1.0
GENRE_WEIGHT = 1.0
ENERGY_SIGMA = 0.25
PARTIAL_MOOD_CREDIT = 0.5  # fraction of MOOD_WEIGHT for a same-cluster mood

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

    songs: List[Dict] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for field in int_fields:
                row[field] = int(row[field])
            for field in float_fields:
                row[field] = float(row[field])
            songs.append(row)
    return songs

TEXT_PREFS = ("genre", "mood")
NUMBER_PREFS = ("energy", "valence")

def clean_prefs(user_prefs: Dict) -> Dict:
    """Return a cleaned copy of a profile: trimmed lowercase text, numbers clamped to 0..1."""
    cleaned = dict(user_prefs)
    for key in TEXT_PREFS:
        if cleaned.get(key) is not None:
            cleaned[key] = str(cleaned[key]).strip().lower() or None
    for key in NUMBER_PREFS:
        if cleaned.get(key) is not None:
            try:
                value = float(cleaned[key])
            except (TypeError, ValueError):
                value = math.nan
            if math.isnan(value):
                raise ValueError(f"'{key}' must be a number between 0 and 1, got {cleaned[key]!r}")
            cleaned[key] = min(max(value, 0.0), 1.0)
    if all(cleaned.get(key) is None for key in TEXT_PREFS + NUMBER_PREFS):
        raise ValueError("profile needs at least one of: genre, mood, energy, valence")
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
