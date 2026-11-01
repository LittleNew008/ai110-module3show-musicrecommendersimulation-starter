import csv
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
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

class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py
    """
    def __init__(self, songs: List[Song]):
        self.songs = songs

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        # TODO: Implement recommendation logic
        return self.songs[:k]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        # TODO: Implement explanation logic
        return "Explanation placeholder"

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

def score_song(user_prefs: Dict, song: Dict) -> Tuple[float, List[str]]:
    """Score one song against user preferences, returning (score, list of reasons)."""
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
    scored = [(song, *score_song(user_prefs, song)) for song in songs]

    def rank_key(item):
        song, score, _ = item
        energy_gap = abs(song["energy"] - user_prefs.get("energy", song["energy"]))
        return (-score, energy_gap, song["title"])

    ranked = sorted(scored, key=rank_key)
    return [(song, score, "; ".join(reasons)) for song, score, reasons in ranked[:k]]
