"""
In-Slack answer engine (Phase 4).

Given a structured intent, queries DuckDB directly and returns a formatted
response dict for the Slack bot to render:

    {"type": "text",  "text": "..."}
    {"type": "table", "text": "..."}              # Slack mrkdwn table
    {"type": "chart", "image_bytes": b"...",
                      "title": "...", "summary": "..."}

Query strategy:
  - Routes the intent to the correct mart table.
  - All queries use parameterised DuckDB (no string interpolation into SQL).
  - Falls back to a "I can't answer that" text reply if the intent can't
    be mapped to a known mart.
"""

from __future__ import annotations

import os
import textwrap
from typing import Any

import duckdb
import pandas as pd

from bi_agent.chart import render_chart

_DUCKDB_PATH = os.environ.get("DUCKDB_PATH", "soundflow.duckdb")

# ---------------------------------------------------------------------------
# Routing table: kpi keyword → (mart, query builder fn name)
# ---------------------------------------------------------------------------
_KPI_ROUTES: dict[str, str] = {
    "streams": "_query_streams",
    "active users": "_query_active_users",
    "completion rate": "_query_completion_rate",
    "skip rate": "_query_skip_rate",
    "listening hours": "_query_listening_hours",
    "genre": "_query_genre_trends",
    "top tracks": "_query_top_tracks",
    "top artists": "_query_top_tracks",  # same mart, different sort
    "user": "_query_user_activity",
    "users": "_query_user_activity",
    "subscription": "_query_subscription_breakdown",
    "platform": "_query_platform_breakdown",
}


def _conn() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(_DUCKDB_PATH, read_only=True)


def _recent_days(timeframe: str | None) -> int:
    """Convert a timeframe string to an integer number of days."""
    if not timeframe:
        return 30
    t = timeframe.lower()
    if "yesterday" in t or "last day" in t:
        return 1
    if "7" in t or "week" in t:
        return 7
    if "14" in t:
        return 14
    if "30" in t or "month" in t:
        return 30
    if "90" in t or "quarter" in t:
        return 90
    if "365" in t or "year" in t:
        return 365
    if "all" in t:
        return 3650  # ~10 years — effectively all time
    return 30


def _df_to_slack_table(df: pd.DataFrame, max_rows: int = 10) -> str:
    """Format a DataFrame as a Slack mrkdwn code block table."""
    df = df.head(max_rows)
    header = " | ".join(str(c) for c in df.columns)
    sep = " | ".join("---" for _ in df.columns)
    rows = "\n".join(" | ".join(str(v) for v in row) for row in df.itertuples(index=False))
    return f"```\n{header}\n{sep}\n{rows}\n```"


# ---------------------------------------------------------------------------
# Query builders
# ---------------------------------------------------------------------------

def _query_streams(intent: dict[str, Any]) -> dict:
    days = _recent_days(intent.get("timeframe"))
    breakdown = intent.get("breakdown", "").lower()

    with _conn() as con:
        if "genre" in breakdown:
            df: pd.DataFrame = con.execute(
                """
                SELECT event_date, genre, stream_count
                FROM   marts.genre_trends
                WHERE  event_date >= current_date - INTERVAL (?) DAY
                ORDER  BY event_date, daily_rank
                """,
                [days],
            ).df()
            img = render_chart(df.groupby("genre")["stream_count"].sum().reset_index(),
                               "bar", f"Streams by Genre — last {days}d",
                               x_col="genre", y_col="stream_count")
            summary = f"Total streams by genre over the last {days} days."
            return {"type": "chart", "image_bytes": img, "title": summary, "summary": summary}

        elif "platform" in breakdown:
            df = con.execute(
                """
                SELECT event_date,
                       streams_ios, streams_android, streams_web,
                       streams_chromecast, streams_alexa
                FROM   marts.daily_listening_stats
                WHERE  event_date >= current_date - INTERVAL (?) DAY
                ORDER  BY event_date
                """,
                [days],
            ).df()
            totals = {
                "ios": int(df["streams_ios"].sum()),
                "android": int(df["streams_android"].sum()),
                "web": int(df["streams_web"].sum()),
                "chromecast": int(df["streams_chromecast"].sum()),
                "alexa": int(df["streams_alexa"].sum()),
            }
            pie_df = pd.DataFrame(list(totals.items()), columns=["platform", "streams"])
            img = render_chart(pie_df, "pie", f"Streams by Platform — last {days}d",
                               x_col="platform", y_col="streams")
            return {"type": "chart", "image_bytes": img,
                    "title": f"Streams by platform – last {days}d",
                    "summary": "  ".join(f"{k}: {v:,}" for k, v in totals.items())}

        else:
            df = con.execute(
                """
                SELECT event_date, total_streams
                FROM   marts.daily_listening_stats
                WHERE  event_date >= current_date - INTERVAL (?) DAY
                ORDER  BY event_date
                """,
                [days],
            ).df()
            total = int(df["total_streams"].sum())
            img = render_chart(df, "line", f"Daily Streams — last {days}d",
                               x_col="event_date", y_col="total_streams")
            return {"type": "chart", "image_bytes": img,
                    "title": f"Daily streams – last {days}d",
                    "summary": f"Total: {total:,} streams over {days} days."}


def _query_active_users(intent: dict[str, Any]) -> dict:
    days = _recent_days(intent.get("timeframe"))
    with _conn() as con:
        df = con.execute(
            """
            SELECT event_date, active_users
            FROM   marts.daily_listening_stats
            WHERE  event_date >= current_date - INTERVAL (?) DAY
            ORDER  BY event_date
            """,
            [days],
        ).df()
    avg = round(float(df["active_users"].mean()), 1)
    img = render_chart(df, "line", f"Daily Active Users — last {days}d",
                       x_col="event_date", y_col="active_users")
    return {"type": "chart", "image_bytes": img,
            "title": f"Daily active users – last {days}d",
            "summary": f"Avg {avg} active users/day over the last {days} days."}


def _query_completion_rate(intent: dict[str, Any]) -> dict:
    days = _recent_days(intent.get("timeframe"))
    with _conn() as con:
        df = con.execute(
            """
            SELECT event_date, completion_rate_pct, skip_rate_pct
            FROM   marts.daily_listening_stats
            WHERE  event_date >= current_date - INTERVAL (?) DAY
            ORDER  BY event_date
            """,
            [days],
        ).df()
    avg_c = round(float(df["completion_rate_pct"].mean()), 1)
    avg_s = round(float(df["skip_rate_pct"].mean()), 1)
    return {
        "type": "text",
        "text": (
            f":headphones: *Engagement — last {days} days*\n"
            f"• Avg completion rate: *{avg_c}%*\n"
            f"• Avg skip rate: *{avg_s}%*"
        ),
    }


def _query_skip_rate(intent: dict[str, Any]) -> dict:
    return _query_completion_rate(intent)


def _query_listening_hours(intent: dict[str, Any]) -> dict:
    days = _recent_days(intent.get("timeframe"))
    with _conn() as con:
        df = con.execute(
            """
            SELECT event_date, total_listening_hours
            FROM   marts.daily_listening_stats
            WHERE  event_date >= current_date - INTERVAL (?) DAY
            ORDER  BY event_date
            """,
            [days],
        ).df()
    total = round(float(df["total_listening_hours"].sum()), 1)
    img = render_chart(df, "line", f"Daily Listening Hours — last {days}d",
                       x_col="event_date", y_col="total_listening_hours")
    return {"type": "chart", "image_bytes": img,
            "title": f"Listening hours – last {days}d",
            "summary": f"Total: {total:,.0f} hours over {days} days."}


def _query_genre_trends(intent: dict[str, Any]) -> dict:
    days = _recent_days(intent.get("timeframe"))
    with _conn() as con:
        df = con.execute(
            """
            SELECT genre,
                   SUM(stream_count) AS total_streams,
                   ROUND(AVG(pct_of_daily_streams), 2) AS avg_daily_share_pct
            FROM   marts.genre_trends
            WHERE  event_date >= current_date - INTERVAL (?) DAY
            GROUP  BY genre
            ORDER  BY total_streams DESC
            LIMIT  10
            """,
            [days],
        ).df()
    img = render_chart(df, "bar", f"Top Genres by Streams — last {days}d",
                       x_col="genre", y_col="total_streams")
    return {"type": "chart", "image_bytes": img,
            "title": f"Genre trends – last {days}d",
            "summary": _df_to_slack_table(df)}


def _query_top_tracks(intent: dict[str, Any]) -> dict:
    days = _recent_days(intent.get("timeframe"))
    with _conn() as con:
        df = con.execute(
            """
            SELECT track_title, artist_name, genre,
                   SUM(stream_count) AS total_streams,
                   ROUND(AVG(completion_rate_pct), 1) AS avg_completion_pct
            FROM   marts.top_tracks_daily
            WHERE  event_date >= current_date - INTERVAL (?) DAY
            GROUP  BY track_title, artist_name, genre
            ORDER  BY total_streams DESC
            LIMIT  10
            """,
            [days],
        ).df()
    return {"type": "table", "text": f"*Top 10 tracks — last {days} days*\n{_df_to_slack_table(df)}"}


def _query_user_activity(intent: dict[str, Any]) -> dict:
    with _conn() as con:
        df = con.execute(
            """
            SELECT username, subscription_type, total_streams,
                   ROUND(total_listening_hours, 1) AS listening_hours,
                   top_genre
            FROM   marts.user_activity
            ORDER  BY total_streams DESC
            LIMIT  10
            """
        ).df()
    return {"type": "table", "text": f"*Top 10 users (all time)*\n{_df_to_slack_table(df)}"}


def _query_subscription_breakdown(intent: dict[str, Any]) -> dict:
    with _conn() as con:
        df = con.execute(
            """
            SELECT subscription_type,
                   COUNT(*) AS users,
                   SUM(total_streams) AS total_streams,
                   ROUND(AVG(total_listening_hours), 1) AS avg_hours
            FROM   marts.user_activity
            GROUP  BY subscription_type
            ORDER  BY total_streams DESC
            """
        ).df()
    img = render_chart(df, "pie", "Streams by Subscription Type",
                       x_col="subscription_type", y_col="total_streams")
    return {"type": "chart", "image_bytes": img,
            "title": "Subscription breakdown",
            "summary": _df_to_slack_table(df)}


def _query_platform_breakdown(intent: dict[str, Any]) -> dict:
    intent = {**intent, "breakdown": "platform"}
    return _query_streams(intent)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

_QUERY_FNS: dict[str, Any] = {
    "_query_streams": _query_streams,
    "_query_active_users": _query_active_users,
    "_query_completion_rate": _query_completion_rate,
    "_query_skip_rate": _query_skip_rate,
    "_query_listening_hours": _query_listening_hours,
    "_query_genre_trends": _query_genre_trends,
    "_query_top_tracks": _query_top_tracks,
    "_query_user_activity": _query_user_activity,
    "_query_subscription_breakdown": _query_subscription_breakdown,
    "_query_platform_breakdown": _query_platform_breakdown,
}


def answer_question(intent: dict[str, Any]) -> dict:
    """
    Route the intent to a query builder and return a formatted answer dict.
    Falls back to a "can't answer" text reply if no route is found.
    """
    kpi = (intent.get("kpi") or "").lower()
    breakdown = (intent.get("breakdown") or "").lower()

    fn_name: str | None = None
    for keyword, fn in _KPI_ROUTES.items():
        if keyword in kpi or keyword in breakdown:
            fn_name = fn
            break

    if not fn_name:
        return {
            "type": "text",
            "text": (
                ":thinking_face: I couldn't map that question to a known metric. "
                "Try asking about streams, active users, completion rate, genre trends, "
                "top tracks, or user segments."
            ),
        }

    try:
        return _QUERY_FNS[fn_name](intent)
    except Exception as exc:
        return {
            "type": "text",
            "text": f":warning: Error querying data: {exc}",
        }
