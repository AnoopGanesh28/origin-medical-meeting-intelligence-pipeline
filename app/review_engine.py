"""
Phase 8: Confidence Evaluation Engine

Determines whether an action item is safe to auto-process (create Jira ticket directly)
or must be routed to Slack for human review.

Core principle: Automate what is clear. Escalate what is ambiguous.
"""
from app.config import settings
from app.schemas import ActionItem

# Words in a title that signal vague/collective ownership — triggers human review
_AMBIGUOUS_OWNERSHIP_WORDS: frozenset[str] = frozenset({"someone", "somebody", "team"})


def requires_review(item: ActionItem) -> bool:
    """
    Return True if this action item must be sent to Slack for human review.

    Review is required if ANY of the following are true:
      1. confidence < CONFIDENCE_THRESHOLD  — Gemini is not certain this is a real task
      2. assignee is None                   — No individual is clearly responsible
      3. title contains an ambiguous word   — "someone", "somebody", or "team"

    Args:
        item: The ActionItem extracted from the meeting transcript.

    Returns:
        True  → route to Slack review queue
        False → safe to auto-create Jira ticket

    Examples:
        >>> requires_review(ActionItem(title="Someone should validate model weights", ...))
        True
        >>> requires_review(ActionItem(title="Rahul will validate model weights", assignee="Rahul", confidence=0.95, ...))
        False
    """
    # Rule 1: Low confidence — Gemini is uncertain this is a real committed task
    if item.confidence < settings.CONFIDENCE_THRESHOLD:
        return True

    # Rule 2: No assignee — nobody is clearly responsible
    if item.assignee is None:
        return True

    # Rule 3: Ambiguous ownership language in the title (word-level match, case-insensitive)
    title_words = set(item.title.lower().split())
    if title_words & _AMBIGUOUS_OWNERSHIP_WORDS:
        return True

    return False
