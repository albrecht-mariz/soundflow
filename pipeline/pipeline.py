"""
SoundFlow ingestion pipeline.

Usage:
    # Run daily (loads yesterday's events + reference data):
    python pipeline.py

    # Run with historical backfill (e.g. last 30 days):
    python pipeline.py --start-date 2025-01-01

    # Dry run (show what would be loaded, no writes):
    python pipeline.py --dry-run
"""

import argparse
import os
from datetime import date, timedelta
import dlt
from sources.music_app import soundflow_source


def parse_args():
    parser = argparse.ArgumentParser(description="SoundFlow dlt ingestion pipeline")
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="ISO date (YYYY-MM-DD) to backfill events from. Defaults to yesterday.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print pipeline config without running.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    api_base_url = os.getenv("SOUNDFLOW_API_URL", "http://localhost:8000")

    # Default start_date: yesterday (so daily run loads one day of events)
    start_date = args.start_date or (date.today() - timedelta(days=1)).isoformat()

    print(f"API URL     : {api_base_url}")
    print(f"Start date  : {start_date}")
    print(f"Run date    : {date.today().isoformat()}")

    if args.dry_run:
        print("Dry run — exiting without loading data.")
        return

    pipeline = dlt.pipeline(
        pipeline_name="soundflow",
        destination=dlt.destinations.duckdb(
            credentials=os.getenv("DUCKDB_PATH", "soundflow.duckdb")
        ),
        dataset_name="raw",
        progress="log",
    )

    source = soundflow_source(
        api_base_url=api_base_url,
        start_date=start_date,
    )

    load_info = pipeline.run(source)

    print(load_info)
    print("Pipeline completed successfully.")


if __name__ == "__main__":
    main()
