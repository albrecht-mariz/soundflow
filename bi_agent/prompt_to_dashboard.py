"""
Prompt → Lightdash dashboard (Phase 2).

Given a natural-language prompt, uses Claude to generate a Lightdash
dashboard definition and then creates it as a draft in Lightdash for
human review before publishing.

CLI usage:
    python -m bi_agent.prompt_to_dashboard "show me weekly streams by genre"

The draft dashboard will be created in the "Draft — Pending Review" space.
Copy the printed URL, open Lightdash, review, then move it to a shared space.
"""

from __future__ import annotations

import json
import os
import sys
import textwrap
from typing import Any

import anthropic

from bi_agent.lightdash_client import (
    create_chart,
    create_dashboard,
    dashboard_url,
    get_or_create_space,
    move_dashboard_to_space,
)
from bi_agent.metrics_context import build_metrics_context, list_explores

_DRAFT_SPACE = "Draft — Pending Review"

_SYSTEM_PROMPT = textwrap.dedent("""\
    You are a BI engineer working with Lightdash (a self-hosted, open-source BI tool
    built on dbt). Your task is to translate a user's natural-language analytics request
    into a valid Lightdash dashboard definition.

    The available explores (dbt mart models) and their metrics/dimensions are listed below.
    You MUST only use the metrics and dimensions listed — do not invent field names.

    Return a JSON object with this structure:
    {{
      "dashboard_name": "<short descriptive name>",
      "description": "<one sentence describing what this dashboard shows>",
      "tiles": [
        {{
          "type": "saved_chart",
          "title": "<tile title>",
          "chart": {{
            "explore": "<model name from the list below>",
            "dimensions": ["<field_name>", ...],
            "metrics": ["<metric_key>", ...],
            "filters": [],
            "sorts": [{{ "fieldId": "<field>", "descending": true }}],
            "limit": 500,
            "chartType": "<bar|line|table|pie|scatter>",
            "chartConfig": {{}}
          }}
        }}
      ]
    }}

    Rules:
    - Include 2–5 tiles per dashboard. Keep it focused.
    - Use "table" chart type for ranked lists (e.g. top tracks).
    - Use "line" for time-series (dimension must be a date field).
    - Use "bar" or "pie" for categorical breakdowns.
    - Return ONLY the raw JSON — no markdown fences, no prose.

    Available explores and fields:
    {metrics_context}
""")


def build_dashboard_payload_from_prompt(prompt: str) -> dict[str, Any]:
    """Ask Claude to generate a Lightdash dashboard definition from a prompt."""
    metrics_context = build_metrics_context()
    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        system=_SYSTEM_PROMPT.format(metrics_context=metrics_context),
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    # Strip accidental markdown fences
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        raw = raw.rstrip("`").strip()
    return json.loads(raw)


def create_draft_dashboard(prompt: str) -> str:
    """
    Full end-to-end: prompt → Claude generates tiles → create charts + dashboard in
    Lightdash draft space. Returns the dashboard URL.
    """
    print(f"Generating dashboard for: {prompt!r}")
    definition = build_dashboard_payload_from_prompt(prompt)
    dashboard_name: str = definition["dashboard_name"]
    description: str = definition.get("description", "")
    tiles_def: list[dict] = definition.get("tiles", [])

    print(f"  Dashboard name : {dashboard_name}")
    print(f"  Tiles          : {len(tiles_def)}")

    # Create each chart as a saved query first, then reference as a tile
    tile_uuids: list[str] = []
    for tile in tiles_def:
        chart_def = tile["chart"]
        chart_payload = {
            "name": tile["title"],
            "description": "",
            "tableName": chart_def["explore"],
            "metricQuery": {
                "dimensions": chart_def.get("dimensions", []),
                "metrics": chart_def.get("metrics", []),
                "filters": {"dimensions": {}, "metrics": {}},
                "sorts": chart_def.get("sorts", []),
                "limit": chart_def.get("limit", 500),
                "tableCalculations": [],
                "additionalMetrics": [],
            },
            "chartConfig": {
                "type": chart_def.get("chartType", "table"),
                "config": chart_def.get("chartConfig", {}),
            },
            "tableConfig": {"columnOrder": []},
            "pivotConfig": None,
        }
        chart = create_chart(chart_payload)
        tile_uuids.append(chart["uuid"])
        print(f"    Created chart: {tile['title']!r} ({chart['uuid']})")

    # Compose dashboard with the created charts as tiles
    tile_rows = []
    for i, (tile, chart_uuid) in enumerate(zip(tiles_def, tile_uuids)):
        tile_rows.append({
            "uuid": None,
            "type": "saved_chart",
            "properties": {"savedChartUuid": chart_uuid, "title": tile["title"]},
            "x": 0,
            "y": i * 6,
            "w": 12,
            "h": 6,
        })

    draft_space_uuid = get_or_create_space(_DRAFT_SPACE)
    dashboard = create_dashboard({
        "name": dashboard_name,
        "description": description,
        "tiles": tile_rows,
        "filters": {"dimensions": [], "metrics": []},
        "spaceUuid": draft_space_uuid,
    })

    url = dashboard_url(dashboard["uuid"])
    print(f"\nDraft dashboard created: {url}")
    print(f"Review in Lightdash, then move to a shared space to publish.")
    return url


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m bi_agent.prompt_to_dashboard \"<prompt>\"")
        sys.exit(1)
    create_draft_dashboard(" ".join(sys.argv[1:]))
