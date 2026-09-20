from __future__ import annotations

import logging
from typing import Any, Dict

from backend.config import get_assist_model, get_settings
from backend.constants import PROMPTS_DIR
from backend.services import llm_client

logger = logging.getLogger(__name__)

IMPROVE_SCHEMA = {
    "type": "object",
    "properties": {
        "improved_text": {"type": "string"},
        "explanation": {"type": "string"},
    },
    "required": ["improved_text", "explanation"],
}
# Generous, because a thinking model spends part of the budget before the answer starts.
MAX_TOKENS = 8192


def _load_prompt() -> str:
    prompt_file = PROMPTS_DIR / "improve.txt"
    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read()


def _build_prompt(
    question_text: str,
    transcript: str,
    current_band: float,
    target_band: float,
) -> str:
    template = _load_prompt()
    return (
        template.replace("{question_text}", question_text)
        .replace("{transcript}", transcript)
        .replace("{current_band}", str(current_band))
        .replace("{target_band}", str(target_band))
    )


async def generate_improvement(
    question_text: str,
    transcript: str,
    current_band: float,
    target_band: float,
) -> Dict[str, Any]:
    """
    Call the LLM to rewrite the response at a higher band level.

    Raises RuntimeError (LLMOutputError when the model truncated or broke the JSON)
    or ValueError, which the API turns into a 502, rather than ever returning
    partial model output as the rewrite.
    """
    settings = get_settings()
    prompt = _build_prompt(question_text, transcript, current_band, target_band)

    try:
        data = await llm_client.generate_json(
            base_url=settings.llm_base_url,
            model=get_assist_model(),
            prompt=prompt,
            api_key=settings.llm_api_key,
            schema=IMPROVE_SCHEMA,
            schema_name="ielts_improved_response",
            temperature=0.4,
            max_tokens=MAX_TOKENS,
            timeout=120.0,
            reasoning_effort=settings.llm_reasoning_effort,
        )
    except RuntimeError as exc:
        logger.exception("LLM request failed for improve: %s", exc)
        raise

    improved = data.get("improved_text")
    if not isinstance(improved, str) or not improved.strip():
        raise ValueError("The rewrite came back empty. Please try again.")

    explanation = data.get("explanation")
    return {
        "improved_text": improved.strip(),
        "explanation": explanation if isinstance(explanation, str) else "",
    }
