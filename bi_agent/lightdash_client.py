"""
Lightdash client helpers (Phases 2–3).

Thin wrapper around the Lightdash REST API used by both the CLI tool
(Phase 2) and the Slack bot (Phase 3).

Environment variables (see .env.example):
    LIGHTDASH_BASE_URL   e.g. http://localhost:8090
    LIGHTDASH_TOKEN      Personal access token from Lightdash → Settings → API tokens
    LIGHTDASH_PROJECT_UUID  UUID of the Lightdash project (shown in the URL)
"""

from __future__ import annotations

import os

import httpx


def _base() -> str:
    return os.environ["LIGHTDASH_BASE_URL"].rstrip("/")


def _headers() -> dict[str, str]:
    return {"Authorization": f"ApiKey {os.environ['LIGHTDASH_TOKEN']}"}


def _project() -> str:
    return os.environ["LIGHTDASH_PROJECT_UUID"]


# ---------------------------------------------------------------------------
# Dashboards
# ---------------------------------------------------------------------------

def list_dashboards() -> list[dict]:
    """Return all dashboards in the project."""
    url = f"{_base()}/api/v1/projects/{_project()}/dashboards"
    r = httpx.get(url, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json().get("results", [])


def get_dashboard(dashboard_uuid: str) -> dict:
    url = f"{_base()}/api/v1/dashboards/{dashboard_uuid}"
    r = httpx.get(url, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()["results"]


def create_dashboard(payload: dict) -> dict:
    """Create a new dashboard (draft). Returns the created dashboard dict."""
    url = f"{_base()}/api/v1/projects/{_project()}/dashboards"
    r = httpx.post(url, json=payload, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()["results"]


def dashboard_url(dashboard_uuid: str) -> str:
    return f"{_base()}/projects/{_project()}/dashboards/{dashboard_uuid}/view"


# ---------------------------------------------------------------------------
# Saved charts (tiles inside a dashboard)
# ---------------------------------------------------------------------------

def create_chart(payload: dict) -> dict:
    """Create a saved chart (used as a tile source). Returns the chart dict."""
    url = f"{_base()}/api/v1/projects/{_project()}/saved"
    r = httpx.post(url, json=payload, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()["results"]


def run_chart_query(chart_uuid: str) -> dict:
    """Execute a saved chart query and return the results."""
    url = f"{_base()}/api/v1/saved/{chart_uuid}/results"
    r = httpx.post(url, json={}, headers=_headers(), timeout=60)
    r.raise_for_status()
    return r.json()["results"]


# ---------------------------------------------------------------------------
# Spaces (for approval workflow — draft vs published)
# ---------------------------------------------------------------------------

def list_spaces() -> list[dict]:
    url = f"{_base()}/api/v1/projects/{_project()}/spaces"
    r = httpx.get(url, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json().get("results", [])


def get_or_create_space(name: str) -> str:
    """Return the UUID of a space by name, creating it if it doesn't exist."""
    for space in list_spaces():
        if space["name"] == name:
            return space["uuid"]
    url = f"{_base()}/api/v1/projects/{_project()}/spaces"
    r = httpx.post(url, json={"name": name, "isPrivate": True}, headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()["results"]["uuid"]


def move_dashboard_to_space(dashboard_uuid: str, space_uuid: str) -> None:
    url = f"{_base()}/api/v1/dashboards/{dashboard_uuid}"
    r = httpx.patch(url, json={"spaceUuid": space_uuid}, headers=_headers(), timeout=15)
    r.raise_for_status()
