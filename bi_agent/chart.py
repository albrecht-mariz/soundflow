"""
Chart renderer (Phase 4).

Generates a Matplotlib chart from a pandas DataFrame and returns the PNG
as bytes, ready to upload to the Slack Files API.
"""

from __future__ import annotations

import io
from typing import Literal

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.use("Agg")  # non-interactive backend — no display required

ChartType = Literal["line", "bar", "pie", "table"]


def render_chart(
    df: pd.DataFrame,
    chart_type: ChartType,
    title: str,
    x_col: str,
    y_col: str,
    *,
    figsize: tuple[int, int] = (10, 5),
) -> bytes:
    """Render a chart and return PNG bytes."""
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#161b22")
    ax.tick_params(colors="#c9d1d9")
    ax.xaxis.label.set_color("#c9d1d9")
    ax.yaxis.label.set_color("#c9d1d9")
    ax.title.set_color("#f0f6fc")
    for spine in ax.spines.values():
        spine.set_edgecolor("#30363d")

    color = "#58a6ff"

    if chart_type == "line":
        ax.plot(df[x_col], df[y_col], color=color, linewidth=2, marker="o", markersize=4)
        ax.fill_between(df[x_col], df[y_col], alpha=0.15, color=color)
        ax.set_xlabel(x_col)
        ax.set_ylabel(y_col)
        plt.xticks(rotation=45, ha="right")

    elif chart_type == "bar":
        ax.bar(df[x_col], df[y_col], color=color, edgecolor="#30363d")
        ax.set_xlabel(x_col)
        ax.set_ylabel(y_col)
        plt.xticks(rotation=45, ha="right")

    elif chart_type == "pie":
        wedges, texts, autotexts = ax.pie(
            df[y_col],
            labels=df[x_col],
            autopct="%1.1f%%",
            startangle=90,
            colors=plt.cm.tab10.colors,  # type: ignore[attr-defined]
        )
        for t in texts + autotexts:
            t.set_color("#c9d1d9")

    elif chart_type == "table":
        ax.axis("off")
        tbl = ax.table(
            cellText=df.values,
            colLabels=df.columns.tolist(),
            cellLoc="center",
            loc="center",
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(10)
        tbl.scale(1, 1.5)
        for (row, col), cell in tbl.get_celld().items():
            cell.set_edgecolor("#30363d")
            if row == 0:
                cell.set_facecolor("#21262d")
                cell.set_text_props(color="#f0f6fc", fontweight="bold")
            else:
                cell.set_facecolor("#0d1117" if row % 2 == 0 else "#161b22")
                cell.set_text_props(color="#c9d1d9")

    ax.set_title(title, pad=12, fontsize=13)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()
