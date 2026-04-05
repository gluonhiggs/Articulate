from __future__ import annotations

import json
import logging
from typing import Any, Dict

from backend.config import get_settings
from backend.constants import PROMPTS_DIR
from backend.services import llm_client

logger = logging.getLogger(__name__)


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


def _parse_response(raw: str) -> Dict[str, Any]:
    """Extract improved_text and explanation from LLM JSON response."""
    if not raw or not raw.strip():
        raise ValueError("LLM returned empty response for improve request")

    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end <= start:
        # No JSON found - treat the whole text as the improved version
        logger.warning("LLM response contained no JSON, using raw text as improved_text.")
        return {"improved_text": raw.strip(), "explanation": ""}

    json_str = raw[start:end]
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        # JSON parse failed - treat as raw text
        logger.warning("LLM returned invalid JSON for improve, using raw text.")
        return {"improved_text": raw.strip(), "explanation": ""}

    improved = data.get("improved_text", "")
    if not improved:
        raise ValueError("LLM returned JSON without improved_text field")

    return {
        "improved_text": improved,
        "explanation": data.get("explanation", ""),
    }


async def generate_improvement(
    question_text: str,
    transcript: str,
    current_band: float,
    target_band: float,
) -> Dict[str, Any]:
    """Call the LLM to rewrite the response at a higher band level."""
    settings = get_settings()
    prompt = _build_prompt(question_text, transcript, current_band, target_band)

    try:
        raw_text = await llm_client.generate(
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            prompt=prompt,
            api_key=settings.llm_api_key,
            temperature=0.4,
            num_predict=1024,
            timeout=120.0,
        )
    except RuntimeError as exc:
        logger.exception("LLM request failed for improve: %s", exc)
        raise

    return _parse_response(raw_text)
