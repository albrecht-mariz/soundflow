"""
Dashboard lookup (Phase 3).

Given a structured intent, searches:
  1. The local dbt exposures.yml index (fast, no API call needed)
  2. The Lightdash REST API (live, catches dashboards not yet in exposures)

Returns the best-matching dashboard URL, or None if no match is found.
"""

from __future__ import annotations

import pathlib
import re
from typing import Any

import yaml

from bi_agent.intent import Intent
from bi_agent.lightdash_client import dashboard_url, list_dashboards

_EXPOSURES_PATH = (
    pathlib.Path(__file__).parent.parent
    / "dbt_project"
    / "models"
    / "marts"
    / "exposures.yml"
)

# Words that indicate a KPI or breakdown (used for fuzzy name matching)
_STOPWORDS = {"show", "me", "the", "a", "an", "for", "by", "of", "in", "on", "and", "or"}


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z]+", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def _score(tokens: set[str], candidate_name: str) -> int:
    candidate_tokens = _tokenize(candidate_name)
    return len(tokens & candidate_tokens)


def _load_exposures() -> list[dict[str, Any]]:
    if not _EXPOSURES_PATH.exists():
        return []
    with _EXPOSURES_PATH.open() as f:
        data = yaml.safe_load(f)
    return data.get("exposures", [])


def find_dashboard(intent: dict[str, Any]) -> str | None:
    """
    Return a dashboard URL that best matches the intent, or None.

    Search order: exposures.yml first (fast), Lightdash API second.
    Returns None if no dashboard scores above the minimum threshold.
    """
    query_tokens = _tokenize(
        " ".join(filter(None, [
            intent.get("kpi"),
            intent.get("breakdown"),
            intent.get("raw_prompt"),
        ]))
    )
    min_score = 1  # at least one overlapping content word

    # --- 1. Search local exposures.yml -----------------------------------
    best_url: str | None = None
    best_score: int = 0

    for exposure in _load_exposures():
        name: str = exposure.get("name", "")
        description: str = exposure.get("description", "")
        url: str | None = exposure.get("url")

        if not url or "<uuid>" in url:
            continue  # URL not yet filled in

        score = _score(query_tokens, name) + _score(query_tokens, description)
        if score > best_score:
            best_score = score
            best_url = url

    if best_score >= min_score:
        return best_url

    # --- 2. Search Lightdash API live dashboards --------------------------
    try:
        dashboards = list_dashboards()
    except Exception:
        return None  # Lightdash may not be running — degrade gracefully

    for dash in dashboards:
        name = dash.get("name", "")
        description = dash.get("description", "")
        uuid = dash.get("uuid")
        if not uuid:
            continue
        score = _score(query_tokens, name) + _score(query_tokens, description)
        if score > best_score:
            best_score = score
            best_url = dashboard_url(uuid)

    return best_url if best_score >= min_score else None
