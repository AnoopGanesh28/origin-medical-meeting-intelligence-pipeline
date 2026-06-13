"""
Shared utility functions used across the pipeline.
"""
import hashlib


def compute_transcript_hash(transcript: str) -> str:
    """
    Compute a SHA256 hex digest of the transcript text.
    Used to detect duplicate submissions — if the same transcript
    is submitted again, the pipeline returns the cached result.

    Args:
        transcript: The raw transcript string.

    Returns:
        64-character lowercase hex string (SHA256).
    """
    return hashlib.sha256(transcript.encode("utf-8")).hexdigest()
