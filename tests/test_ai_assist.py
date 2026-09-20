"""ai_assist service: schema-constrained sample answers and topic vocabulary, with no salvage of partial output."""

from __future__ import annotations

import pytest

from backend.services import ai_assist
from backend.services.llm_client import LLMOutputError

VOCAB_ITEM = {
    "term": "broaden one's horizons",
    "type": "collocation",
    "definition": "expand experience of the world",
    "example": "Travelling solo broadened my horizons.",
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
        raise AssertionError("ai_assist must use the JSON-schema call, not free-text generate()")

    monkeypatch.setattr(ai_assist.llm_client, "generate_json", fake_generate_json)
    monkeypatch.setattr(ai_assist.llm_client, "generate", forbidden_generate)
    return state


class TestSampleAnswer:
    async def test_returns_answer_and_key_phrases(self, fake_llm):
        fake_llm["result"] = {"sample_answer": "Honestly, I'd say the city.", "key_phrases": ["at my fingertips"]}

        result = await ai_assist.generate_sample_answer("City or countryside?", "1")

        assert result == {"sample_answer": "Honestly, I'd say the city.", "key_phrases": ["at my fingertips"]}
        assert fake_llm["kwargs"]["max_tokens"] >= 8192

    async def test_truncated_output_raises_instead_of_returning_raw_text(self, fake_llm):
        fake_llm["result"] = LLMOutputError("gemini output was cut off at max_tokens=8192")

        with pytest.raises(LLMOutputError, match="cut off"):
            await ai_assist.generate_sample_answer("City or countryside?", "1")

    async def test_empty_answer_raises(self, fake_llm):
        fake_llm["result"] = {"sample_answer": "", "key_phrases": []}

        with pytest.raises(ValueError):
            await ai_assist.generate_sample_answer("City or countryside?", "1")

    async def test_missing_key_phrases_defaults_to_empty_list(self, fake_llm):
        fake_llm["result"] = {"sample_answer": "Honestly, I'd say the city."}

        assert (await ai_assist.generate_sample_answer("City or countryside?", "1"))["key_phrases"] == []


class TestAssistModel:
    async def test_sample_answer_uses_the_assist_model(self, fake_llm, monkeypatch):
        monkeypatch.setattr(ai_assist, "get_assist_model", lambda: "gemini-3.5-flash-lite", raising=True)
        fake_llm["result"] = {"sample_answer": "The city.", "key_phrases": []}

        await ai_assist.generate_sample_answer("City or countryside?", "1")

        assert fake_llm["kwargs"]["model"] == "gemini-3.5-flash-lite"

    async def test_topic_vocab_uses_the_assist_model(self, fake_llm, monkeypatch):
        monkeypatch.setattr(ai_assist, "get_assist_model", lambda: "gemini-3.5-flash-lite", raising=True)
        fake_llm["result"] = {"vocabulary": [VOCAB_ITEM]}

        await ai_assist.generate_topic_vocab("Do you like travelling?")

        assert fake_llm["kwargs"]["model"] == "gemini-3.5-flash-lite"


class TestTopicVocab:
    async def test_returns_vocabulary_items(self, fake_llm):
        fake_llm["result"] = {"vocabulary": [VOCAB_ITEM]}

        result = await ai_assist.generate_topic_vocab("Do you like travelling?")

        assert result == {"vocabulary": [VOCAB_ITEM]}
        assert fake_llm["kwargs"]["max_tokens"] >= 8192

    async def test_truncated_output_raises_instead_of_being_repaired(self, fake_llm):
        fake_llm["result"] = LLMOutputError("gemini output was cut off at max_tokens=8192")

        with pytest.raises(LLMOutputError, match="cut off"):
            await ai_assist.generate_topic_vocab("Do you like travelling?")

    async def test_items_without_a_term_are_dropped(self, fake_llm):
        fake_llm["result"] = {"vocabulary": [VOCAB_ITEM, {"term": "  ", "definition": "nothing"}]}

        result = await ai_assist.generate_topic_vocab("Do you like travelling?")

        assert result == {"vocabulary": [VOCAB_ITEM]}

    async def test_empty_vocabulary_raises(self, fake_llm):
        fake_llm["result"] = {"vocabulary": []}

        with pytest.raises(ValueError):
            await ai_assist.generate_topic_vocab("Do you like travelling?")

    async def test_excluded_terms_reach_the_prompt(self, fake_llm):
        fake_llm["result"] = {"vocabulary": [VOCAB_ITEM]}

        await ai_assist.generate_topic_vocab("Do you like travelling?", exclude_terms=["wanderlust"])

        assert "wanderlust" in fake_llm["kwargs"]["prompt"]
