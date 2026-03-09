"""
dlt source for the SoundFlow Mock API.

Implements paginated REST calls for each resource:
  - artists   (full refresh / merge)
  - albums    (full refresh / merge)
  - tracks    (full refresh / merge)
  - users     (full refresh / merge)
  - events    (incremental append by date)
"""

from datetime import date, timedelta
from typing import Iterator
import dlt
import requests
from dlt.sources import DltResource

API_BASE_URL = "http://localhost:8000"
DEFAULT_PAGE_SIZE = 500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _paginate(url: str, params: dict) -> Iterator[list]:
    """Yield pages of results from a paginated endpoint."""
    page = 1
    while True:
        resp = requests.get(url, params={**params, "page": page, "page_size": DEFAULT_PAGE_SIZE}, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        yield body["data"]
        if not body.get("has_more"):
            break
        page += 1


# ---------------------------------------------------------------------------
# dlt source
# ---------------------------------------------------------------------------

@dlt.source(name="soundflow")
def soundflow_source(
    api_base_url: str = dlt.config.value,
    start_date: str = None,
) -> list[DltResource]:
    """
    SoundFlow music streaming data source.

    Args:
        api_base_url: Base URL of the SoundFlow mock API.
        start_date:   ISO date string (YYYY-MM-DD). Events are loaded from this
                      date up to yesterday. Defaults to yesterday only.
    """
    base = api_base_url or API_BASE_URL

    @dlt.resource(name="artists", write_disposition="replace")
    def artists():
        for page_data in _paginate(f"{base}/artists", {}):
            yield page_data

    @dlt.resource(name="albums", write_disposition="replace")
    def albums():
        for page_data in _paginate(f"{base}/albums", {}):
            yield page_data

    @dlt.resource(name="tracks", write_disposition="replace")
    def tracks():
        for page_data in _paginate(f"{base}/tracks", {}):
            yield page_data

    @dlt.resource(name="users", write_disposition="replace")
    def users():
        for page_data in _paginate(f"{base}/users", {}):
            yield page_data

    @dlt.resource(name="stream_events", write_disposition="append", primary_key="event_id")
    def stream_events():
        """Load stream events day by day from start_date up to yesterday."""
        yesterday = date.today() - timedelta(days=1)
        from_date = date.fromisoformat(start_date) if start_date else yesterday

        current = from_date
        while current <= yesterday:
            for page_data in _paginate(f"{base}/events", {"date": current.isoformat()}):
                yield page_data
            current += timedelta(days=1)

    return [artists, albums, tracks, users, stream_events]
