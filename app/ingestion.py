"""
Phase 6: Transcript Ingestion

Provides load_transcript() to safely read a meeting transcript from disk.
Raises descriptive custom exceptions so the caller always knows exactly what went wrong.
"""
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class TranscriptNotFoundError(FileNotFoundError):
    """Raised when no file exists at the given path."""
    pass


class TranscriptEmptyError(ValueError):
    """Raised when the file exists but contains no usable content."""
    pass


def load_transcript(path: str) -> str:
    """
    Read a meeting transcript from the filesystem.

    Args:
        path: Absolute or relative path to the transcript text file.

    Returns:
        The transcript text, stripped of leading/trailing whitespace.

    Raises:
        TranscriptNotFoundError: File does not exist at the given path.
        TranscriptEmptyError:    File exists but is empty or whitespace-only.
    """
    transcript_path = Path(path)

    if not transcript_path.exists():
        raise TranscriptNotFoundError(
            f"Transcript file not found: '{path}'. "
            "Verify the path and ensure the file is present before submitting."
        )

    if not transcript_path.is_file():
        raise TranscriptNotFoundError(
            f"Path exists but is not a file: '{path}'."
        )

    content = transcript_path.read_text(encoding="utf-8").strip()

    if not content:
        raise TranscriptEmptyError(
            f"Transcript file is empty or contains only whitespace: '{path}'."
        )

    logger.info("Successfully loaded transcript from '%s' (%d chars)", path, len(content))
    return content
