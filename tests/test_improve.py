"""improve service: schema-constrained output, with failures raised instead of shown as the rewrite."""

from __future__ import annotations

import pytest

from backend.config import Settings
from backend.services import improve as improve_service
from backend.services.llm_client import LLMOutputError

ARGS = {
    "question_text": "What do you do in your free time?",
    "transcript": "I like to play game in my free time.",
    "current_band": 5.0,
    "target_band": 6.0,
}


@pytest.fixture
def fake_llm(monkeypatch):
    """Replace generate_json with a stub, and make any plain generate() call a failure."""
    state = {"result": {}, "kwargs": {}}

    async def fake_generate_json(**kwargs):
        state["kwargs"] = kwargs
        if isinstance(state["result"], Exception):
            raise state["result"]
        return state["result"]

    async def forbidden_generate(*args, **kwargs):
        raise AssertionError("improve must use the JSON-schema call, not free-text generate()")

    monkeypatch.setattr(improve_service.llm_client, "generate_json", fake_generate_json)
    monkeypatch.setattr(improve_service.llm_client, "generate", forbidden_generate)
    return state


async def test_returns_improved_text_and_explanation(fake_llm):
    fake_llm["result"] = {"improved_text": "In my free time I play video games.", "explanation": "Fixed the noun."}

    result = await improve_service.generate_improvement(**ARGS)

    assert result == {"improved_text": "In my free time I play video games.", "explanation": "Fixed the noun."}


async def test_request_leaves_room_for_a_thinking_model(fake_llm):
    fake_llm["result"] = {"improved_text": "Rewritten.", "explanation": ""}

    await improve_service.generate_improvement(**ARGS)

    assert fake_llm["kwargs"]["max_tokens"] >= 8192
    assert fake_llm["kwargs"]["schema"] == improve_service.IMPROVE_SCHEMA


async def test_truncated_output_raises_instead_of_returning_a_json_fragment(fake_llm):
    fake_llm["result"] = LLMOutputError("gemini output was cut off at max_tokens=8192")

    with pytest.raises(LLMOutputError, match="cut off"):
        await improve_service.generate_improvement(**ARGS)


async def test_empty_improved_text_raises(fake_llm):
    fake_llm["result"] = {"improved_text": "   ", "explanation": "nothing to say"}

    with pytest.raises(ValueError):
        await improve_service.generate_improvement(**ARGS)


async def test_missing_explanation_defaults_to_empty_string(fake_llm):
    fake_llm["result"] = {"improved_text": "Rewritten."}

    assert (await improve_service.generate_improvement(**ARGS))["explanation"] == ""


async def test_reasoning_effort_is_forwarded_only_when_configured(fake_llm, monkeypatch):
    fake_llm["result"] = {"improved_text": "Rewritten.", "explanation": ""}

    monkeypatch.setattr(improve_service, "get_settings", lambda: Settings(llm_reasoning_effort=""))
    await improve_service.generate_improvement(**ARGS)
    assert fake_llm["kwargs"]["reasoning_effort"] == ""

    monkeypatch.setattr(improve_service, "get_settings", lambda: Settings(llm_reasoning_effort="none"))
    await improve_service.generate_improvement(**ARGS)
    assert fake_llm["kwargs"]["reasoning_effort"] == "none"
