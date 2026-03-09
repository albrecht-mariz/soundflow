# SoundFlow Data Pipeline — Developer Convenience Commands
# Usage: make <target>

.PHONY: help setup api pipeline dbt run backfill test clean docs

DUCKDB_PATH ?= soundflow.duckdb
API_URL      ?= http://localhost:8000
START_DATE   ?= $(shell python -c "from datetime import date, timedelta; print((date.today()-timedelta(days=7)).isoformat())")
DBT          ?= /c/Users/acmar/Documents/venv/soundflow312/Scripts/dbt

help:   ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Setup ──────────────────────────────────────────────────────────────────────

setup: ## Install all Python dependencies locally
	pip install -r mock_api/requirements.txt
	pip install -r pipeline/requirements.txt
	pip install -r dbt_project/requirements.txt
	cd dbt_project && dbt deps

# ── Mock API ───────────────────────────────────────────────────────────────────

api: ## Start the mock API server (background)
	cd mock_api && uvicorn app:app --host 0.0.0.0 --port 8000 --reload

api-check: ## Test API health and sample endpoints
	@echo "Health:"; curl -s $(API_URL)/health | python -m json.tool
	@echo "\nArtists (2):"; curl -s "$(API_URL)/artists?page_size=2" | python -m json.tool
	@echo "\nEvents (yesterday):"; curl -s "$(API_URL)/events?date=$(shell python -c "from datetime import date, timedelta; print((date.today()-timedelta(days=1)).isoformat())")&page_size=3" | python -m json.tool

# ── Pipeline ───────────────────────────────────────────────────────────────────

pipeline: ## Run dlt ingestion for yesterday
	cd pipeline && SOUNDFLOW_API_URL=$(API_URL) DUCKDB_PATH=../$(DUCKDB_PATH) python pipeline.py

backfill: ## Backfill events from START_DATE (default: 7 days ago)
	@echo "Backfilling from $(START_DATE) ..."
	cd pipeline && SOUNDFLOW_API_URL=$(API_URL) DUCKDB_PATH=../$(DUCKDB_PATH) python pipeline.py --start-date $(START_DATE)

# ── dbt ────────────────────────────────────────────────────────────────────────

dbt: ## Run all dbt models
	cd dbt_project && DUCKDB_PATH=../$(DUCKDB_PATH) $(DBT) run --profiles-dir .

dbt-test: ## Run dbt tests
	cd dbt_project && DUCKDB_PATH=../$(DUCKDB_PATH) $(DBT) test --profiles-dir .

dbt-docs: ## Generate and serve dbt documentation
	cd dbt_project && DUCKDB_PATH=../$(DUCKDB_PATH) $(DBT) docs generate --profiles-dir . && $(DBT) docs serve

# ── Full run ───────────────────────────────────────────────────────────────────

run: pipeline dbt ## Run dlt pipeline then dbt (requires API running)

# ── Docker ─────────────────────────────────────────────────────────────────────

docker-up: ## Start all services via docker-compose
	mkdir -p data
	docker compose up --build

docker-down: ## Stop all docker-compose services
	docker compose down

# ── Testing & QA ──────────────────────────────────────────────────────────────

test: ## Run dbt tests and print DuckDB table counts
	cd dbt_project && DUCKDB_PATH=../$(DUCKDB_PATH) $(DBT) test --profiles-dir .
	@python - <<'EOF'
	import duckdb
	con = duckdb.connect("$(DUCKDB_PATH)", read_only=True)
	for schema, tbl in [("raw","artists"),("raw","tracks"),("raw","users"),("raw","stream_events"),
	                    ("marts","daily_listening_stats"),("marts","top_tracks_daily"),
	                    ("marts","user_activity"),("marts","genre_trends")]:
	    try:
	        n = con.execute(f"SELECT count(*) FROM {schema}.{tbl}").fetchone()[0]
	        print(f"  {schema}.{tbl}: {n:,}")
	    except Exception as e:
	        print(f"  {schema}.{tbl}: {e}")
	EOF

# ── Cleanup ────────────────────────────────────────────────────────────────────

clean: ## Remove generated files (DuckDB, dbt target)
	rm -f $(DUCKDB_PATH)
	rm -rf dbt_project/target dbt_project/dbt_packages pipeline/.dlt/pipeline_state
	@echo "Cleaned."
