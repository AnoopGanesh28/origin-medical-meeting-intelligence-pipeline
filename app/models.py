"""
Phase 4: Database Models

Defines the two ORM models that persist workflow state:
  - ProcessedMeeting: idempotency guard — prevents the same transcript being processed twice
  - PendingReview: human review queue — tracks ambiguous action items awaiting Slack approval
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReviewStatus(str, enum.Enum):
    """Lifecycle states for a PendingReview record."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ProcessedMeeting(Base):
    """
    Records every successfully processed transcript.
    `transcript_hash` (SHA256) is UNIQUE — if the same transcript is submitted
    again, the pipeline returns the cached result instead of re-processing.
    """
    __tablename__ = "processed_meetings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transcript_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<ProcessedMeeting id={self.id} hash={self.transcript_hash[:8]}...>"


class PendingReview(Base):
    """
    Stores action items that were flagged as ambiguous and routed to Slack
    for human approval. `slack_message_ts` links this record to the exact
    Slack message so we can update it when the user clicks Approve/Reject.
    """
    __tablename__ = "pending_reviews"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[ReviewStatus] = mapped_column(
        SAEnum(ReviewStatus, name="review_status"),
        default=ReviewStatus.PENDING,
        nullable=False,
    )
    slack_message_ts: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<PendingReview id={self.id} title='{self.title[:30]}' status={self.status}>"
