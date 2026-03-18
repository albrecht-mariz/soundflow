# /dbt-check

Run all dbt quality checks: SQL linting (sqlfluff) + dbt schema tests + singular tests.

## Steps

1. Lint all SQL models and tests with sqlfluff:
   ```bash
   sqlfluff lint dbt_project/ --dialect duckdb --templater jinja
   ```
   Collect any lint violations. Do not fix automatically — report them first.

2. Run dbt schema tests (not_null, unique, accepted_values, relationships):
   ```bash
   cd dbt_project && dbt test --profiles-dir . --target dev --select test_type:generic
   ```

3. Run dbt singular tests (custom SQL assertions in `dbt_project/tests/`):
   ```bash
   cd dbt_project && dbt test --profiles-dir . --target dev --select test_type:singular
   ```

4. Run Python linting with ruff:
   ```bash
   ruff check .
   ```

5. Report a consolidated summary:
   - sqlfluff: number of violations per file (if any)
   - dbt generic tests: pass / fail counts
   - dbt singular tests: pass / fail counts
   - ruff: number of issues (if any)
   - If anything failed, list the specific failures and ask whether to fix them

## Notes
- Requires dbt models to have been run first (`/run-pipeline` or `make dbt`).
- sqlfluff uses the DuckDB dialect and Jinja templater — do not change these.
- Singular tests live in `dbt_project/tests/` and validate business logic (e.g. completion rates must be 0–100%).
