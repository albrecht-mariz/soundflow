"""
Metrics context loader (Phase 2).

Reads the dbt schema.yml meta: blocks for all mart models and builds a
compact text representation that can be injected into the agent's system
prompt so it knows which metrics and dimensions are available in Lightdash.

Usage:
    from bi_agent.metrics_context import build_metrics_context
    ctx = build_metrics_context()          # reads dbt_project/models/marts/schema.yml
    ctx = build_metrics_context(path)      # custom path
"""

from __future__ import annotations

import pathlib
from typing import Any

import yaml


# Default: resolve relative to this file's location
_DEFAULT_SCHEMA = (
    pathlib.Path(__file__).parent.parent
    / "dbt_project"
    / "models"
    / "marts"
    / "schema.yml"
)


def build_metrics_context(schema_path: pathlib.Path | str = _DEFAULT_SCHEMA) -> str:
    """Return a concise text listing of every Lightdash metric and dimension."""
    schema_path = pathlib.Path(schema_path)
    with schema_path.open() as f:
        data: dict[str, Any] = yaml.safe_load(f)

    lines: list[str] = []
    for model in data.get("models", []):
        model_name: str = model["name"]
        model_label: str = model.get("meta", {}).get("label", model_name)
        lines.append(f"\n## Explore: {model_label} (model: {model_name})")

        dimensions: list[str] = []
        metrics: list[str] = []

        for col in model.get("columns", []):
            col_name: str = col["name"]
            meta: dict[str, Any] = col.get("meta", {})

            dim: dict[str, Any] | None = meta.get("dimension")
            if dim:
                dim_label = dim.get("label", col_name)
                dim_type = dim.get("type", "string")
                dimensions.append(f"  - {col_name} ({dim_type}) → \"{dim_label}\"")

            for metric_key, metric_def in meta.get("metrics", {}).items():
                m_label = metric_def.get("label", metric_key)
                m_type = metric_def.get("type", "")
                metrics.append(f"  - {metric_key} ({m_type}) → \"{m_label}\" [on {col_name}]")

        if dimensions:
            lines.append("Dimensions:")
            lines.extend(dimensions)
        if metrics:
            lines.append("Metrics:")
            lines.extend(metrics)

    return "\n".join(lines)


def list_explores() -> list[dict[str, str]]:
    """Return a list of {name, label} dicts for every mart model."""
    schema_path = _DEFAULT_SCHEMA
    with schema_path.open() as f:
        data: dict[str, Any] = yaml.safe_load(f)
    return [
        {
            "name": m["name"],
            "label": m.get("meta", {}).get("label", m["name"]),
        }
        for m in data.get("models", [])
    ]


if __name__ == "__main__":
    print(build_metrics_context())
