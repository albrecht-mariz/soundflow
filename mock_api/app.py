"""
SoundFlow Mock API — simulates a music streaming app's internal data API.

Endpoints:
  GET /health
  GET /artists?page=1&page_size=100
  GET /albums?page=1&page_size=100
  GET /tracks?page=1&page_size=100
  GET /users?page=1&page_size=100
  GET /events?date=YYYY-MM-DD&page=1&page_size=1000
"""

from datetime import date
from fastapi import FastAPI, Query, HTTPException
from generators import (
    generate_artists,
    generate_albums,
    generate_tracks,
    generate_users,
    generate_events,
)

app = FastAPI(
    title="SoundFlow Mock API",
    description="Deterministic mock API simulating a music streaming service.",
    version="1.0.0",
)

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 1000


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/artists")
def get_artists(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
):
    return generate_artists(page=page, page_size=page_size)


@app.get("/albums")
def get_albums(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
):
    return generate_albums(page=page, page_size=page_size)


@app.get("/tracks")
def get_tracks(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
):
    return generate_tracks(page=page, page_size=page_size)


@app.get("/users")
def get_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
):
    return generate_users(page=page, page_size=page_size)


@app.get("/events")
def get_events(
    event_date: date = Query(..., alias="date", description="Date in YYYY-MM-DD format"),
    page: int = Query(1, ge=1),
    page_size: int = Query(1000, ge=1, le=MAX_PAGE_SIZE),
):
    if event_date > date.today():
        raise HTTPException(status_code=400, detail="Cannot request future dates.")
    return generate_events(event_date=event_date, page=page, page_size=page_size)
