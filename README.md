# SoundFlow Data Pipeline

An end-to-end batch data pipeline that simulates a music streaming service. Built for educational and portfolio purposes.

## Stack

| Layer | Tool | Role |
|---|---|---|
| Mock Data | FastAPI + Faker | Simulates a music streaming app's REST API |
| Ingestion | dlt | Loads raw data into DuckDB (incremental) |
| Storage | DuckDB | Analytical database (file-based) |
| Transformation | dbt | Staging → Intermediate → Marts |
| Orchestration | GitHub Actions | Daily cron, artifact persistence |

## Architecture

```
┌──────────────────────────┐
│   SoundFlow Mock API     │  FastAPI · deterministic daily data
│   (FastAPI + Faker)      │  100 users · 1K tracks · ~4K–8.5K events/day
└────────────┬─────────────┘
             │ HTTP (REST)
             ▼
┌──────────────────────────┐
│   dlt Pipeline           │  Incremental load (events by date)
│   (Python)               │  Merge upsert (users, tracks, artists)
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│   DuckDB · raw schema    │  stream_events, users, tracks,
│                          │  artists, albums
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│   dbt Transformations    │
│                          │  staging/    → typed, renamed
│                          │  intermediate/ → joined enriched events
│                          │  marts/      → analytics-ready tables
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│   DuckDB · marts schema  │  daily_listening_stats
│                          │  top_tracks_daily
│                          │  user_activity
│                          │  genre_trends
└──────────────────────────┘
             ▲
GitHub Actions (daily 06:00 UTC)
  · Downloads previous DuckDB artifact
  · Appends new day's events
  · Runs dbt models + tests
  · Uploads updated DuckDB artifact
```

## Data Model

### Mock API Endpoints

| Endpoint | Description |
|---|---|
| `GET /health` | Health check |
| `GET /artists?page=1&page_size=100` | Artist catalog (50 artists) |
| `GET /albums?page=1&page_size=100` | Album catalog (200 albums) |
| `GET /tracks?page=1&page_size=100` | Track catalog (1K tracks) |
| `GET /users?page=1&page_size=100` | User accounts (100 users) |
| `GET /events?date=YYYY-MM-DD` | Stream events for a given date (~5K/day, varies by patterns below) |

All reference data (artists, albums, tracks, users) is seeded deterministically — the same data is always returned. Events are seeded by date — the same date always returns the same events, making the pipeline idempotent.

### Simulated Data Patterns

The mock API generates data with realistic behavioural patterns built in:

| Pattern | Detail |
|---|---|
| **Weekend boost** | Saturday ×1.35, Sunday ×1.25 vs Monday–Wednesday ×1.00 |
| **Evening peak** | Hour 20 (8 PM) has 13× more streams than hour 3 (3 AM); commute hours (7–9 AM, 5–6 PM) also elevated |
| **Seasonal variation** | July is the quietest month (×0.78); November–December ramp up (×1.08–1.15) |
| **Christmas / New Year** | Dec 20 – Jan 5 gets an additional ×1.30 boost on top of seasonal multiplier |
| **User 80/20** | Top 20% of users generate ~80% of streams (Zipf distribution, α=1.0) |
| **Track 80/20** | Top 20% of tracks capture ~80% of streams (Zipf distribution, α=1.0) |
| **Artist 80/20** | Popular artists attract more tracks during catalog generation, so they also capture a disproportionate share of streams |
| **User growth** | Event volume starts at 30% on Jan 1 2025 and grows linearly to 100% over 18 months, simulating an expanding user base |

These patterns can be verified after a pipeline run:

```bash
python validate_patterns.py
```

### dbt Marts

| Table | Grain | Description |
|---|---|---|
| `daily_listening_stats` | 1 row/day | Platform-wide engagement metrics |
| `top_tracks_daily` | 1 row/track/day | Top 100 tracks by stream count |
| `user_activity` | 1 row/user | All-time listening summary per user |
| `genre_trends` | 1 row/genre/day | Genre popularity with share of streams |

## Quick Start

### Prerequisites
- Python 3.12+
- Docker + Docker Compose (for full stack)
- `make` (optional but convenient)

### 1. Install dependencies

```bash
make setup
```

### 2. Start the mock API

```bash
make api
# API running at http://localhost:8000
# Interactive docs: http://localhost:8000/docs
```

### 3. Run the pipeline (yesterday's data)

```bash
make pipeline
```

### 4. Run dbt transformations

```bash
make dbt
make dbt-test
```

### 5. Or run everything with Docker Compose

```bash
make docker-up
```

### 6. Backfill historical data (e.g. last 30 days)

```bash
make backfill START_DATE=2025-01-01
```

### 7. Explore the data

```bash
# Open DuckDB CLI
duckdb soundflow.duckdb

# Sample queries:
SELECT * FROM marts.daily_listening_stats ORDER BY event_date DESC LIMIT 7;
SELECT * FROM marts.top_tracks_daily WHERE event_date = current_date - 1 LIMIT 10;
SELECT * FROM marts.genre_trends WHERE event_date = current_date - 1 ORDER BY daily_rank;
```

### 8. dbt docs

```bash
make dbt-docs
# Opens browser at http://localhost:8080
```

## GitHub Actions

Two workflows are included:

| Workflow | Trigger | Purpose |
|---|---|---|
| `daily_pipeline.yml` | Daily 06:00 UTC + manual | Full pipeline run with DuckDB artifact persistence |
| `ci.yml` | Push/PR to main | Smoke tests, 3-day pipeline run, dbt tests |

### Artifact Persistence

The DuckDB file is persisted across daily runs as a GitHub Actions artifact (`soundflow-duckdb`). Each run:
1. Downloads the previous DuckDB artifact
2. Appends the new day's events (incremental via dlt)
3. Rebuilds dbt mart tables
4. Uploads the updated DuckDB as a new artifact (90-day retention)

### Manual Backfill via workflow_dispatch

Trigger the `daily_pipeline.yml` workflow manually with a `start_date` parameter to backfill historical data.

## Project Structure

```
soundflow-pipeline/
├── mock_api/               # FastAPI mock server
│   ├── app.py              # API routes
│   ├── generators.py       # Deterministic Faker-based data generators
│   ├── Dockerfile
│   └── requirements.txt
├── pipeline/               # dlt ingestion pipeline
│   ├── sources/
│   │   └── music_app.py    # dlt source (REST client + resources)
│   ├── pipeline.py         # Entry point
│   ├── config.toml         # dlt config
│   ├── Dockerfile
│   └── requirements.txt
├── dbt_project/            # dbt transformation project
│   ├── models/
│   │   ├── staging/        # Typed/renamed raw sources
│   │   ├── intermediate/   # Joined enriched events
│   │   └── marts/          # Analytics-ready tables
│   ├── dbt_project.yml
│   ├── profiles.yml
│   ├── packages.yml
│   └── requirements.txt
├── .github/
│   └── workflows/
│       ├── daily_pipeline.yml
│       └── ci.yml
├── docker-compose.yml
├── Makefile
├── validate_patterns.py    # validates simulated data patterns against DuckDB
└── README.md
```

## Key Design Decisions

- **Deterministic data**: All mock data is seeded — same inputs, same outputs. This makes the pipeline idempotent and testable.
- **Incremental loading**: Stream events are appended daily using dlt's incremental cursor on `started_at`. Reference data (users, tracks, artists) uses merge/upsert.
- **DuckDB as artifact**: No cloud infrastructure needed. The DuckDB file travels between GitHub Actions runs as an artifact, accumulating data over time.
- **dbt layers**: Staging (clean), Intermediate (joined), Marts (aggregated) — standard dbt layering pattern.
- **No secrets required**: The entire pipeline runs without API keys or cloud credentials.
