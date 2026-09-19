"""Prompt text and JSON schemas for the interview grader, verifier and drafter LLM calls."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Iterable, Sequence

from backend.constants import PROMPTS_DIR

ROLE_LABELS = {
    "swe": "software engineer",
    "be": "backend engineer",
    "fe": "frontend engineer",
    "de": "data engineer",
    "da": "data analyst",
    "ds": "data scientist",
    "other": "software / IT",
}
IMPORTANCE_BY_WEIGHT = {3: "core", 2: "supporting", 1: "detail"}
WEIGHT_BY_IMPORTANCE = {label: weight for weight, label in IMPORTANCE_BY_WEIGHT.items()}

PROPOSER_VERDICTS = ["covered", "partial", "missing", "incorrect"]
VERIFIER_VERDICTS = ["supported", "partial", "not_supported", "contradicted"]

_PLACEHOLDER_RE = re.compile(r"\{\{([A-Z_]+)\}\}")
_BLOCK_MARKER_RE = re.compile(r"[<>]{3,}")


@lru_cache(maxsize=None)
def _template(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def as_data(text: str) -> str:
    """Untrusted text for a delimited prompt block, unable to close the block early."""
    return _BLOCK_MARKER_RE.sub(" ", text).strip() or "(none)"


def _fill(template_name: str, values: dict[str, str]) -> str:
    # Single pass, so placeholder-like text inside a value is never substituted again.
    return _PLACEHOLDER_RE.sub(lambda m: values[m.group(1)], _template(template_name))


def _one_line(text: str) -> str:
    return " ".join(text.split())


def build_grade_prompt(
    *,
    role: str,
    level: str,
    question: str,
    key_points: Sequence[tuple[str, int, str]],
    misconceptions: Sequence[tuple[str, str]],
    transcript: str,
) -> str:
    """key_points: (uid, weight, text) in the order to show; misconceptions: (uid, text)."""
    return _fill(
        "interview_grade.txt",
        {
            "ROLE": ROLE_LABELS.get(role, role),
            "LEVEL": level,
            "QUESTION": as_data(question),
            "KEY_POINTS": as_data(
                "\n".join(
                    f"{uid} | {IMPORTANCE_BY_WEIGHT[weight]} | {_one_line(text)}" for uid, weight, text in key_points
                )
            ),
            "MISCONCEPTIONS": as_data("\n".join(f"{uid} | {_one_line(text)}" for uid, text in misconceptions)),
            "TRANSCRIPT": as_data(transcript),
        },
    )


def build_verify_prompt(
    *,
    question: str,
    transcript: str,
    key_point_claims: Sequence[tuple[str, str, str]],
    misconception_claims: Sequence[tuple[str, str, str]],
) -> str:
    """Claims are (uid, text, quote)."""
    return _fill(
        "interview_verify.txt",
        {
            "QUESTION": as_data(question),
            "TRANSCRIPT": as_data(transcript),
            "KEY_POINT_CLAIMS": as_data(
                "\n".join(f'{uid} | {_one_line(text)} | "{_one_line(quote)}"' for uid, text, quote in key_point_claims)
            ),
            "MISCONCEPTION_CLAIMS": as_data(
                "\n".join(
                    f'{uid} | {_one_line(text)} | "{_one_line(quote)}"' for uid, text, quote in misconception_claims
                )
            ),
        },
    )


def build_draft_prompt(
    *,
    role: str,
    level: str,
    job_description: str,
    topic: str,
    count: int,
    sources: str,
    existing_questions: Iterable[str],
) -> str:
    return _fill(
        "interview_draft.txt",
        {
            "ROLE": ROLE_LABELS.get(role, role),
            "LEVEL": level,
            "JOB_DESCRIPTION": as_data(job_description),
            "TOPIC": as_data(topic),
            "SOURCES": as_data(sources),
            "EXISTING_QUESTIONS": as_data("\n".join(f"- {_one_line(text)}" for text in existing_questions)),
            "COUNT": str(count),
        },
    )


def _id_schema(ids: Sequence[str]) -> dict:
    return {"type": "string", "enum": list(ids)} if ids else {"type": "string"}


def grade_schema(key_point_uids: Sequence[str], misconception_uids: Sequence[str]) -> dict:
    # Quote and reason come before the verdict so the model commits to evidence first.
    return {
        "type": "object",
        "properties": {
            "key_points": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": _id_schema(key_point_uids),
                        "quote": {"type": "string"},
                        "reason": {"type": "string"},
                        "verdict": {"type": "string", "enum": PROPOSER_VERDICTS},
                    },
                    "required": ["id", "quote", "reason", "verdict"],
                },
            },
            "misconceptions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": _id_schema(misconception_uids),
                        "quote": {"type": "string"},
                        "stated": {"type": "boolean"},
                    },
                    "required": ["id", "quote", "stated"],
                },
            },
            "content_tips": {"type": "array", "items": {"type": "string"}},
            "english_tip": {"type": "string"},
        },
        "required": ["key_points", "misconceptions", "content_tips", "english_tip"],
    }


def verify_schema(key_point_uids: Sequence[str], misconception_uids: Sequence[str]) -> dict:
    """Strict-mode schema: every object closed and every property required."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "key_points": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": _id_schema(key_point_uids),
                        "verdict": {"type": "string", "enum": VERIFIER_VERDICTS},
                    },
                    "required": ["id", "verdict"],
                },
            },
            "misconceptions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": _id_schema(misconception_uids),
                        "confirmed": {"type": "boolean"},
                    },
                    "required": ["id", "confirmed"],
                },
            },
        },
        "required": ["key_points", "misconceptions"],
    }


_DRAFT_KEY_POINT = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "importance": {"type": "string", "enum": list(WEIGHT_BY_IMPORTANCE)},
        "source_quote": {"type": "string"},
    },
    "required": ["text", "importance", "source_quote"],
}
_DRAFT_MISCONCEPTION = {
    "type": "object",
    "properties": {"text": {"type": "string"}, "correction": {"type": "string"}},
    "required": ["text", "correction"],
}

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "answer_seconds": {"type": "integer"},
                    "key_points": {"type": "array", "items": _DRAFT_KEY_POINT},
                    "misconceptions": {"type": "array", "items": _DRAFT_MISCONCEPTION},
                    "follow_ups": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "answer_seconds": {"type": "integer"},
                                "trigger_key_point_index": {"type": "integer"},
                                "key_points": {"type": "array", "items": _DRAFT_KEY_POINT},
                                "misconceptions": {"type": "array", "items": _DRAFT_MISCONCEPTION},
                            },
                            "required": [
                                "text",
                                "answer_seconds",
                                "trigger_key_point_index",
                                "key_points",
                                "misconceptions",
                            ],
                        },
                    },
                },
                "required": ["text", "answer_seconds", "key_points", "misconceptions", "follow_ups"],
            },
        }
    },
    "required": ["questions"],
}
