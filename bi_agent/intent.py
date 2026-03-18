"""
Intent classifier (Phase 3).

Parses a Slack message into a structured analytics intent using Claude.
The intent is used by dashboard_lookup.py to find an existing dashboard
or by prompt_to_dashboard.py to build a new one.

Returned intent schema:
    {
        "kpi":        str,          # e.g. "streams", "active users", "completion rate"
        "breakdown":  str | None,   # e.g. "genre", "platform", "subscription type"
        "timeframe":  str | None,   # e.g. "last 7 days", "this month", "all time"
        "entity":     str | None,   # e.g. "track", "artist", "user" — if scoped to one
        "raw_prompt": str,          # original user message, verbatim
    }
"""

from __future__ import annotations

import json
import textwrap
from typing import Any

import anthropic

_SYSTEM = textwrap.dedent("""\
    You extract structured analytics intent from a Slack message sent to a BI bot.

    Return ONLY a JSON object with these keys (use null for unknown fields):
    - kpi        : the main metric being asked about (e.g. "streams", "active users")
    - breakdown  : the dimension to group by (e.g. "genre", "platform", null)
    - timeframe  : the time range (e.g. "last 7 days", "yesterday", "all time", null)
    - entity     : a specific entity being scoped to (e.g. "track X", "user Y", null)
    - raw_prompt : the original message verbatim

    Examples:
    Input:  "How many streams did we get last week?"
    Output: {"kpi":"streams","breakdown":null,"timeframe":"last 7 days","entity":null,"raw_prompt":"..."}

    Input:  "Show genre trends for the past 30 days"
    Output: {"kpi":"streams","breakdown":"genre","timeframe":"last 30 days","entity":null,"raw_prompt":"..."}

    Input:  "Who are our top 10 users this month?"
    Output: {"kpi":"active users","breakdown":"user","timeframe":"this month","entity":null,"raw_prompt":"..."}

    Return ONLY raw JSON, no markdown fences.
""")


def parse_intent(message: str) -> dict[str, Any]:
    """Extract a structured intent dict from a raw Slack message."""
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        system=_SYSTEM,
        messages=[{"role": "user", "content": message}],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:]).rstrip("`").strip()
    intent: dict[str, Any] = json.loads(raw)
    intent["raw_prompt"] = message
    return intent


def intent_to_prompt(intent: dict[str, Any]) -> str:
    """Convert a structured intent back to a natural-language dashboard prompt."""
    parts: list[str] = [f"Show {intent['kpi']}"]
    if intent.get("breakdown"):
        parts.append(f"broken down by {intent['breakdown']}")
    if intent.get("timeframe"):
        parts.append(f"for {intent['timeframe']}")
    if intent.get("entity"):
        parts.append(f"(scoped to {intent['entity']})")
    return " ".join(parts)
