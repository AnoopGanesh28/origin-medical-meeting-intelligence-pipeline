"""
Phase 7: Gemini Extraction Engine

Calls Gemini 2.5 Flash with the meeting transcript and returns a fully validated
MeetingExtraction object. Retries up to 3 times on transient API failures.

Uses the google-genai SDK (google.genai), the current supported Gemini SDK.
"""
import logging

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.schemas import MeetingExtraction

logger = logging.getLogger(__name__)

# Prompt instructs Gemini exactly how to populate each field of MeetingExtraction
EXTRACTION_PROMPT_TEMPLATE = """\
You are an expert medical meeting analyst. Carefully analyse the transcript below \
and extract every distinct, actionable task that was committed to during the meeting.

For each action item produce:
- title        : Short imperative task (start with a verb, max ~10 words)
- description  : Full context — what needs doing, why, and any stated deadline
- assignee     : The specific named person responsible. Use null if no individual \
is clearly named or if ownership is vague (e.g. "someone", "the team").
- priority     : Exactly one of "HIGH", "MEDIUM", or "LOW"
- confidence   : Float 0.0-1.0 — how confident you are this is a real, \
committed, actionable task (not just a suggestion or background discussion)

Also provide a concise meeting_summary (2-3 sentences) covering the key decisions made.

TRANSCRIPT:
{transcript}
"""

# Only retry on transient server-side errors — not on config/auth/parse errors
_RETRYABLE_EXCEPTIONS = (
    genai_errors.ServerError,   # 5xx — transient server failures
    genai_errors.APIError,      # generic transient API errors
)


def _get_client() -> genai.Client:
    """Return a configured Gemini async client."""
    return genai.Client(api_key=settings.GEMINI_API_KEY)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
    reraise=True,
)
async def _call_gemini(client: genai.Client, prompt: str) -> str:
    """
    Make the raw async API call. This is the only function wrapped in retry logic —
    client creation and response parsing are not retried (they are not transient).
    """
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=MeetingExtraction,
        ),
    )

    if not response.text:
        raise ValueError("Gemini returned an empty response — cannot parse extraction.")

    return response.text


async def extract_action_items(transcript: str) -> MeetingExtraction:
    """
    Convert a raw meeting transcript into a structured MeetingExtraction.

    Args:
        transcript: The full text of the meeting transcript.

    Returns:
        A validated MeetingExtraction containing the meeting summary and action items.

    Raises:
        google.genai.errors.ServerError:  On persistent API failure after 3 retries.
        pydantic.ValidationError:         If Gemini returns JSON that doesn't match the schema.
    """
    client = _get_client()
    prompt = EXTRACTION_PROMPT_TEMPLATE.format(transcript=transcript)

    logger.info("Calling Gemini 2.5 Flash for structured extraction...")

    raw_json = await _call_gemini(client, prompt)

    # Validate and parse — if Gemini violated the schema, Pydantic will raise ValidationError
    extraction = MeetingExtraction.model_validate_json(raw_json.strip())

    logger.info(
        "Extraction complete: %d action item(s) extracted, summary: %d chars",
        len(extraction.action_items),
        len(extraction.meeting_summary),
    )

    return extraction
