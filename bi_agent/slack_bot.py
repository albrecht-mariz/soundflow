"""
Slack bot (Phase 3 + Phase 4).

Listens for @mentions and DMs.  For each message:

Phase 3 flow:
  1. Parse intent with Claude (claude-haiku-4-5, fast + cheap).
  2. Look up existing dashboard in exposures.yml / Lightdash API.
     → Found: reply with the link.
     → Not found: generate a draft dashboard, post approval buttons.
  3. On [Approve]: move dashboard to "Published" space, reply with link.
     On [Reject]:  delete the draft, reply with confirmation.

Phase 4 flow (in-Slack answers):
  4. If the user asks a direct data question (not a "show me a dashboard"
     request), query DuckDB directly and reply with a formatted answer,
     optionally attaching a chart image.

Environment variables (all required — see .env.example):
    SLACK_BOT_TOKEN
    SLACK_SIGNING_SECRET
    ANTHROPIC_API_KEY
    LIGHTDASH_BASE_URL
    LIGHTDASH_TOKEN
    LIGHTDASH_PROJECT_UUID
    DUCKDB_PATH              path to soundflow.duckdb (default: soundflow.duckdb)
    REVIEWER_SLACK_USER_ID   Slack user ID of the person who can approve dashboards
"""

from __future__ import annotations

import os

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from bi_agent.answer import answer_question
from bi_agent.dashboard_lookup import find_dashboard
from bi_agent.intent import intent_to_prompt, parse_intent
from bi_agent.prompt_to_dashboard import create_draft_dashboard

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

app = App(token=os.environ["SLACK_BOT_TOKEN"])

_REVIEWER_ID = os.environ.get("REVIEWER_SLACK_USER_ID", "")

# Pending approvals: maps action_id → draft dashboard URL
_pending: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_dashboard_request(intent: dict) -> bool:
    """True if the user wants a dashboard/chart, False if they want a direct answer."""
    dashboard_words = {"dashboard", "chart", "show", "visuali", "graph", "report"}
    raw = (intent.get("raw_prompt") or "").lower()
    return any(w in raw for w in dashboard_words)


def _approval_blocks(dashboard_url: str, description: str) -> list[dict]:
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":bar_chart: *New draft dashboard ready for review*\n"
                    f"{description}\n"
                    f"<{dashboard_url}|Open in Lightdash>"
                ),
            },
        },
        {
            "type": "actions",
            "block_id": "dashboard_approval",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":white_check_mark: Approve"},
                    "style": "primary",
                    "action_id": f"approve__{dashboard_url}",
                    "value": dashboard_url,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":x: Reject"},
                    "style": "danger",
                    "action_id": f"reject__{dashboard_url}",
                    "value": dashboard_url,
                },
            ],
        },
    ]


# ---------------------------------------------------------------------------
# Event: app mention or DM
# ---------------------------------------------------------------------------

@app.event("app_mention")
def handle_mention(event: dict, say, client) -> None:
    _handle_message(event, say, client)


@app.event("message")
def handle_dm(event: dict, say, client) -> None:
    # Only handle DMs (channel_type == "im"), ignore bot messages
    if event.get("channel_type") != "im" or event.get("bot_id"):
        return
    _handle_message(event, say, client)


def _handle_message(event: dict, say, client) -> None:
    user_text: str = event.get("text", "").strip()
    thread_ts: str = event.get("ts", "")

    # Strip the bot mention prefix if present
    if "<@" in user_text:
        user_text = user_text.split(">", 1)[-1].strip()

    if not user_text:
        say(text="Hi! Ask me a data question or say 'build a dashboard for ...'",
            thread_ts=thread_ts)
        return

    intent = parse_intent(user_text)

    if _is_dashboard_request(intent):
        _handle_dashboard_request(intent, say, thread_ts)
    else:
        _handle_direct_question(intent, say, client, event, thread_ts)


# ---------------------------------------------------------------------------
# Dashboard request flow (Phase 3)
# ---------------------------------------------------------------------------

def _handle_dashboard_request(intent: dict, say, thread_ts: str) -> None:
    existing_url = find_dashboard(intent)

    if existing_url:
        say(
            text=f":bar_chart: Found an existing dashboard: {existing_url}",
            thread_ts=thread_ts,
        )
        return

    say(text=":hourglass: No existing dashboard found. Building a draft...", thread_ts=thread_ts)

    prompt = intent_to_prompt(intent)
    draft_url = create_draft_dashboard(prompt)

    say(
        blocks=_approval_blocks(draft_url, prompt),
        text=f"Draft dashboard ready for review: {draft_url}",
        thread_ts=thread_ts,
    )


# ---------------------------------------------------------------------------
# Approval actions (Phase 3)
# ---------------------------------------------------------------------------

@app.action({"action_id": lambda id: id.startswith("approve__")})
def handle_approve(ack, action, body, say) -> None:
    ack()
    user_id = body["user"]["id"]

    if _REVIEWER_ID and user_id != _REVIEWER_ID:
        say(text=f":no_entry: Only <@{_REVIEWER_ID}> can approve dashboards.")
        return

    draft_url: str = action["value"]

    # Move from draft space to "Published" space via Lightdash client
    try:
        from bi_agent.lightdash_client import get_or_create_space, move_dashboard_to_space
        uuid = draft_url.rstrip("/").split("/")[-3]  # extract uuid from URL path
        published_space_uuid = get_or_create_space("Published")
        move_dashboard_to_space(uuid, published_space_uuid)
        say(text=f":white_check_mark: Dashboard published: {draft_url}")
    except Exception as exc:
        say(text=f":warning: Could not publish automatically: {exc}\nManually move it in Lightdash.")


@app.action({"action_id": lambda id: id.startswith("reject__")})
def handle_reject(ack, action, body, say) -> None:
    ack()
    user_id = body["user"]["id"]

    if _REVIEWER_ID and user_id != _REVIEWER_ID:
        say(text=f":no_entry: Only <@{_REVIEWER_ID}> can reject dashboards.")
        return

    say(text=":x: Dashboard rejected and will not be published.")


# ---------------------------------------------------------------------------
# Direct data question flow (Phase 4)
# ---------------------------------------------------------------------------

def _handle_direct_question(intent: dict, say, client, event: dict, thread_ts: str) -> None:
    result = answer_question(intent)

    if result["type"] == "text":
        say(text=result["text"], thread_ts=thread_ts)

    elif result["type"] == "table":
        say(text=result["text"], thread_ts=thread_ts)

    elif result["type"] == "chart":
        # Upload the chart image as a Slack file
        client.files_upload_v2(
            channel=event["channel"],
            thread_ts=thread_ts,
            file=result["image_bytes"],
            filename="chart.png",
            title=result.get("title", "Chart"),
            initial_comment=result.get("summary", ""),
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Socket mode requires SLACK_APP_TOKEN (xapp-...) in addition to the bot token
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    print("⚡ SoundFlow BI bot is running")
    handler.start()
