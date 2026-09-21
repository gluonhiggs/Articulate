"""
Attempt lifecycle statuses.

The single source of truth for the status column, the API contract and the
frontend copy in frontend/src/types/attemptStatus.ts, which
tests/test_attempt_status.py keeps in sync.
"""

from __future__ import annotations

from enum import StrEnum


class AttemptStatus(StrEnum):
    PROCESSING = "processing"
    TRANSCRIBING = "transcribing"
    SCORING = "scoring"
    READY = "ready"
    FAILED = "failed"
    FAILED_TRANSCRIPTION = "failed:transcription"
    FAILED_EMPTY_AUDIO = "failed:empty_audio"
    FAILED_SCORING = "failed:scoring"
    FAILED_QUOTA = "failed:quota"


PROCESSING_STATUSES = frozenset({AttemptStatus.PROCESSING, AttemptStatus.TRANSCRIBING, AttemptStatus.SCORING})

STATUS_MAX_LENGTH = 32


def is_processing(status: str) -> bool:
    return status in PROCESSING_STATUSES


def is_failed(status: str) -> bool:
    """Prefix match, so a status added on the backend still reads as a failure to older code."""
    return status == AttemptStatus.FAILED or status.startswith("failed:")
