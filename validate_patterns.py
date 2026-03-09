"""
Validates that the expected data patterns are present in the DuckDB database.

Run after a successful pipeline + dbt run:
    python validate_patterns.py

Checks:
  1. Weekend streams > weekday average
  2. Evening hours (18-22) peak vs morning (2-6) trough
  3. Winter months (Nov-Jan) > summer months (Jun-Aug)
  4. Top 20% users  → ~80% of streams
  5. Top 20% tracks → ~80% of streams
  6. Top 20% artists → ~80% of streams
"""

import os
import sys
import duckdb

DUCKDB_PATH = os.getenv("DUCKDB_PATH", "soundflow.duckdb")
PASS = "\033[92m PASS\033[0m"
FAIL = "\033[91m FAIL\033[0m"
INFO = "\033[94m INFO\033[0m"

def check(label: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    print(f"  [{status}] {label}")
    if detail:
        print(f"         {detail}")
    return condition


def main():
    try:
        con = duckdb.connect(DUCKDB_PATH, read_only=True)
    except Exception as e:
        print(f"Could not open {DUCKDB_PATH}: {e}")
        sys.exit(1)

    results = []
    print(f"\nValidating patterns in: {DUCKDB_PATH}\n")

    # ── 1. Weekend vs weekday ─────────────────────────────────────────────
    print("1. Weekend vs Weekday streams")
    row = con.execute("""
        SELECT
            avg(case when dayofweek(event_date) in (0,6) then total_streams end) as avg_weekend,
            avg(case when dayofweek(event_date) not in (0,6) then total_streams end) as avg_weekday
        FROM marts.daily_listening_stats
    """).fetchone()
    if row and row[0] and row[1]:
        avg_wknd, avg_wkdy = row
        ratio = avg_wknd / avg_wkdy
        results.append(check(
            f"Weekend avg ({avg_wknd:,.0f}) > Weekday avg ({avg_wkdy:,.0f})",
            ratio > 1.10,
            f"Ratio: {ratio:.2f}x  (expect > 1.10x)"
        ))
    else:
        print(f"  [{INFO}] Not enough data (need multiple weeks)")

    # ── 2. Evening vs overnight hours ─────────────────────────────────────
    print("\n2. Evening peak vs overnight trough")
    row = con.execute("""
        SELECT
            sum(case when hour(started_at) between 18 and 22 then 1 end) as evening,
            sum(case when hour(started_at) between 2  and  5 then 1 end) as overnight
        FROM raw.stream_events
    """).fetchone()
    if row and row[1]:
        evening, overnight = row
        ratio = evening / overnight
        results.append(check(
            f"Evening streams ({evening:,}) >> Overnight ({overnight:,})",
            ratio > 3.0,
            f"Ratio: {ratio:.1f}x  (expect > 3x)"
        ))
    else:
        print(f"  [{INFO}] No data")

    # ── 3. Seasonal: winter vs summer ─────────────────────────────────────
    print("\n3. Seasonal patterns (winter > summer)")
    row = con.execute("""
        SELECT
            avg(case when month(event_date) in (11,12,1) then total_streams end) as winter_avg,
            avg(case when month(event_date) in (6,7,8)  then total_streams end) as summer_avg
        FROM marts.daily_listening_stats
    """).fetchone()
    if row and row[0] and row[1]:
        winter, summer = row
        ratio = winter / summer
        results.append(check(
            f"Winter avg ({winter:,.0f}) > Summer avg ({summer:,.0f})",
            ratio > 1.10,
            f"Ratio: {ratio:.2f}x  (expect > 1.10x)"
        ))
    else:
        print(f"  [{INFO}] Need data across multiple seasons to validate")

    # ── 4. User 80/20 ────────────────────────────────────────────────────
    print("\n4. User 80/20 distribution")
    row = con.execute("""
        WITH user_streams AS (
            SELECT user_id, count(*) as streams
            FROM raw.stream_events
            GROUP BY user_id
        ),
        ranked AS (
            SELECT
                user_id,
                streams,
                row_number() over (order by streams desc) as rn,
                count(*) over () as total_users,
                sum(streams) over () as total_streams
            FROM user_streams
        )
        SELECT
            sum(case when rn <= total_users * 0.2 then streams end) * 100.0 / max(total_streams) as top20_pct
        FROM ranked
    """).fetchone()
    if row and row[0]:
        top20_pct = row[0]
        results.append(check(
            f"Top 20% users → {top20_pct:.1f}% of streams",
            top20_pct >= 70.0,
            f"(expect ≥ 70%, target ~80%)"
        ))
    else:
        print(f"  [{INFO}] No data")

    # ── 5. Track 80/20 ────────────────────────────────────────────────────
    print("\n5. Track 80/20 distribution")
    row = con.execute("""
        WITH track_streams AS (
            SELECT track_id, count(*) as streams
            FROM raw.stream_events
            GROUP BY track_id
        ),
        ranked AS (
            SELECT
                track_id,
                streams,
                row_number() over (order by streams desc) as rn,
                count(*) over () as total_tracks,
                sum(streams) over () as total_streams
            FROM track_streams
        )
        SELECT
            sum(case when rn <= total_tracks * 0.2 then streams end) * 100.0 / max(total_streams) as top20_pct
        FROM ranked
    """).fetchone()
    if row and row[0]:
        top20_pct = row[0]
        results.append(check(
            f"Top 20% tracks → {top20_pct:.1f}% of streams",
            top20_pct >= 70.0,
            f"(expect ≥ 70%, target ~80%)"
        ))
    else:
        print(f"  [{INFO}] No data")

    # ── 6. Artist 80/20 ───────────────────────────────────────────────────
    print("\n6. Artist 80/20 distribution")
    row = con.execute("""
        WITH artist_streams AS (
            SELECT t.artist_id, count(*) as streams
            FROM raw.stream_events e
            JOIN raw.tracks t ON e.track_id = t.track_id
            GROUP BY t.artist_id
        ),
        ranked AS (
            SELECT
                artist_id,
                streams,
                row_number() over (order by streams desc) as rn,
                count(*) over () as total_artists,
                sum(streams) over () as total_streams
            FROM artist_streams
        )
        SELECT
            sum(case when rn <= total_artists * 0.2 then streams end) * 100.0 / max(total_streams) as top20_pct
        FROM ranked
    """).fetchone()
    if row and row[0]:
        top20_pct = row[0]
        results.append(check(
            f"Top 20% artists → {top20_pct:.1f}% of streams",
            top20_pct >= 60.0,
            f"(expect ≥ 60%, target ~80%)"
        ))
    else:
        print(f"  [{INFO}] No data")

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n{'─'*50}")
    passed = sum(results)
    total  = len(results)
    print(f"  {passed}/{total} checks passed\n")

    con.close()
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
