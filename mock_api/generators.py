"""
Deterministic fake data generators for the SoundFlow mock music streaming API.

Realistic patterns baked in:
  - More streams on weekends, fewer in summer, peak around Christmas
  - Evening-weighted listening hours (6 PM–10 PM peak)
  - 80/20 user distribution: top 20% of users → ~80% of streams (Zipf)
  - 80/20 artist distribution: top 20% of artists get more tracks AND
    popular tracks cluster on popular artists → ~80% of streams
"""

import bisect
import hashlib
import random
from datetime import date, datetime
from faker import Faker

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GENRES = [
    "Pop", "Rock", "Hip-Hop", "R&B", "Electronic", "Jazz", "Classical",
    "Country", "Latin", "Metal", "Folk", "Indie", "Blues", "Soul", "Reggae",
]
DEVICE_TYPES = ["mobile", "desktop", "tablet", "smart_speaker", "tv"]
PLATFORMS   = ["ios", "android", "web", "chromecast", "alexa"]
SUBSCRIPTION_TYPES = ["free", "premium", "family", "student"]
COUNTRIES = [
    "US", "GB", "DE", "FR", "BR", "MX", "JP", "KR", "IN", "AU",
    "CA", "ES", "IT", "NL", "SE", "NO", "PL", "AR", "CO", "ZA",
]

NUM_USERS   = 100
NUM_ARTISTS = 50
NUM_ALBUMS  = 200
NUM_TRACKS  = 1_000

BASE_EVENTS_PER_DAY = 5_000
BASE_SEED = 42


# ---------------------------------------------------------------------------
# Temporal pattern weights
# ---------------------------------------------------------------------------

# Hour weights (0–23): low overnight, morning commute, big evening peak
_HOUR_WEIGHTS = [
    3, 2, 1, 1, 1, 2,      # 00–05 overnight
    4, 6, 7, 6, 5, 5,      # 06–11 morning
    6, 6, 5, 5, 6, 8,      # 12–17 afternoon
    10, 12, 13, 12, 9, 6,  # 18–23 evening peak
]

# Day-of-week multipliers (Mon=0 … Sun=6)
_DOW_MULT = {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.05, 4: 1.15, 5: 1.35, 6: 1.25}

# Monthly multipliers: fall/winter heavy, summer light
_MONTH_MULT = {
    1: 1.05, 2: 0.95, 3: 0.90, 4: 0.88, 5: 0.85,
    6: 0.80, 7: 0.78, 8: 0.82, 9: 0.90, 10: 1.00,
    11: 1.08, 12: 1.15,
}

# Business launch date — user base growth is measured from here
LAUNCH_DATE = date(2025, 1, 1)

# Christmas / New Year boost: Dec 20 – Jan 5
def _is_holiday_period(d: date) -> bool:
    return (d.month == 12 and d.day >= 20) or (d.month == 1 and d.day <= 5)


def get_daily_event_count(d: date) -> int:
    """Return the number of stream events for a given date after applying all multipliers."""
    n = BASE_EVENTS_PER_DAY
    n *= _DOW_MULT[d.weekday()]
    n *= _MONTH_MULT[d.month]
    if _is_holiday_period(d):
        n *= 1.30
    # User base growth: starts at 30% of full volume at launch,
    # grows linearly to 100% over 18 months (~540 days)
    days_since_launch = max(0, (d - LAUNCH_DATE).days)
    growth = min(0.30 + 0.70 * days_since_launch / 540, 1.0)
    n *= growth
    return max(1, int(n))


# ---------------------------------------------------------------------------
# Zipf weighted selection helpers
# ---------------------------------------------------------------------------

def _build_cum_weights_zipf(n: int, alpha: float = 1.0) -> list:
    """
    Build a cumulative weight list using a Zipf (power-law) distribution.
    alpha=1.0 → top 20% of items capture ~80% of probability (Pareto-like).
    """
    weights = [1.0 / (i + 1) ** alpha for i in range(n)]
    total = sum(weights)
    cum, running = [], 0.0
    for w in weights:
        running += w / total
        cum.append(running)
    cum[-1] = 1.0  # guard against floating-point drift
    return cum


def _build_cum_weights_uniform(raw: list) -> list:
    """Build a cumulative weight list from a raw (unnormalised) weight list."""
    total = sum(raw)
    cum, running = [], 0.0
    for w in raw:
        running += w / total
        cum.append(running)
    cum[-1] = 1.0
    return cum


def _weighted_idx(rng: random.Random, cum_weights: list) -> int:
    """O(log n) weighted random index using pre-computed cumulative weights."""
    return min(bisect.bisect_left(cum_weights, rng.random()), len(cum_weights) - 1)


# ---------------------------------------------------------------------------
# Pre-compute popularity orders and cumulative weights at module load
# ---------------------------------------------------------------------------

# Shuffled popularity rankings — so "most popular" isn't always index 0
_user_pop_order: list = list(range(NUM_USERS))
random.Random(BASE_SEED + 100).shuffle(_user_pop_order)

_track_pop_order: list = list(range(NUM_TRACKS))
random.Random(BASE_SEED + 101).shuffle(_track_pop_order)

_artist_pop_order: list = list(range(NUM_ARTISTS))
random.Random(BASE_SEED + 102).shuffle(_artist_pop_order)

# Inverse lookups: item_index → popularity rank (O(1) vs O(n) .index())
_user_rank:   list = [0] * NUM_USERS
_track_rank:  list = [0] * NUM_TRACKS
_artist_rank: list = [0] * NUM_ARTISTS
for _rank, _idx in enumerate(_user_pop_order):
    _user_rank[_idx] = _rank + 1
for _rank, _idx in enumerate(_track_pop_order):
    _track_rank[_idx] = _rank + 1
for _rank, _idx in enumerate(_artist_pop_order):
    _artist_rank[_idx] = _rank + 1

# Zipf cumulative weights (alpha=1.0 ≈ 80/20)
_USER_CUM   = _build_cum_weights_zipf(NUM_USERS)
_TRACK_CUM  = _build_cum_weights_zipf(NUM_TRACKS)
_ARTIST_CUM = _build_cum_weights_zipf(NUM_ARTISTS)
_HOUR_CUM   = _build_cum_weights_uniform(_HOUR_WEIGHTS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stable_id(prefix: str, index: int) -> str:
    raw = f"{prefix}-{index}"
    h = hashlib.md5(raw.encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def _paginate(items: list, page: int, page_size: int, total: int) -> dict:
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "data": items[start:end],
        "page": page,
        "page_size": page_size,
        "total": total,
        "has_more": end < total,
    }


# ---------------------------------------------------------------------------
# Reference data — built ONCE at module load, cached in memory
# ---------------------------------------------------------------------------

def _build_artists() -> list:
    fake = Faker()
    Faker.seed(BASE_SEED)
    rng = random.Random(BASE_SEED)
    result = []
    for i in range(NUM_ARTISTS):
        result.append({
            "artist_id": _stable_id("artist", i),
            "name": fake.name(),
            "genre": rng.choice(GENRES),
            "country": rng.choice(COUNTRIES),
            "monthly_listeners": rng.randint(1_000, 10_000_000),
            "created_at": fake.date_between(start_date="-5y", end_date="-1y").isoformat(),
            # popularity_rank exposed so downstream analytics can validate 80/20
            "popularity_rank": _artist_rank[i],
        })
    return result


def _build_albums() -> list:
    fake = Faker()
    Faker.seed(BASE_SEED + 1)
    rng = random.Random(BASE_SEED + 1)
    result = []
    for i in range(NUM_ALBUMS):
        result.append({
            "album_id": _stable_id("album", i),
            "title": f"{fake.word().capitalize()} {fake.word().capitalize()}",
            "artist_id": _stable_id("artist", rng.randint(0, NUM_ARTISTS - 1)),
            "release_date": fake.date_between(start_date="-10y", end_date="today").isoformat(),
            "num_tracks": rng.randint(4, 18),
            "genre": rng.choice(GENRES),
        })
    return result


def _build_tracks() -> list:
    """
    Build tracks with artist assignment biased by artist popularity (Zipf).
    Popular artists (low popularity_rank) receive more tracks, which means
    they also capture more streams when track selection is Zipf-weighted.
    """
    fake = Faker()
    Faker.seed(BASE_SEED + 2)
    rng = random.Random(BASE_SEED + 2)
    result = []
    for i in range(NUM_TRACKS):
        # Assign artist using Zipf — popular artists get more tracks
        artist_rank = _weighted_idx(rng, _ARTIST_CUM)
        artist_index = _artist_pop_order[artist_rank]

        duration_ms = rng.randint(90_000, 420_000)
        result.append({
            "track_id": _stable_id("track", i),
            "title": f"{fake.word().capitalize()} {fake.word().capitalize()}",
            "artist_id": _stable_id("artist", artist_index),
            "album_id": _stable_id("album", rng.randint(0, NUM_ALBUMS - 1)),
            "duration_ms": duration_ms,
            "genre": rng.choice(GENRES),
            "release_year": rng.randint(2000, 2025),
            "explicit": rng.random() < 0.15,
            "tempo_bpm": rng.randint(60, 180),
            "energy_score": round(rng.uniform(0.1, 1.0), 3),
            "popularity_rank": _track_rank[i],
        })
    return result


def _build_users() -> list:
    fake = Faker()
    Faker.seed(BASE_SEED + 3)
    rng = random.Random(BASE_SEED + 3)
    result = []
    for i in range(NUM_USERS):
        result.append({
            "user_id": _stable_id("user", i),
            "username": fake.user_name(),
            "email": fake.email(),
            "country": rng.choice(COUNTRIES),
            "subscription_type": rng.choices(
                SUBSCRIPTION_TYPES, weights=[50, 30, 12, 8]
            )[0],
            "age_group": rng.choice(["13-17", "18-24", "25-34", "35-44", "45-54", "55+"]),
            "joined_at": fake.date_between(start_date=LAUNCH_DATE, end_date="-1d").isoformat(),
            "popularity_rank": _user_rank[i],
        })
    return result


print("Building reference data cache...")
_ARTISTS = _build_artists()
_ALBUMS  = _build_albums()
_TRACKS  = _build_tracks()
_USERS   = _build_users()
print(f"Cache ready: {len(_ARTISTS)} artists | {len(_ALBUMS)} albums | "
      f"{len(_TRACKS)} tracks | {len(_USERS)} users")


# ---------------------------------------------------------------------------
# Public API — instant slices from cache
# ---------------------------------------------------------------------------

def generate_artists(page: int, page_size: int) -> dict:
    return _paginate(_ARTISTS, page, page_size, NUM_ARTISTS)

def generate_albums(page: int, page_size: int) -> dict:
    return _paginate(_ALBUMS, page, page_size, NUM_ALBUMS)

def generate_tracks(page: int, page_size: int) -> dict:
    return _paginate(_TRACKS, page, page_size, NUM_TRACKS)

def generate_users(page: int, page_size: int) -> dict:
    return _paginate(_USERS, page, page_size, NUM_USERS)


# ---------------------------------------------------------------------------
# Event generator — patterns applied here
# ---------------------------------------------------------------------------

def generate_events(event_date: date, page: int, page_size: int) -> dict:
    """
    Generate stream events for a date with realistic patterns:
      - Total volume varies by weekday, month, and holiday period
      - Listening hour weighted toward evenings
      - User and track selection follow Zipf (80/20) distribution
    """
    date_seed = int(event_date.strftime("%Y%m%d"))
    total = get_daily_event_count(event_date)
    start = (page - 1) * page_size
    end = min(start + page_size, total)

    # Each page independently seeded → no need to replay prior pages
    rng = random.Random(date_seed + page * 9_999)

    events = []
    for idx in range(start, end):
        # ── Track & user (Zipf 80/20) ─────────────────────────────────────
        user_rank  = _weighted_idx(rng, _USER_CUM)
        user_index = _user_pop_order[user_rank]

        track_rank  = _weighted_idx(rng, _TRACK_CUM)
        track_index = _track_pop_order[track_rank]

        # ── Listening behaviour ──────────────────────────────────────────
        track_duration_ms = rng.randint(90_000, 420_000)
        listen_ratio = rng.betavariate(2, 1)   # skewed toward completion
        ms_played    = int(track_duration_ms * listen_ratio)

        # ── Evening-weighted timestamp ───────────────────────────────────
        hour   = _weighted_idx(rng, _HOUR_CUM)
        minute = rng.randint(0, 59)
        second = rng.randint(0, 59)
        started_at = datetime(
            event_date.year, event_date.month, event_date.day,
            hour, minute, second,
        )

        events.append({
            "event_id":          _stable_id(f"event-{event_date.isoformat()}", idx),
            "user_id":           _stable_id("user", user_index),
            "track_id":          _stable_id("track", track_index),
            "started_at":        started_at.isoformat(),
            "ms_played":         ms_played,
            "track_duration_ms": track_duration_ms,
            "completed":         ms_played >= track_duration_ms * 0.8,
            "skipped":           ms_played < track_duration_ms * 0.3,
            "device_type":       rng.choice(DEVICE_TYPES),
            "platform":          rng.choice(PLATFORMS),
            "shuffle_mode":      rng.random() < 0.4,
            "offline_mode":      rng.random() < 0.05,
        })

    return {
        "data":      events,
        "date":      event_date.isoformat(),
        "page":      page,
        "page_size": page_size,
        "total":     total,
        "has_more":  end < total,
    }
