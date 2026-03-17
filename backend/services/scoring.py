from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from backend.config import get_settings
from backend.constants import PROMPTS_DIR
from backend.services import ollama_client

logger = logging.getLogger(__name__)


def _load_prompt(part: str) -> str:
    """Load the appropriate prompt template based on IELTS part."""
    if part == "2":
        prompt_file = PROMPTS_DIR / "score_part2.txt"
    elif part == "3":
        prompt_file = PROMPTS_DIR / "score_part3.txt"
    else:
        prompt_file = PROMPTS_DIR / "score_part1.txt"

    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")


def _build_prompt(
    question_text: str,
    part: str,
    transcript: str,
    flagged_words: List[str],
) -> str:
    """Render the prompt template with actual values."""
    template = _load_prompt(part)
    flagged_str = ", ".join(flagged_words) if flagged_words else "none"
    return (
        template.replace("{question_text}", question_text)
        .replace("{transcript}", transcript)
        .replace("{flagged_words}", flagged_str)
    )


def _clamp_band(value: Any) -> Optional[float]:
    """Clamp a band score to the valid 0-9 range in 0.5 steps."""
    try:
        v = float(value)
        v = max(0.0, min(9.0, v))
        return round(v * 2) / 2
    except (TypeError, ValueError):
        return None


def _parse_llm_response(raw: str) -> Dict[str, Any]:
    """
    Parse the LLM's raw text response into a structured scoring dict.
    Falls back gracefully if JSON is malformed.
    """
    # Try to extract a JSON object from the response
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start != -1 and end > start:
        json_str = raw[start:end]
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("LLM returned invalid JSON, using fallback scoring.")
            data = {}
    else:
        logger.warning("LLM response contained no JSON object, using fallback scoring.")
        data = {}

    fluency = _clamp_band(data.get("fluency"))
    vocabulary = _clamp_band(data.get("vocabulary"))
    grammar = _clamp_band(data.get("grammar"))
    pronunciation = _clamp_band(data.get("pronunciation"))
    feedback_text = data.get("feedback_text", "")
    error_highlights = data.get("error_highlights", [])

    if not isinstance(feedback_text, str):
        feedback_text = str(feedback_text)

    if not isinstance(error_highlights, list):
        error_highlights = []

    # Validate each error highlight has required fields
    cleaned_highlights = []
    for highlight in error_highlights:
        if isinstance(highlight, dict) and "word" in highlight:
            # Prefer "correction" field; fall back to "suggestion" for backward compat
            correction = highlight.get("correction")
            if correction is None:
                correction = highlight.get("suggestion", "")
            cleaned_highlights.append(
                {
                    "word": str(highlight.get("word", "")),
                    "type": str(highlight.get("type", "error")),
                    "correction": str(correction),
                    "explanation": str(highlight.get("explanation", "")),
                    # Keep suggestion as alias for backward compat
                    "suggestion": str(correction),
                }
            )

    # Compute overall band score as mean of four criteria
    scores = [s for s in [fluency, vocabulary, grammar, pronunciation] if s is not None]
    if scores:
        mean_score = sum(scores) / len(scores)
        overall = round(mean_score / 0.5) * 0.5
    else:
        overall = None

    return {
        "fluency": fluency,
        "vocabulary": vocabulary,
        "grammar": grammar,
        "pronunciation": pronunciation,
        "score": overall,
        "error_highlights": cleaned_highlights,
        "feedback_text": feedback_text,
    }


async def score_attempt(
    question_text: str,
    part: str,
    transcript: str,
    flagged_words: List[str],
) -> Dict[str, Any]:
    """
    Score a transcribed IELTS attempt using Ollama LLM.

    Returns:
        {
            "fluency": float,
            "vocabulary": float,
            "grammar": float,
            "pronunciation": float,
            "score": float,
            "error_highlights": [{"word": str, "type": str, "correction": str, "explanation": str, "suggestion": str}],
            "feedback_text": str,
        }
    """
    settings = get_settings()
    prompt = _build_prompt(question_text, part, transcript, flagged_words)

    try:
        raw_text = await ollama_client.generate(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            prompt=prompt,
            temperature=0.2,
            num_predict=1024,
            timeout=120.0,
        )
    except (RuntimeError, FileNotFoundError) as exc:
        logger.exception("Scoring failed: %s", exc)
        raw_text = ""

    return _parse_llm_response(raw_text)
