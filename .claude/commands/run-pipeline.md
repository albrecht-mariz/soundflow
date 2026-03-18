# /run-pipeline

Run the full SoundFlow daily pipeline: mock API → dlt ingestion → dbt run → dbt test.

## Steps

1. Check that the mock API is running. If not, start it:
   ```bash
   cd mock_api && uvicorn app:app --host 0.0.0.0 --port 8000 --reload &
   ```
   Wait for it to be healthy before proceeding (`curl http://localhost:8000/health`).

2. Run the dlt pipeline to ingest yesterday's events:
   ```bash
   cd pipeline && python pipeline.py
   ```

3. Run dbt models:
   ```bash
   cd dbt_project && dbt run --profiles-dir . --target dev
   ```

4. Run dbt tests:
   ```bash
   cd dbt_project && dbt test --profiles-dir . --target dev
   ```

5. Report a summary:
   - How many events were loaded (from dlt output)
   - Which dbt models ran and whether any tests failed
   - If tests failed, show the failing test names and ask whether to investigate

## Notes
- Do not run this while Lightdash is running against `soundflow.duckdb` — DuckDB allows only one writer at a time.
- Use `--target prod` instead of `dev` for production runs.
- For historical backfill use `make backfill START_DATE=YYYY-MM-DD` instead.
