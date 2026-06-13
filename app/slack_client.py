"""
Phase 10: Slack Client

Sends two types of messages to Slack:
  - post_summary()        : Final meeting summary to the notification channel
  - post_review_request() : Interactive approve/reject card to the approval channel

Also provides update_message() for Phase 11 to update a message after approval/rejection.
"""
import logging

import aiohttp

from app.config import settings
from app.schemas import ActionItem, MeetingExtraction

logger = logging.getLogger(__name__)

_SLACK_API = "https://slack.com/api"


def _headers() -> dict:
    """Authorization headers for all Slack API calls."""
    return {
        "Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}",
        "Content-Type": "application/json",
    }


async def _post_message(channel: str, blocks: list, text: str) -> dict:
    """
    Internal helper — posts a Block Kit message to a Slack channel.
    Returns the full Slack API response dict.
    Raises RuntimeError if Slack reports an error.
    """
    payload = {"channel": channel, "blocks": blocks, "text": text}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{_SLACK_API}/chat.postMessage", json=payload, headers=_headers()
        ) as resp:
            data = await resp.json()

    if not data.get("ok"):
        raise RuntimeError(
            f"Slack chat.postMessage failed: {data.get('error', 'unknown')} "
            f"(channel={channel})"
        )
    return data


async def post_summary(
    extraction: MeetingExtraction,
    tickets_created: list[str],
    pending_titles: list[str],
) -> None:
    """
    Post a formatted meeting intelligence summary to the notification channel.

    Args:
        extraction:      The full Gemini extraction result.
        tickets_created: List of Jira ticket keys that were auto-created.
        pending_titles:  Titles of action items routed to human review.
    """
    base_url = settings.JIRA_BASE_URL.rstrip("/")
    auto_text = (
        "\n".join(
            f"• <{base_url}/browse/{key}|{key}>" for key in tickets_created
        )
        or "_None_"
    )
    pending_text = (
        "\n".join(f"• {title}" for title in pending_titles) or "_None_"
    )

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Meeting Intelligence Summary",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Summary:*\n{extraction.meeting_summary}",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Jira Tickets Created Automatically ({len(tickets_created)}):*\n"
                    f"{auto_text}"
                ),
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Items Routed for Human Review ({len(pending_titles)}):*\n"
                    f"{pending_text}"
                ),
            },
        },
    ]

    await _post_message(
        channel=settings.SLACK_NOTIFY_CHANNEL_ID,
        blocks=blocks,
        text="Meeting Intelligence Summary",
    )
    logger.info(
        "Posted meeting summary to Slack | %d tickets, %d pending",
        len(tickets_created),
        len(pending_titles),
    )


async def post_review_request(item: ActionItem, review_id: int) -> str:
    """
    Post an interactive review card (with Approve/Reject buttons) to the
    approval channel. The button value carries the review_id so the
    /slack/interactions endpoint can look it up directly.

    Args:
        item:      The ambiguous ActionItem that needs human review.
        review_id: The PendingReview.id to embed in the button payload.

    Returns:
        The Slack message timestamp (ts) — stored in PendingReview.slack_message_ts.
    """
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Action Item Requires Human Review",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Task:*\n{item.title}"},
                {"type": "mrkdwn", "text": f"*Priority:* {item.priority}"},
                {
                    "type": "mrkdwn",
                    "text": f"*Assignee:* {item.assignee or '_Unassigned_'}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Confidence:* {item.confidence:.0%}",
                },
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Description:*\n{item.description}",
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve", "emoji": True},
                    "style": "primary",
                    "action_id": "approve",
                    "value": str(review_id),
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Reject", "emoji": True},
                    "style": "danger",
                    "action_id": "reject",
                    "value": str(review_id),
                },
            ],
        },
    ]

    data = await _post_message(
        channel=settings.SLACK_APPROVAL_CHANNEL_ID,
        blocks=blocks,
        text=f"Review required: {item.title}",
    )
    message_ts: str = data["ts"]
    logger.info(
        "Posted review request for '%s' | review_id=%d ts=%s",
        item.title,
        review_id,
        message_ts,
    )
    return message_ts


async def update_message(channel: str, ts: str, text: str) -> None:
    """
    Replace an existing Slack message with plain text.
    Used after Approve/Reject to show the outcome and remove the buttons.

    Args:
        channel: Slack channel ID.
        ts:      Timestamp of the message to update.
        text:    The new plain-text content.
    """
    payload = {
        "channel": channel,
        "ts": ts,
        "text": text,
        "blocks": [],  # Clear blocks to remove the interactive buttons
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{_SLACK_API}/chat.update", json=payload, headers=_headers()
        ) as resp:
            data = await resp.json()

    if not data.get("ok"):
        # Non-fatal — log but don't crash the workflow
        logger.warning(
            "Slack chat.update failed: %s (channel=%s ts=%s)",
            data.get("error"),
            channel,
            ts,
        )
