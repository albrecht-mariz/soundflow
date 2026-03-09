"""
Bulk backfill script — writes historical data directly to DuckDB,
bypassing the HTTP API and dlt overhead.

Uses numpy for vectorised event generation (~10-50x faster than pure Python).

Usage:
    python bulk_backfill.py --start-date 2024-01-01
    python bulk_backfill.py --start-date 2024-01-01 --end-date 2024-06-30
"""

import argparse
import os
import sys
import time
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import duckdb

_STREAM_COLS = [
    "event_id", "user_id", "track_id", "started_at", "ms_played",
    "track_duration_ms", "completed", "skipped", "device_type",
    "platform", "shuffle_mode", "offline_mode",
]

# Add mock_api to path so we can import generators directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "mock_api"))
from generators import (  # noqa: E402
    _ARTISTS, _ALBUMS, _TRACKS, _USERS,
    _user_pop_order, _track_pop_order,
    _USER_CUM, _TRACK_CUM, _HOUR_CUM,
    _stable_id,
    get_daily_event_count,
    DEVICE_TYPES, PLATFORMS,
    NUM_USERS, NUM_TRACKS,
)

DUCKDB_PATH = os.getenv("DUCKDB_PATH", "soundflow.duckdb")
BATCH_SIZE  = 20_000

# ---------------------------------------------------------------------------
# Pre-computed numpy arrays (built once at startup)
# ---------------------------------------------------------------------------

print("Building lookup arrays...")
_USER_CUM_NP  = np.array(_USER_CUM,  dtype=np.float64)
_TRACK_CUM_NP = np.array(_TRACK_CUM, dtype=np.float64)
_HOUR_CUM_NP  = np.array(_HOUR_CUM,  dtype=np.float64)
_USER_POP_NP  = np.array(_user_pop_order,  dtype=np.int32)
_TRACK_POP_NP = np.array(_track_pop_order, dtype=np.int32)

# Pre-compute all user_ids and track_ids (avoids md5 per event)
_USER_IDS  = [_stable_id("user",  i) for i in range(NUM_USERS)]
_TRACK_IDS = [_stable_id("track", i) for i in range(NUM_TRACKS)]

_DEVICE_ARR   = np.array(DEVICE_TYPES)
_PLATFORM_ARR = np.array(PLATFORMS)

print(f"  Ready: {NUM_USERS:,} users · {NUM_TRACKS:,} tracks\n")


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

DDL = """
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.artists (
    artist_id         VARCHAR PRIMARY KEY,
    name              VARCHAR,
    genre             VARCHAR,
    country           VARCHAR,
    monthly_listeners INTEGER,
    created_at        DATE,
    popularity_rank   INTEGER,
    _dlt_load_id      VARCHAR,
    _dlt_id           VARCHAR
);
CREATE TABLE IF NOT EXISTS raw.albums (
    album_id     VARCHAR PRIMARY KEY,
    title        VARCHAR,
    artist_id    VARCHAR,
    release_date DATE,
    num_tracks   INTEGER,
    genre        VARCHAR,
    _dlt_load_id VARCHAR,
    _dlt_id      VARCHAR
);
CREATE TABLE IF NOT EXISTS raw.tracks (
    track_id        VARCHAR PRIMARY KEY,
    title           VARCHAR,
    artist_id       VARCHAR,
    album_id        VARCHAR,
    duration_ms     INTEGER,
    genre           VARCHAR,
    release_year    INTEGER,
    explicit        BOOLEAN,
    tempo_bpm       INTEGER,
    energy_score    DOUBLE,
    popularity_rank INTEGER,
    _dlt_load_id    VARCHAR,
    _dlt_id         VARCHAR
);
CREATE TABLE IF NOT EXISTS raw.users (
    user_id           VARCHAR PRIMARY KEY,
    username          VARCHAR,
    email             VARCHAR,
    country           VARCHAR,
    subscription_type VARCHAR,
    age_group         VARCHAR,
    joined_at         DATE,
    popularity_rank   INTEGER,
    _dlt_load_id      VARCHAR,
    _dlt_id           VARCHAR
);
CREATE TABLE IF NOT EXISTS raw.stream_events (
    event_id          VARCHAR PRIMARY KEY,
    user_id           VARCHAR,
    track_id          VARCHAR,
    started_at        TIMESTAMP,
    ms_played         INTEGER,
    track_duration_ms INTEGER,
    completed         BOOLEAN,
    skipped           BOOLEAN,
    device_type       VARCHAR,
    platform          VARCHAR,
    shuffle_mode      BOOLEAN,
    offline_mode      BOOLEAN,
    _dlt_load_id      VARCHAR,
    _dlt_id           VARCHAR
);
"""


def setup_schema(con):
    for stmt in DDL.strip().split(";"):
        s = stmt.strip()
        if s:
            con.execute(s)


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

def load_reference_data(con):
    print("Loading reference data...")
    con.executemany(
        "INSERT OR REPLACE INTO raw.artists VALUES (?,?,?,?,?,?,?,?,?)",
        [(r["artist_id"], r["name"], r["genre"], r["country"],
          r["monthly_listeners"], r["created_at"], r["popularity_rank"], None, None)
         for r in _ARTISTS],
    )
    print(f"  artists : {len(_ARTISTS):,}")
    con.executemany(
        "INSERT OR REPLACE INTO raw.albums VALUES (?,?,?,?,?,?,?,?)",
        [(r["album_id"], r["title"], r["artist_id"], r["release_date"],
          r["num_tracks"], r["genre"], None, None)
         for r in _ALBUMS],
    )
    print(f"  albums  : {len(_ALBUMS):,}")
    con.executemany(
        "INSERT OR REPLACE INTO raw.tracks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [(r["track_id"], r["title"], r["artist_id"], r["album_id"],
          r["duration_ms"], r["genre"], r["release_year"], r["explicit"],
          r["tempo_bpm"], r["energy_score"], r["popularity_rank"], None, None)
         for r in _TRACKS],
    )
    print(f"  tracks  : {len(_TRACKS):,}")
    con.executemany(
        "INSERT OR REPLACE INTO raw.users VALUES (?,?,?,?,?,?,?,?,?,?)",
        [(r["user_id"], r["username"], r["email"], r["country"],
          r["subscription_type"], r["age_group"], r["joined_at"],
          r["popularity_rank"], None, None)
         for r in _USERS],
    )
    print(f"  users   : {len(_USERS):,}\n")


# ---------------------------------------------------------------------------
# Vectorised event generation (numpy)
# ---------------------------------------------------------------------------

def _events_for_date(event_date: date) -> list:
    """Generate all events for one day using numpy vectorised operations."""
    date_seed = int(event_date.strftime("%Y%m%d"))
    total     = get_daily_event_count(event_date)
    rng       = np.random.default_rng(date_seed)

    # ── Random draws (all at once) ─────────────────────────────────────────
    r_user     = rng.random(total)
    r_track    = rng.random(total)
    r_dur      = rng.integers(90_000, 420_001, total, dtype=np.int32)
    r_listen_a = rng.random(total)
    r_listen_b = rng.random(total)
    r_hour_r   = rng.random(total)
    r_minute   = rng.integers(0, 60, total, dtype=np.int32)
    r_second   = rng.integers(0, 60, total, dtype=np.int32)
    r_device   = rng.integers(0, len(DEVICE_TYPES), total, dtype=np.int8)
    r_platform = rng.integers(0, len(PLATFORMS),    total, dtype=np.int8)
    r_shuffle  = rng.random(total) < 0.4
    r_offline  = rng.random(total) < 0.05

    # ── Weighted selection (vectorised bisect) ─────────────────────────────
    user_ranks  = np.searchsorted(_USER_CUM_NP,  r_user).clip(0, NUM_USERS  - 1)
    track_ranks = np.searchsorted(_TRACK_CUM_NP, r_track).clip(0, NUM_TRACKS - 1)
    hours       = np.searchsorted(_HOUR_CUM_NP,  r_hour_r).clip(0, 23)

    user_indices  = _USER_POP_NP[user_ranks]
    track_indices = _TRACK_POP_NP[track_ranks]

    # ── Listen behaviour ───────────────────────────────────────────────────
    listen_ratio = np.maximum(r_listen_a, r_listen_b)   # ≡ betavariate(2,1)
    ms_played    = (r_dur * listen_ratio).astype(np.int32)
    completed    = ms_played >= (r_dur * 0.8).astype(np.int32)
    skipped      = ms_played <  (r_dur * 0.3).astype(np.int32)

    # ── Timestamps ─────────────────────────────────────────────────────────
    base = datetime(event_date.year, event_date.month, event_date.day)
    sec_offsets = hours.astype(np.int32) * 3600 + r_minute * 60 + r_second
    # Format timestamps without calling datetime per row
    timestamps = [
        (base + timedelta(seconds=int(s))).isoformat()
        for s in sec_offsets
    ]

    # ── IDs ────────────────────────────────────────────────────────────────
    date_str   = event_date.isoformat()
    event_ids  = [f"ev-{date_str}-{i}" for i in range(total)]
    user_ids   = [_USER_IDS[i]  for i in user_indices]
    track_ids  = [_TRACK_IDS[i] for i in track_indices]
    devices    = _DEVICE_ARR[r_device].tolist()
    platforms  = _PLATFORM_ARR[r_platform].tolist()

    return list(zip(
        event_ids, user_ids, track_ids, timestamps,
        ms_played.tolist(), r_dur.tolist(),
        completed.tolist(), skipped.tolist(),
        devices, platforms,
        r_shuffle.tolist(), r_offline.tolist(),
    ))


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------

def _fmt_eta(seconds: float) -> str:
    if seconds <= 0 or seconds > 86_400 * 7:
        return "--:--:--"
    return str(timedelta(seconds=int(seconds)))


def _print_progress(day_i: int, total_days: int, rows: int, t0: float):
    elapsed = time.perf_counter() - t0
    rate    = rows / elapsed if elapsed > 0 else 0
    pct     = day_i / total_days * 100
    secs_remaining = (total_days - day_i) * (elapsed / day_i) if day_i > 0 else 0
    print(
        f"  day {day_i:>4}/{total_days}"
        f"  |  {rows:>12,} rows"
        f"  |  {rate:>8,.0f} rows/s"
        f"  |  {pct:>5.1f}%"
        f"  |  ETA {_fmt_eta(secs_remaining)}",
        flush=True,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Bulk backfill SoundFlow DuckDB")
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date",   default=None,  help="YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--skip-reference", action="store_true",
                        help="Skip loading reference tables (use if already loaded)")
    return parser.parse_args()


def main():
    args  = parse_args()
    start = date.fromisoformat(args.start_date)
    end   = date.fromisoformat(args.end_date) if args.end_date \
            else date.today() - timedelta(days=1)

    if start > end:
        print("start-date must be before end-date.")
        sys.exit(1)

    total_days = (end - start).days + 1
    print(f"Bulk backfill : {start} → {end}  ({total_days} days, ~{total_days * 50_000:,} events est.)")
    print(f"DuckDB        : {DUCKDB_PATH}\n")

    con = duckdb.connect(DUCKDB_PATH)
    setup_schema(con)

    if not args.skip_reference:
        load_reference_data(con)

    # Rough estimate: benchmark one day first
    print("Benchmarking one day to estimate total time...")
    t_bench = time.perf_counter()
    _events_for_date(start)
    secs_per_day = time.perf_counter() - t_bench
    est_total = secs_per_day * total_days
    print(f"  ~{secs_per_day:.2f}s/day  →  estimated total: {_fmt_eta(est_total)}\n")

    print("Generating events...")
    t0, total_rows, buffer = time.perf_counter(), 0, []

    for day_i, d in enumerate(
        (start + timedelta(days=i) for i in range(total_days)), start=1
    ):
        buffer.extend(_events_for_date(d))
        _print_progress(day_i, total_days, total_rows + len(buffer), t0)

        if len(buffer) >= BATCH_SIZE or day_i == total_days:
            df = pd.DataFrame(buffer, columns=_STREAM_COLS)
            df["_dlt_load_id"] = None
            df["_dlt_id"] = None
            con.execute(
                "INSERT OR IGNORE INTO raw.stream_events SELECT * FROM df"
            )
            total_rows += len(df)
            buffer = []

    elapsed = time.perf_counter() - t0
    print(f"\n\nDone in {elapsed:.1f}s  —  {total_rows:,} events  "
          f"({total_rows / elapsed:,.0f} rows/s)\n")

    for tbl in ["artists", "albums", "tracks", "users", "stream_events"]:
        n = con.execute(f"SELECT count(*) FROM raw.{tbl}").fetchone()[0]
        print(f"  raw.{tbl}: {n:,}")

    con.close()
    print("\nNext step:  cd dbt_project && dbt run --profiles-dir .")


if __name__ == "__main__":
    main()
