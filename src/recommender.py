import csv
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field, asdict
import math
import numbers
import operator
import re

# Algorithm Recipe weights for the default (balanced) mode (base maximum score is 8.0)
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

# Diversity penalties (opt-in): points taken off a candidate for each song already picked
# with the same artist / the same genre. These are the sizes the CLI's --diverse flag uses.
ARTIST_PENALTY = 1.0
GENRE_PENALTY = 0.5

@dataclass(frozen=True)
class ScoringMode:
    """A named set of weights for the four base terms; each mode's base maximum is the sum of its weights."""
    name: str
    description: str
    energy_weight: float
    mood_weight: float
    valence_weight: float
    genre_weight: float
    energy_sigma: float = ENERGY_SIGMA
    partial_mood_credit: float = PARTIAL_MOOD_CREDIT

    def __post_init__(self):
        weights = (self.energy_weight, self.mood_weight, self.valence_weight, self.genre_weight)
        if not all(math.isfinite(w) and w >= 0 for w in weights):
            raise ValueError(f"mode {self.name!r}: weights must be finite numbers >= 0, got {weights}")
        if not (math.isfinite(self.energy_sigma) and self.energy_sigma > 0):
            raise ValueError(f"mode {self.name!r}: energy_sigma must be a finite number > 0, got {self.energy_sigma!r}")
        if not 0 <= self.partial_mood_credit <= 1:
            raise ValueError(f"mode {self.name!r}: partial_mood_credit must be between 0 and 1, got {self.partial_mood_credit!r}")

    @property
    def max_score(self) -> float:
        """Highest base score a song can earn in this mode (extension terms are extra)."""
        return self.energy_weight + self.mood_weight + self.valence_weight + self.genre_weight

# Scoring modes: add a new mode by adding one entry here. Every mode's weights sum to 8.0,
# so base scores stay on the same scale. "balanced" is the default and uses the constants above.
DEFAULT_MODE = "balanced"
MODES: Dict[str, ScoringMode] = {
    mode.name: mode
    for mode in (
        ScoringMode("balanced", "Standard recipe: energy first, then mood, valence and genre.",
                    ENERGY_WEIGHT, MOOD_WEIGHT, VALENCE_WEIGHT, GENRE_WEIGHT),
        ScoringMode("genre-first", "The genre label dominates, with energy and mood in supporting roles.",
                    energy_weight=2.0, mood_weight=1.5, valence_weight=0.5, genre_weight=4.0),
        ScoringMode("mood-first", "The mood label dominates, with energy as the second voice.",
                    energy_weight=2.0, mood_weight=4.0, valence_weight=1.0, genre_weight=1.0),
        ScoringMode("energy-focused", "Energy closeness is almost the whole score.",
                    energy_weight=5.5, mood_weight=1.0, valence_weight=1.0, genre_weight=0.5),
    )
}

def resolve_mode(mode=None) -> ScoringMode:
    """Turn None, a mode name or a ScoringMode into a ScoringMode; raise ValueError for an unknown name."""
    if mode is None:
        return MODES[DEFAULT_MODE]
    if isinstance(mode, ScoringMode):
        return mode
    name = str(mode).strip().lower()
    if name not in MODES:
        raise ValueError(f"unknown mode {mode!r}. Valid modes: {', '.join(MODES)}")
    return MODES[name]

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
    def __init__(self, songs: List[Song], mode=None, artist_penalty: float = 0.0, genre_penalty: float = 0.0):
        self.songs = songs
        self.mode = resolve_mode(mode)
        self.artist_penalty = check_penalty("artist_penalty", artist_penalty)
        self.genre_penalty = check_penalty("genre_penalty", genre_penalty)

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
        ranked = recommend_songs(self._prefs(user), rows, k, self.mode, self.artist_penalty, self.genre_penalty)
        return [by_id[row["id"]] for row, _, _ in ranked]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        """Explain why a song fits the user, reusing the reasons from score_song."""
        _, reasons = score_song(self._prefs(user), asdict(song), self.mode)
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

def score_song(user_prefs: Dict, song: Dict, mode=None) -> Tuple[float, List[str]]:
    """Score one song against user preferences, returning (score, list of reasons)."""
    mode = resolve_mode(mode)
    user_prefs = clean_prefs(user_prefs)
    score = 0.0
    reasons: List[str] = []

    target_energy = user_prefs.get("energy")
    if target_energy is not None:
        gap = abs(song["energy"] - target_energy)
        points = mode.energy_weight * math.exp(-(gap ** 2) / (2 * mode.energy_sigma ** 2))
        score += points
        reasons.append(
            f"energy {song['energy']:.2f} vs target {target_energy:.2f} (+{points:.2f})"
        )

    user_mood = user_prefs.get("mood")
    if user_mood is not None:
        if song["mood"] == user_mood:
            score += mode.mood_weight
            reasons.append(f"mood match: {song['mood']} (+{mode.mood_weight:.2f})")
        elif any(user_mood in c and song["mood"] in c for c in MOOD_CLUSTERS):
            points = mode.mood_weight * mode.partial_mood_credit
            score += points
            reasons.append(
                f"similar mood: {song['mood']} is close to {user_mood} (+{points:.2f})"
            )

    target_valence = user_prefs.get("valence")
    if target_valence is not None:
        points = mode.valence_weight * (1 - abs(song["valence"] - target_valence))
        score += points
        reasons.append(
            f"valence {song['valence']:.2f} vs target {target_valence:.2f} (+{points:.2f})"
        )

    if song["genre"] == user_prefs.get("genre"):
        score += mode.genre_weight
        reasons.append(f"genre match: {song['genre']} (+{mode.genre_weight:.2f})")

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

def check_penalty(name: str, value) -> float:
    """Return a diversity penalty as a float; raise ValueError unless it is a finite number >= 0."""
    ok = not isinstance(value, bool) and isinstance(value, numbers.Real)
    if ok:
        try:
            ok = math.isfinite(value) and value >= 0
        except OverflowError:  # an int too large for a float
            ok = False
    if not ok:
        raise ValueError(f"{name} must be a finite number >= 0, got {value!r}")
    return float(value)

def check_k(k) -> int:
    """Return k as an int (negative counts as 0); raise ValueError unless it is a whole number."""
    try:
        if isinstance(k, bool):
            raise TypeError
        k = operator.index(k)
    except TypeError:
        raise ValueError(f"k must be a whole number, got {k!r}") from None
    return max(k, 0)

def pick_diverse(scored: List[Tuple[Dict, float, List[str]]], k: int, target_energy: Optional[float],
                 artist_penalty: float, genre_penalty: float) -> List[Tuple[Dict, float, List[str]]]:
    """Greedily pick k songs, charging each candidate for same-artist and same-genre songs already picked."""
    remaining = list(scored)
    picked: List[Tuple[Dict, float, List[str]]] = []
    while remaining and len(picked) < k:
        best = None
        for index, (song, score, reasons) in enumerate(remaining):
            # A missing (None) artist or genre never counts as a repeat
            artist, genre = song.get("artist"), song.get("genre")
            n_artist = 0 if artist is None else sum(p.get("artist") == artist for p, _, _ in picked)
            n_genre = 0 if genre is None else sum(p.get("genre") == genre for p, _, _ in picked)
            adjusted = score - artist_penalty * n_artist - genre_penalty * n_genre
            energy_gap = 0.0 if target_energy is None else abs(song["energy"] - target_energy)
            key = (-adjusted, energy_gap, song["title"])
            if best is None or key < best[0]:
                best = (key, index, adjusted, n_artist, n_genre)
        _, index, adjusted, n_artist, n_genre = best
        song, _, reasons = remaining.pop(index)
        extra = []
        if artist_penalty > 0 and n_artist:
            extra += [f"diversity penalty: artist {song['artist']} already recommended (-{artist_penalty:.2f})"] * n_artist
        if genre_penalty > 0 and n_genre:
            extra += [f"diversity penalty: genre {song['genre']} already recommended (-{genre_penalty:.2f})"] * n_genre
        picked.append((song, adjusted, reasons + extra))
    return picked

def recommend_songs(user_prefs: Dict, songs: List[Dict], k: int = 5, mode=None,
                    artist_penalty: float = 0.0, genre_penalty: float = 0.0) -> List[Tuple[Dict, float, str]]:
    """Score every song and return the top k as (song, score, explanation), best first.

    With a nonzero artist_penalty or genre_penalty the list is built greedily and each pick's score
    is its adjusted score (see pick_diverse); with both at 0 the plain ranking is returned.
    k must be a whole number; a k of 0 or less returns an empty list.
    """
    mode = resolve_mode(mode)
    artist_penalty = check_penalty("artist_penalty", artist_penalty)
    genre_penalty = check_penalty("genre_penalty", genre_penalty)
    k = check_k(k)
    prefs = clean_prefs(user_prefs)
    scored = [(song, *score_song(prefs, song, mode)) for song in songs]
    target_energy = prefs.get("energy")

    if artist_penalty > 0 or genre_penalty > 0:
        picked = pick_diverse(scored, k, target_energy, artist_penalty, genre_penalty)
        return [(song, score, "; ".join(reasons)) for song, score, reasons in picked]

    def rank_key(item):
        song, score, _ = item
        energy_gap = 0.0 if target_energy is None else abs(song["energy"] - target_energy)
        return (-score, energy_gap, song["title"])

    ranked = sorted(scored, key=rank_key)
    return [(song, score, "; ".join(reasons)) for song, score, reasons in ranked[:k]]
