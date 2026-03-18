# SoundFlow Data Pipeline

An end-to-end batch data pipeline that simulates a music streaming service, with an agentic BI layer built on Lightdash and Slack.

## Stack

| Layer | Tool | Role |
|---|---|---|
| Mock Data | FastAPI + Faker | Simulates a music streaming app's REST API |
| Ingestion | dlt | Loads raw data into DuckDB (incremental) |
| Storage | DuckDB | Analytical database (file-based) |
| Transformation | dbt | Staging → Intermediate → Marts |
| Orchestration | GitHub Actions | Daily cron, artifact persistence |
| BI | Lightdash (self-hosted) | Dashboards on top of dbt mart models |
| Slack Agent | Slack Bolt + Claude API | Answers KPI questions and builds dashboards from Slack |
| Development | Claude Code | AI-assisted development (Anthropic) |

## Architecture

```
┌──────────────────────────┐
│   bulk_backfill.py       │  One-time historical load (months of data)
│                          │  Same deterministic seed as mock API
│                          │  Writes direct to DuckDB (no HTTP overhead)
└────────────┬─────────────┘
             │ direct write
             ▼
┌──────────────────────────┐
│   SoundFlow Mock API     │  FastAPI · deterministic daily data
│   (FastAPI + Faker)      │  100 users · 1K tracks · ~4K–8.5K events/day
└────────────┬─────────────┘
             │ HTTP (REST)
             ▼
┌──────────────────────────┐
│   dlt Pipeline           │  Daily incremental load (events by date)
│   (Python)               │  Replace (reference data) · Merge (events)
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
│                          │  staging/      → typed, renamed
│                          │  intermediate/ → joined enriched events
│                          │  marts/        → analytics-ready tables
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│   DuckDB · marts schema  │  daily_listening_stats
│                          │  top_tracks_daily
│                          │  user_activity
│                          │  genre_trends
└────────────┬─────────────┘
             │
             ├──────────────────────────────────────────┐
             ▼                                          ▼
┌──────────────────────────┐            ┌──────────────────────────────┐
│   Lightdash (port 8090)  │            │   Slack BI Agent             │
│   Self-hosted BI         │            │   (slack_bot.py)             │
│                          │            │                              │
│   · Platform Overview    │◄───────────│   · Answers KPI questions    │
│   · Top Tracks           │  dashboard │     in Slack (Phase 4)       │
│   · Genre Trends         │  links     │   · Finds existing dashboard │
│   · User Segments        │            │     or builds a new one      │
└──────────────────────────┘            │     (Phase 3)                │
             ▲                          │   · Builds dashboards from   │
             │                          │     a prompt (Phase 2)       │
             │ Claude API               └──────────────────────────────┘
             │ Lightdash REST API
             │
GitHub Actions (daily 06:00 UTC)
  · Downloads previous DuckDB artifact
  · Merges new day's events via dlt (deduplicates on event_id)
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
| **Daily active user pool** | Only a realistic subset of users (~50–80) is active each day. Popular users have higher activation probability; quiet days (summer Mondays) have fewer active users than busy days (Christmas Saturdays) |

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

### 2. Backfill historical data

Load months of historical data directly into DuckDB — this bypasses the API for speed and is the right starting point before running the daily pipeline:

```bash
make backfill START_DATE=2025-01-01
# or with an explicit end date:
python bulk_backfill.py --start-date 2025-01-01 --end-date 2025-12-31
```

The backfill generates data using the same deterministic seed as the mock API, so it's fully compatible with subsequent dlt runs.

> **Note**: The backfill writes reference data (artists, albums, tracks, users) and events directly into `raw` — including `_dlt_load_id` and `_dlt_id` columns — so subsequent dlt pipeline runs append cleanly on top.

### 3. Start the mock API

```bash
make api
# API running at http://localhost:8000
# Interactive docs: http://localhost:8000/docs
```

### 4. Run the pipeline (yesterday's data)

Once the API is running, append the most recent day:

```bash
make pipeline
```

### 5. Run dbt transformations

```bash
make dbt
make dbt-test
```

### 6. Or run everything with Docker Compose

```bash
make docker-up
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

The docs include an interactive lineage graph (DAG) showing the full source → staging → intermediate → marts dependency chain. They are also published automatically to GitHub Pages on every push to `main`:

**[albrecht-mariz.github.io/soundflow-pipeline](https://albrecht-mariz.github.io/soundflow-pipeline)**

## Agentic BI Layer

A four-phase agentic BI layer sits on top of the dbt marts: self-hosted Lightdash dashboards (Phase 1), a Claude-powered prompt-to-dashboard CLI (Phase 2), a Slack bot that finds or builds dashboards on request with human approval (Phase 3), and a fully in-Slack data answering experience with charts rendered directly in the thread (Phase 4).

### Phase 1 — Lightdash Dashboards

Self-hosted Lightdash connected directly to the DuckDB file. All four mart models are configured as Lightdash explores with full metric and dimension YAML blocks.

> **Important**: DuckDB supports only one writer at a time. Stop the pipeline before starting Lightdash, and vice versa.

```bash
# Run the pipeline first to populate DuckDB
make backfill START_DATE=2025-01-01
make dbt

# Start Lightdash (do NOT run pipeline simultaneously)
docker-compose up lightdash-db lightdash
# Opens at http://localhost:8090
```

On first launch: create an admin account → connect the dbt project (mounted at `/usr/app/dbt`) → the four explores (Daily Listening Stats, Top Tracks Daily, Genre Trends, User Activity) will appear automatically.

| Dashboard | Mart | Key tiles |
|---|---|---|
| Platform Overview | `daily_listening_stats` | Total streams over time, active users, completion vs skip rate, platform & subscription splits |
| Top Tracks | `top_tracks_daily` | Ranked table: track / artist / streams / completion rate |
| Genre Trends | `genre_trends` | Stream share over time (stacked area), genre rank table |
| User Segments | `user_activity` | Subscription breakdown, top listeners, preferred platform |

Once dashboards are built, fill in the `url:` fields in `dbt_project/models/marts/exposures.yml` — these URLs are used by the Slack agent for dashboard lookup.

### Phase 2 — Prompt-to-Dashboard CLI

Claude reads the available metrics from `schema.yml` and generates a Lightdash dashboard definition from a natural-language prompt. The dashboard is created as a draft in the "Draft — Pending Review" space for human review before publishing.

```bash
pip install -r bi_agent/requirements.txt
cp .env.example .env  # fill in ANTHROPIC_API_KEY + LIGHTDASH_*

python -m bi_agent.prompt_to_dashboard "show me weekly streams by genre last 90 days"
# → creates draft dashboard, prints URL for review in Lightdash
```

Or in Claude Code:

```
/build-dashboard top 10 artists this week by completion rate
```

The `/build-dashboard` command invokes the `lightdash-agent` subagent (`.claude/agents/lightdash-agent.md`), which plans the dashboard tiles and waits for your approval before calling the Lightdash API.

### Phase 3 — Slack Agent (Find or Build)

Users ask KPI questions in Slack. The bot either returns a link to an existing dashboard or builds a new draft and sends it for approval via Block Kit buttons.

```
@SoundFlow show me genre trends for the last month
→ Found: Here's the dashboard: http://localhost:8090/...

@SoundFlow how are student subscribers doing vs premium?
→ No existing dashboard. Building a draft... [Approve] [Reject]
```

Flow:
1. Claude Haiku extracts a structured intent (`kpi`, `breakdown`, `timeframe`) from the message.
2. Bot searches `exposures.yml` + Lightdash API for a matching dashboard.
3. If found → reply with link. If not → generate draft with Claude Opus → post approval buttons.
4. On Approve: dashboard is moved to "Published" space. On Reject: draft is discarded.

Approval is gated to `REVIEWER_SLACK_USER_ID` (set in `.env`).

### Phase 4 — Full In-Slack Answers

For direct data questions (not dashboard requests), the bot queries DuckDB and replies in-thread with text, a Slack table, or a chart image — no browser needed.

```
@SoundFlow how many streams last week?
→ 📊 [line chart image] Total: 34,210 streams over 7 days.

@SoundFlow top 10 tracks this month?
→ [formatted table in thread]

@SoundFlow what's our completion rate?
→ 🎧 Engagement — last 30 days
   • Avg completion rate: 67.3%
   • Avg skip rate: 18.1%
```

Supported KPIs: streams, active users, completion rate, skip rate, listening hours, genre trends, top tracks, top artists, user activity, subscription breakdown, platform breakdown.

### Running the Slack Bot

```bash
# 1. Create a Slack app at api.slack.com/apps
#    Enable: Socket Mode, Event Subscriptions (app_mention + message.im), Interactivity
#    Copy tokens to .env

# 2. Start Lightdash + the bot
docker-compose up lightdash-db lightdash slack-bot
```

Required environment variables (see `.env.example`):

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `SLACK_BOT_TOKEN` | `xoxb-...` from Slack app OAuth settings |
| `SLACK_APP_TOKEN` | `xapp-...` Socket Mode app-level token |
| `SLACK_SIGNING_SECRET` | From Slack app Basic Information |
| `LIGHTDASH_BASE_URL` | `http://localhost:8090` |
| `LIGHTDASH_TOKEN` | Personal access token from Lightdash Settings |
| `LIGHTDASH_PROJECT_UUID` | UUID from the Lightdash project URL |
| `REVIEWER_SLACK_USER_ID` | Slack user ID allowed to approve new dashboards |
| `DUCKDB_PATH` | Path to `soundflow.duckdb` (default: `soundflow.duckdb`) |

## GitHub Actions

Two workflows are included:

| Workflow | Trigger | Purpose |
|---|---|---|
| `daily_pipeline.yml` | Daily 06:00 UTC + manual | Full pipeline run with DuckDB artifact persistence |
| `ci.yml` | Push/PR to main | Lint (ruff + sqlfluff), smoke tests, 3-day pipeline run, dbt tests, publish dbt docs to GitHub Pages |

### Artifact Persistence

The DuckDB file is persisted across daily runs as a GitHub Actions artifact (`soundflow-duckdb`). Each run:
1. Downloads the previous DuckDB artifact
2. Merges the new day's events (incremental via dlt, deduplicates on event_id)
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
│   │   │   ├── sources.yml
│   │   │   ├── schema.yml
│   │   │   └── stg_*.sql
│   │   ├── intermediate/   # Joined enriched events
│   │   │   ├── schema.yml
│   │   │   └── int_enriched_events.sql
│   │   └── marts/          # Analytics-ready tables
│   │       ├── schema.yml  # Lightdash meta: blocks (metrics + dimensions)
│   │       ├── exposures.yml
│   │       └── *.sql
│   ├── tests/              # Custom singular tests
│   │   ├── assert_completion_rate_valid.sql
│   │   ├── assert_skip_rate_valid.sql
│   │   ├── assert_top_tracks_rank_range.sql
│   │   └── assert_genre_pct_sums_to_100.sql
│   ├── macros/
│   │   └── generate_schema_name.sql
│   ├── dbt_project.yml
│   ├── profiles.yml
│   ├── packages.yml
│   └── requirements.txt
├── bi_agent/               # Agentic BI layer (Phases 2–4)
│   ├── metrics_context.py  # Reads schema.yml meta blocks → agent context
│   ├── lightdash_client.py # Lightdash REST API wrapper
│   ├── prompt_to_dashboard.py  # Phase 2: prompt → draft dashboard
│   ├── intent.py           # Phase 3: Claude Haiku intent classifier
│   ├── dashboard_lookup.py # Phase 3: search exposures.yml + Lightdash API
│   ├── slack_bot.py        # Phase 3+4: Slack Bolt app
│   ├── answer.py           # Phase 4: DuckDB query router + Slack formatter
│   ├── chart.py            # Phase 4: Matplotlib PNG renderer
│   ├── Dockerfile
│   └── requirements.txt
├── .claude/                # Claude Code configuration
│   ├── agents/
│   │   └── lightdash-agent.md  # Subagent for dashboard creation
│   ├── commands/
│   │   ├── run-pipeline.md     # /run-pipeline slash command
│   │   ├── dbt-check.md        # /dbt-check slash command
│   │   └── build-dashboard.md  # /build-dashboard slash command
│   └── skills/
│       └── bi-roadmap/
│           └── SKILL.md        # Auto-discoverable BI roadmap skill
├── .github/
│   └── workflows/
│       ├── daily_pipeline.yml
│       └── ci.yml
├── docker-compose.yml      # pipeline + dbt + Lightdash + Slack bot
├── Makefile
├── .env.example            # Required environment variables
├── CLAUDE.md               # Claude Code instructions
├── bulk_backfill.py        # Fast historical backfill
├── validate_patterns.py    # Validates simulated data patterns
└── README.md
```

## Key Design Decisions

- **Deterministic data**: All mock data is seeded — same inputs, same outputs. This makes the pipeline idempotent and testable.
- **Incremental loading**: Stream events are loaded daily using `write_disposition="merge"` with `event_id` as the primary key — making the pipeline fully idempotent. Re-running for the same date range is safe; existing events are updated, not duplicated. Reference data (artists, albums, tracks, users) is replaced on each run (`write_disposition="replace"`).
- **DuckDB as artifact**: No cloud infrastructure needed. The DuckDB file travels between GitHub Actions runs as an artifact, accumulating data over time.
- **dbt layers**: Staging (clean), Intermediate (joined), Marts (aggregated) — standard dbt layering pattern.
- **No secrets required**: The entire pipeline runs without API keys or cloud credentials.
- **Vectorised event generation**: `bulk_backfill.py` uses NumPy for all random draws (user/track selection, timestamps, listen ratios) in batch rather than per-event Python loops — ~10–50× faster than the equivalent pure-Python approach.
- **dbt singular tests**: Custom SQL assertion tests (in `dbt_project/tests/`) validate business logic — e.g. completion rates must be 0–100%, daily rank must be 1–100. These complement dbt's built-in schema tests (`not_null`, `unique`, `accepted_values`).
- **dbt_utils package**: Uses `dbt-labs/dbt_utils` for utility macros (e.g. `generate_surrogate_key`).
- **Dev/prod schema separation**: Two dbt targets in `profiles.yml` (`dev` and `prod`) write to different DuckDB schemas. In `prod`, models land in `raw`/`staging`/`marts`. In `dev`, they land in `dev_raw`/`dev_staging`/`dev_marts` — so local development never pollutes the production dataset. The `generate_schema_name.sql` macro enforces this via `target.name`.
- **Linting in CI**: Python files are linted with `ruff` (fast, replaces flake8/isort); SQL models and tests are linted with `sqlfluff` using the DuckDB dialect and Jinja templater.
- **Self-hosted Lightdash**: Lightdash Cloud cannot connect to a local DuckDB file — the self-hosted open-source edition is used instead, running via Docker with the DuckDB file mounted read-only.
- **Semantic layer via Lightdash explores**: Metrics and dimensions are defined once in `schema.yml` `meta:` blocks. Every consumer — the Lightdash UI, the prompt-to-dashboard CLI, and the Slack agent — reads from the same definitions, preventing metric inconsistency.
- **Human-in-the-loop approval**: New dashboards created by the agent always land in a "Draft — Pending Review" space. A designated reviewer must approve before they are published, preventing unreviewed dashboards from reaching users.
- **Parameterised DuckDB queries**: All queries in `bi_agent/answer.py` use DuckDB parameter binding — no string interpolation into SQL, preventing injection.
