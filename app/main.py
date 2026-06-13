"""
Origin Medical Meeting Intelligence Pipeline
FastAPI application entry point.

Phase 11: Adds startup database initialization and POST /slack/interactions
endpoint for handling Slack button clicks (Approve / Reject).
"""
import hashlib
import hmac
import json
import time
import urllib.parse
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db, init_db
from app.jira_client import create_ticket
from app.models import PendingReview, ReviewStatus
from app.schemas import ActionItem
from app.slack_client import update_message


# ---------------------------------------------------------------------------
# Startup / Shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create all database tables on startup (migration-free)."""
    await init_db()
    yield


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Origin Medical Meeting Intelligence Pipeline",
    description=(
        "AI-powered meeting transcript processor that extracts action items "
        "using Gemini 2.5 Flash, creates Jira tickets automatically for "
        "high-confidence tasks, and routes ambiguous tasks to Slack for "
        "human approval."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Utility"])
async def health_check():
    """Liveness probe — returns OK if the server is running."""
    return {"status": "ok", "version": "0.1.0"}


# ---------------------------------------------------------------------------
# Slack Interactions — Phase 11
# ---------------------------------------------------------------------------

def _verify_slack_signature(body: bytes, timestamp: str, signature: str) -> bool:
    """
    Verify the request is genuinely from Slack using HMAC-SHA256.
    See https://api.slack.com/authentication/verifying-requests-from-slack
    """
    # Reject if headers are missing entirely
    if not timestamp or not signature:
        return False

    # Reject stale requests (replay protection — 5 minute window)
    try:
        if abs(time.time() - float(timestamp)) > 300:
            return False
    except ValueError:
        return False

    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}".encode("utf-8")
    expected = (
        "v0="
        + hmac.new(
            settings.SLACK_SIGNING_SECRET.encode("utf-8"),
            sig_basestring,
            hashlib.sha256,
        ).hexdigest()
    )
    return hmac.compare_digest(expected, signature)


@app.post("/slack/interactions", tags=["Slack"])
async def slack_interactions(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Slack interactive component callbacks (Approve / Reject button clicks).

    Workflow:
      Approve → update PendingReview status to APPROVED, create Jira ticket,
                update Slack message with ticket key.
      Reject  → update PendingReview status to REJECTED, update Slack message.
    """
    body = await request.body()

    # --- Signature verification (skip only if SLACK_SIGNING_SECRET not configured) ---
    if settings.SLACK_SIGNING_SECRET:
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")
        if not _verify_slack_signature(body, timestamp, signature):
            raise HTTPException(status_code=403, detail="Invalid Slack signature")

    # --- Parse URL-encoded form body ---
    form_data = urllib.parse.parse_qs(body.decode("utf-8"))
    raw_payload = form_data.get("payload", [None])[0]
    if not raw_payload:
        raise HTTPException(status_code=400, detail="Missing payload field")

    payload = json.loads(raw_payload)

    # Only handle block_actions (button clicks) — ignore other event types
    if payload.get("type") != "block_actions":
        return {"ok": True}

    action = payload["actions"][0]
    action_id: str = action["action_id"]          # "approve" or "reject"
    review_id: int = int(action["value"])          # PendingReview.id
    message_ts: str = payload["message"]["ts"]
    channel_id: str = payload["container"]["channel_id"]
    user_id: str = payload["user"]["id"]

    # --- Look up the PendingReview record ---
    result = await db.execute(
        select(PendingReview).where(PendingReview.id == review_id)
    )
    review: PendingReview | None = result.scalar_one_or_none()

    if not review:
        raise HTTPException(
            status_code=404, detail=f"PendingReview {review_id} not found"
        )

    # Guard against double-clicks — already actioned
    if review.status != ReviewStatus.PENDING:
        await update_message(
            channel_id,
            message_ts,
            f"Already {review.status.value.lower()} — no further action taken.",
        )
        return {"ok": True}

    # --- Approve path ---
    if action_id == "approve":
        item = ActionItem(
            title=review.title,
            description=review.description or "",
            assignee=review.assignee,
            priority="MEDIUM",
            confidence=review.confidence,
        )
        ticket_key = await create_ticket(item)

        review.status = ReviewStatus.APPROVED
        await db.commit()

        await update_message(
            channel_id,
            message_ts,
            f"Approved by <@{user_id}> — Jira ticket *{ticket_key}* created.",
        )

    # --- Reject path ---
    elif action_id == "reject":
        review.status = ReviewStatus.REJECTED
        await db.commit()

        await update_message(
            channel_id,
            message_ts,
            f"Rejected by <@{user_id}> — no Jira ticket created.",
        )

    return {"ok": True}
