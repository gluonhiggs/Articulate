from __future__ import annotations

import json
import logging
from typing import Any, Dict

from backend.config import get_settings
from backend.constants import PROMPTS_DIR
from backend.services import ollama_client

logger = logging.getLogger(__name__)


def _load_prompt(name: str) -> str:
    with open(PROMPTS_DIR / name, "r", encoding="utf-8") as f:
        return f.read()


def _parse_json_response(raw: str, required_field: str) -> Dict[str, Any]:
    """Extract JSON from LLM response, raising on failure."""
    if not raw or not raw.strip():
        raise ValueError("LLM returned empty response")

    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end <= start:
        raise ValueError("LLM response contained no JSON object")

    try:
        data = json.loads(raw[start:end])
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned invalid JSON: {exc}") from exc

    if required_field not in data or not data[required_field]:
        raise ValueError(f"LLM response missing '{required_field}' field")

    return data


def _repair_vocab_json(raw: str) -> str:
    """Try to salvage truncated {\"vocabulary\":[...]} JSON from LLM output."""
    start = raw.find('{"vocabulary"')
    if start == -1:
        start = raw.find('{')
    if start == -1:
        raise ValueError("No JSON found in LLM response")
    fragment = raw[start:]
    # Find last complete item: ends with }
    last_complete = fragment.rfind('}')
    if last_complete == -1:
        raise ValueError("No complete JSON object found")
    # Close the array and wrapper if needed
    truncated = fragment[:last_complete + 1]
    open_arrays = truncated.count('[') - truncated.count(']')
    open_braces = truncated.count('{') - truncated.count('}')
    if open_arrays > 0:
        truncated += ']' * open_arrays
    if open_braces > 0:
        truncated += '}' * open_braces
    return truncated


async def generate_sample_answer(
    question_text: str,
    part: str,
    target_band: float = 7.0,
) -> Dict[str, Any]:
    """Generate a sample IELTS response at the target band level."""
    settings = get_settings()
    template = _load_prompt("sample_answer.txt")
    word_count = "40-60" if part == "1" else "150-200" if part == "2" else "60-90"
    prompt = (
        template.replace("{question_text}", question_text)
        .replace("{target_band}", str(target_band))
        .replace("{part}", f"Part {part}")
        .replace("{word_count}", word_count)
    )

    raw = await ollama_client.generate(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        prompt=prompt,
        api_key=settings.llm_api_key,
        temperature=0.6,
        num_predict=1024,
        timeout=120.0,
    )
    try:
        data = _parse_json_response(raw, "sample_answer")
    except ValueError:
        # Fallback: use raw text as the answer
        logger.warning("Sample answer JSON parse failed, using raw text")
        data = {"sample_answer": raw.strip(), "key_phrases": []}
    return data


async def generate_topic_vocab(question_text: str) -> Dict[str, Any]:
    """Generate advanced topic vocabulary for an IELTS question."""
    settings = get_settings()
    template = _load_prompt("topic_vocab.txt")
    prompt = template.replace("{question_text}", question_text)

    raw = await ollama_client.generate(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        prompt=prompt,
        api_key=settings.llm_api_key,
        temperature=0.4,
        num_predict=2048,
        timeout=120.0,
    )

    # Try standard parse first
    start = raw.find('{"vocabulary"')
    if start == -1:
        start = raw.find('{')
    end = raw.rfind('}') + 1

    if start != -1 and end > start:
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass  # Fall through to repair

    # Repair truncated JSON
    try:
        repaired = _repair_vocab_json(raw)
        data = json.loads(repaired)
        if "vocabulary" in data and data["vocabulary"]:
            return data
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("Vocab JSON repair failed: %s", exc)

    raise ValueError("Could not parse vocabulary response from LLM")
