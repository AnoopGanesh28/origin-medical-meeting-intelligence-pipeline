"""
Phase 9: Jira Client

Creates Jira Tasks asynchronously via the Jira Cloud REST API v3.
Retries on 429 (rate limit), 500, 502, 503 (transient server errors).
"""
import base64
import logging

import aiohttp
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.schemas import ActionItem

logger = logging.getLogger(__name__)

# HTTP status codes that indicate a transient failure worth retrying
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503}

# Jira priority labels mapped from our internal priority strings
_PRIORITY_MAP = {"HIGH": "High", "MEDIUM": "Medium", "LOW": "Low"}


class JiraRetryableError(Exception):
    """Raised on retryable Jira HTTP errors — triggers tenacity retry."""
    pass


class JiraError(Exception):
    """Raised on non-retryable Jira errors (bad credentials, bad request, etc.)."""
    pass


def _auth_header() -> str:
    """Build the Basic auth header from Jira email + API token."""
    credentials = f"{settings.JIRA_EMAIL}:{settings.JIRA_API_TOKEN}"
    encoded = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
    return f"Basic {encoded}"


def _build_jira_payload(item: ActionItem) -> dict:
    """Construct the Jira REST API issue creation payload."""
    jira_priority = _PRIORITY_MAP.get(item.priority.upper(), "Medium")

    # Jira Cloud requires Atlassian Document Format (ADF) for description
    description_parts = []
    if item.assignee:
        description_parts.append(f"Suggested assignee: {item.assignee}")
    description_parts.append(item.description)
    full_description = "\n\n".join(description_parts)

    return {
        "fields": {
            "project": {"key": settings.JIRA_PROJECT_KEY},
            "summary": item.title,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": full_description}],
                    }
                ],
            },
            "issuetype": {"name": "Task"},
            "priority": {"name": jira_priority},
        }
    }


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(JiraRetryableError),
    reraise=True,
)
async def create_ticket(item: ActionItem) -> str:
    """
    Create a Jira Task from an ActionItem.

    Args:
        item: The ActionItem to create a ticket for.

    Returns:
        The Jira ticket key (e.g. 'PROJ-42').

    Raises:
        JiraRetryableError: On 429/500/502/503 — retried up to 3 times.
        JiraError:          On non-retryable failures (auth, bad request, etc.).
    """
    url = f"{settings.JIRA_BASE_URL.rstrip('/')}/rest/api/3/issue"
    headers = {
        "Authorization": _auth_header(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = _build_jira_payload(item)

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as resp:
            if resp.status in _RETRYABLE_STATUS_CODES:
                text = await resp.text()
                raise JiraRetryableError(
                    f"Jira returned retryable status {resp.status}: {text[:200]}"
                )

            if resp.status not in (200, 201):
                text = await resp.text()
                raise JiraError(
                    f"Jira ticket creation failed (HTTP {resp.status}): {text[:500]}"
                )

            data = await resp.json()
            ticket_key: str = data["key"]

    logger.info("Created Jira ticket %s | '%s' [%s]", ticket_key, item.title, item.priority)
    return ticket_key
