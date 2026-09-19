from __future__ import annotations

import logging
import random
from typing import Any, Dict, List, Optional

from backend.config import get_settings
from backend.constants import PROMPTS_DIR
from backend.services import llm_client

logger = logging.getLogger(__name__)

_VOCAB_FOCUS_ROTATION = [
    "idioms and set phrases",
    "phrasal verbs",
    "collocations (adjective+noun or verb+noun pairs)",
    "advanced single words",
    "discourse markers and linking expressions",
    "hedging and opinion expressions (tend to, it could be argued, somewhat)",
    "verb phrases and action expressions",
    "expressions native speakers use naturally but learners rarely know",
    "expressions useful for Part 3 abstract discussions",
    "words and phrases for describing feelings and reactions",
    "expressions for comparing and contrasting",
    "expressions for describing habits and routines",
]

SAMPLE_ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "sample_answer": {"type": "string"},
        "key_phrases": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["sample_answer", "key_phrases"],
}

TOPIC_VOCAB_SCHEMA = {
    "type": "object",
    "properties": {
        "vocabulary": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "term": {"type": "string"},
                    "type": {"type": "string"},
                    "definition": {"type": "string"},
                    "example": {"type": "string"},
                },
                "required": ["term", "type", "definition", "example"],
            },
        }
    },
    "required": ["vocabulary"],
}
# Generous, because a thinking model spends part of the budget before the answer starts.
MAX_TOKENS = 8192


def _load_prompt(name: str) -> str:
    with open(PROMPTS_DIR / name, "r", encoding="utf-8") as f:
        return f.read()


async def generate_sample_answer(
    question_text: str,
    part: str,
    target_band: float = 7.0,
) -> Dict[str, Any]:
    """
    Generate a sample IELTS response at the target band level.

    Raises RuntimeError or ValueError, which the API turns into a 502, rather than
    passing partial model output off as a sample answer.
    """
    settings = get_settings()
    template = _load_prompt("sample_answer.txt")
    word_count = "40-60" if part == "1" else "150-200" if part == "2" else "60-90"
    prompt = (
        template.replace("{question_text}", question_text)
        .replace("{target_band}", str(target_band))
        .replace("{part}", f"Part {part}")
        .replace("{word_count}", word_count)
    )

    data = await llm_client.generate_json(
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        prompt=prompt,
        api_key=settings.llm_api_key,
        schema=SAMPLE_ANSWER_SCHEMA,
        schema_name="ielts_sample_answer",
        temperature=0.6,
        max_tokens=MAX_TOKENS,
        timeout=120.0,
        reasoning_effort=settings.llm_reasoning_effort,
    )

    answer = data.get("sample_answer")
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("The sample answer came back empty. Please try again.")
    phrases = data.get("key_phrases")
    return {
        "sample_answer": answer.strip(),
        "key_phrases": [str(p) for p in phrases] if isinstance(phrases, list) else [],
    }


async def generate_topic_vocab(
    question_text: str,
    exclude_terms: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generate topic vocabulary for an IELTS question.

    exclude_terms: terms already shown to the learner - model is instructed to avoid them.
    Raises RuntimeError or ValueError, which the API turns into a 502, rather than
    returning a half-finished vocabulary list.
    """
    settings = get_settings()
    template = _load_prompt("topic_vocab.txt")
    focus = random.choice(_VOCAB_FOCUS_ROTATION)
    exclude_str = ", ".join(exclude_terms) if exclude_terms else "none"
    prompt = (
        template.replace("{question_text}", question_text)
        .replace("{focus}", focus)
        .replace("{exclude_terms}", exclude_str)
    )

    data = await llm_client.generate_json(
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        prompt=prompt,
        api_key=settings.llm_api_key,
        schema=TOPIC_VOCAB_SCHEMA,
        schema_name="ielts_topic_vocab",
        temperature=0.4,
        max_tokens=MAX_TOKENS,
        timeout=120.0,
        reasoning_effort=settings.llm_reasoning_effort,
    )

    items = data.get("vocabulary")
    vocabulary = [
        {
            "term": str(item.get("term", "")),
            "type": str(item.get("type", "")),
            "definition": str(item.get("definition", "")),
            "example": str(item.get("example", "")),
        }
        for item in (items if isinstance(items, list) else [])
        if isinstance(item, dict) and str(item.get("term", "")).strip()
    ]
    if not vocabulary:
        raise ValueError("No vocabulary came back from the model. Please try again.")
    return {"vocabulary": vocabulary}
