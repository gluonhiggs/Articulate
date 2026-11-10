"""Sentence-level rewrites for a spoken interview answer.

The sentences are chosen by backend.services.sentences; this module only asks the
assist model to say each one better, and refuses anything that drifts from the
candidate's own words.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

from backend.config import get_assist_model, get_settings
from backend.constants import PROMPTS_DIR
from backend.services import llm_client
from backend.services.sentences import REASON_LABELS

logger = logging.getLogger(__name__)

SENTENCES_SCHEMA = {
    "type": "object",
    "properties": {
        "rewrites": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "improved": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["index", "improved", "note"],
            },
        }
    },
    "required": ["rewrites"],
}

MAX_TOKENS = 4096
# A rewrite longer than this multiple of the original is padding, not a rewrite.
MAX_GROWTH = 1.4


def _load_prompt() -> str:
    with open(PROMPTS_DIR / "interview_sentences.txt", "r", encoding="utf-8") as handle:
        return handle.read()


def _format_sentences(sentences: Sequence[dict[str, Any]]) -> str:
    lines = []
    for position, sentence in enumerate(sentences, start=1):
        reasons = ", ".join(REASON_LABELS.get(reason, reason) for reason in sentence["reasons"])
        lines.append(f"{position}. [{reasons}] {sentence['text']}")
    return "\n".join(lines)


def _accept(original: str, improved: str) -> bool:
    improved = improved.strip()
    if not improved or improved == original.strip():
        return False
    return len(improved) <= len(original) * MAX_GROWTH


async def generate_sentence_fixes(
    question_text: str,
    sentences: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return [{original, improved, note, reasons}] for the sentences worth rewriting.

    Rewrites the model declined, returned unchanged or padded out are dropped rather
    than shown, so an empty list means "nothing useful came back", not an error.
    """
    if not sentences:
        return []

    settings = get_settings()
    prompt = (
        _load_prompt()
        .replace("{question_text}", question_text)
        .replace("{sentences}", _format_sentences(sentences))
    )

    data = await llm_client.generate_json(
        base_url=settings.llm_base_url,
        model=get_assist_model(),
        prompt=prompt,
        api_key=settings.llm_api_key,
        schema=SENTENCES_SCHEMA,
        schema_name="interview_sentence_rewrites",
        temperature=0.3,
        max_tokens=MAX_TOKENS,
        timeout=120.0,
        reasoning_effort=settings.llm_reasoning_effort,
    )

    rewrites = data.get("rewrites")
    if not isinstance(rewrites, list):
        raise ValueError("The rewrite came back in an unexpected shape. Please try again.")

    by_position = {
        rewrite["index"]: rewrite
        for rewrite in rewrites
        if isinstance(rewrite, dict) and isinstance(rewrite.get("index"), int)
    }

    fixes: list[dict[str, Any]] = []
    dropped = 0
    for position, sentence in enumerate(sentences, start=1):
        rewrite = by_position.get(position)
        improved = rewrite.get("improved") if isinstance(rewrite, dict) else None
        if not isinstance(improved, str) or not _accept(sentence["text"], improved):
            dropped += 1
            continue
        note = rewrite.get("note")
        fixes.append(
            {
                "original": sentence["text"],
                "improved": improved.strip(),
                "note": note.strip() if isinstance(note, str) else "",
                "reasons": list(sentence["reasons"]),
            }
        )

    logger.info(
        "INTERVIEW SENTENCES: asked for %d, kept %d, dropped %d (unchanged, empty or padded)",
        len(sentences),
        len(fixes),
        dropped,
    )
    return fixes
