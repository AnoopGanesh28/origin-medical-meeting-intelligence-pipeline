"""
Phase 5: Pydantic Schemas

Defines the structured data contracts for all AI responses.
These schemas serve two purposes:
  1. Passed as `response_schema` to Gemini to enforce structured JSON output
  2. Validate and parse every Gemini response before it enters the pipeline
"""
from typing import Literal
from pydantic import BaseModel, Field


class ActionItem(BaseModel):
    """
    A single action item extracted from a meeting transcript.

    Fields:
        title       — Short, imperative task title (e.g. "Update model weights")
        description — Full context and details of what needs to be done
        assignee    — Person responsible. None if unclear or unassigned.
        priority    — One of: "HIGH", "MEDIUM", "LOW"
        confidence  — Gemini's confidence that this is a real, actionable task (0.0–1.0)
    """
    title: str
    description: str
    assignee: str | None = None
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    confidence: float = Field(ge=0.0, le=1.0)


class MeetingExtraction(BaseModel):
    """
    The complete structured output from Gemini for a single meeting transcript.

    Fields:
        meeting_summary — A concise paragraph summarising the meeting's key decisions
        action_items    — All action items extracted from the transcript
    """
    meeting_summary: str = Field(min_length=1)
    action_items: list[ActionItem]
