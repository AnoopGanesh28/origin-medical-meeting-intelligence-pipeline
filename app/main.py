"""
Origin Medical Meeting Intelligence Pipeline
FastAPI application entry point.

Phase 11: Adds startup database initialization and POST /slack/interactions
endpoint for handling Slack button clicks (Approve / Reject).
"""
import hashlib
import hmac
import json
import logging
import time
import urllib.parse
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db, init_db
from app.extraction_agent import extract_action_items
from app.ingestion import load_transcript
from app.jira_client import create_ticket
from app.logging_config import setup_logging
from app.models import PendingReview, ProcessedMeeting, ReviewStatus
from app.review_engine import requires_review
from app.schemas import ActionItem
from app.slack_client import post_review_request, post_summary, update_message
from app.utils import compute_transcript_hash

# Initialize logging globally
setup_logging()
logger = logging.getLogger(__name__)


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Utility"])
async def health_check():
    """Liveness probe — returns OK if the server is running."""
    return {"status": "ok", "version": "0.1.0"}


# ---------------------------------------------------------------------------
# Core Pipeline — Phase 12
# ---------------------------------------------------------------------------

class ProcessMeetingRequest(BaseModel):
    transcript_text: str


@app.post("/process-meeting", tags=["Pipeline"])
async def process_meeting(
    request_data: ProcessMeetingRequest,
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
):
    """
    Main orchestration workflow.
    Loads transcript, extracts tasks, filters ambiguity, creates Jira tickets,
    and asks for human approval in Slack for ambiguous tasks.
    """
    if x_api_key != settings.PIPELINE_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    logger.info("Processing meeting transcript directly from text payload (%d chars)", len(request_data.transcript_text))

    # 1. Get transcript
    transcript = request_data.transcript_text
    if not transcript or not transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript text cannot be empty.")

    # 2. Hash transcript
    transcript_hash = compute_transcript_hash(transcript)

    # 3. Check idempotent DB record
    result = await db.execute(
        select(ProcessedMeeting).where(ProcessedMeeting.transcript_hash == transcript_hash)
    )
    existing = result.scalar_one_or_none()
    if existing:
        logger.info("Duplicate transcript %s. Returning cached summary.", transcript_hash)
        return {
            "summary": existing.summary,
            "tickets_created": 0,
            "pending_review": 0,
            "status": "already_processed"
        }

    # 4. Extract action items
    extraction = await extract_action_items(transcript)

    # 5. Split items into auto vs review
    tickets_created = []
    pending_titles = []

    for item in extraction.action_items:
        if requires_review(item):
            # 7. Create PendingReview record
            pending = PendingReview(
                title=item.title,
                description=item.description,
                assignee=item.assignee,
                confidence=item.confidence,
                status=ReviewStatus.PENDING
            )
            db.add(pending)
            await db.flush()  # We need pending.id for the slack button
            
            # 8. Post Slack review request
            ts = await post_review_request(item, pending.id)
            pending.slack_message_ts = ts
            pending_titles.append(item.title)
        else:
            # 6. Auto-create Jira ticket
            ticket_key = await create_ticket(item)
            tickets_created.append(ticket_key)

    # 9. Generate Slack summary
    await post_summary(extraction, tickets_created, pending_titles)

    # 10. Store ProcessedMeeting
    processed = ProcessedMeeting(
        transcript_hash=transcript_hash,
        summary=extraction.meeting_summary
    )
    db.add(processed)
    
    await db.commit()

    logger.info("Meeting processed successfully.")
    return {
        "summary": extraction.meeting_summary,
        "tickets_created": len(tickets_created),
        "pending_review": len(pending_titles),
        "status": "processed"
    }


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
