# CLAUDE.md — SoundFlow Pipeline

Project instructions for Claude Code. Read this first before making changes.

---

## Project Overview

End-to-end batch data pipeline simulating a music streaming service. Covers ingestion (dlt), storage (DuckDB), transformation (dbt), and orchestration (GitHub Actions). The next layer being built is **agentic BI** using Lightdash + Slack. For the full BI roadmap invoke `/bi-roadmap` or see [`.claude/skills/bi-roadmap/SKILL.md`](.claude/skills/bi-roadmap/SKILL.md).

---

## Stack

| Layer | Tool |
|---|---|
| Mock Data | FastAPI + Faker |
| Ingestion | dlt (DuckDB, incremental) |
| Storage | DuckDB (file-based) |
| Transformation | dbt (staging → intermediate → marts) |
| Orchestration | GitHub Actions |
| BI | Lightdash (next step) |
| Agent | Claude API / Slack Bolt (planned) |

---

## Common Commands

```bash
# Setup
make setup

# Historical backfill
make backfill START_DATE=2025-01-01

# Start mock API
make api                          # http://localhost:8000

# Run daily pipeline (requires API running)
make pipeline

# dbt
make dbt                          # run all models
make dbt-test                     # run all tests
make dbt-docs                     # build + serve docs (http://localhost:8080)

# Full stack (Docker)
make docker-up

# Lightdash BI (self-hosted, port 8090) — do NOT run while pipeline is active
docker-compose up lightdash-db lightdash

# Pattern validation
python validate_patterns.py

# Linting
ruff check .                      # Python
sqlfluff lint dbt_project/        # SQL
```

## Claude Code Slash Commands

| Command | What it does |
|---|---|
| `/run-pipeline` | Start API → dlt ingest → dbt run → dbt test, with summary |
| `/dbt-check` | sqlfluff lint + dbt tests + ruff, consolidated failure report |
| `/bi-roadmap` | Load the agentic BI roadmap skill (Phases 1–4, Lightdash, Slack agent) |

---

## Project Structure

```
soundflow-pipeline/
├── mock_api/           # FastAPI deterministic mock server
├── pipeline/           # dlt ingestion (HTTP → DuckDB raw schema)
├── dbt_project/        # dbt project
│   ├── models/
│   │   ├── staging/        # stg_* — typed, renamed
│   │   ├── intermediate/   # int_* — joined/enriched
│   │   └── marts/          # final analytics tables
│   ├── tests/              # singular SQL assertion tests
│   └── macros/
├── .github/workflows/  # CI + daily pipeline
├── bulk_backfill.py    # Fast historical load (bypasses API)
├── validate_patterns.py
└── Makefile
```

---

## dbt Conventions

- **Layer naming**: `stg_` → staging, `int_` → intermediate, no prefix → marts.
- **Schema per layer**: staging, intermediate, marts (prod); dev_* in dev target.
- **Tests**: Schema tests in `schema.yml`; business-logic tests as singular SQL in `dbt_project/tests/`.
- **Surrogate keys**: Use `dbt_utils.generate_surrogate_key()`.
- **Schema separation**: `generate_schema_name.sql` macro enforces dev vs prod schemas. Never override this.
- **Exposures**: Document all Lightdash dashboards as `exposures:` in `dbt_project/models/marts/exposures.yml`. See `/bi-roadmap` for details.

## SQL Style

- All SQL via sqlfluff (`duckdb` dialect, `jinja` templater).
- Lowercase keywords. Trailing commas.
- CTE-first style — one CTE per logical step.
- Ref models with `{{ ref('model_name') }}`, never direct table names.

## Python Style

- Linted with `ruff`. Line length 100.
- Type hints on all function signatures.
- No bare `except`. Explicit exception types only.

---

## Key Design Constraints

- **Idempotent**: Re-running the pipeline for the same date is safe. Events merge on `event_id`; reference data is replaced.
- **No cloud credentials**: Everything runs locally or via GitHub Actions artifacts. DuckDB is file-based.
- **Deterministic mock data**: Same date → same data. Do not change Faker seeds in `generators.py` or `bulk_backfill.py` without updating tests.
- **DuckDB file as artifact**: The `.duckdb` file accumulates data across GitHub Actions runs. Do not change the artifact name `soundflow-duckdb` without updating both workflows.

---

## BI Layer (Lightdash) — Current Focus

The next phase is building a Lightdash BI layer on top of the dbt marts. Key tasks:

1. Add metric/dimension YAML blocks to mart `schema.yml` files (Lightdash explores).
2. Create `dbt_project/models/marts/exposures.yml` to document dashboards.
3. Configure Lightdash to connect to the DuckDB artifact via dbt project.
4. Build initial dashboards: platform overview, top tracks, genre trends, user segments.

See `/bi-roadmap` (`.claude/skills/bi-roadmap/SKILL.md`) for the full phased plan including the Slack agent.

---

## Do Not

- Do not add `LIMIT` to mart models — marts are already aggregated and must be complete.
- Do not change `write_disposition` values in `pipeline/sources/music_app.py` without understanding idempotency implications.
- Do not modify `bulk_backfill.py` seeds or generators without syncing with `mock_api/generators.py`.
- Do not hard-code schema names in dbt models — always use `{{ target.schema }}` or the schema macro.
- Do not push directly to `main` — use PRs; CI runs lint + tests.
