"""Groq verifier request budgeting for the interview grader."""

from __future__ import annotations

import pytest

from backend.config import Settings
from backend.models import InterviewQuestion
from backend.services import interview_grading
from backend.services.interview_grading import (
    GROQ_FREE_TIER_TOKENS_PER_MINUTE,
    MIN_VERIFIER_MAX_TOKENS,
    verifier_max_tokens,
)

CLAIMS = [("kp-1", "Transformations are lazy", "nothing runs until an action")]


class TestVerifierMaxTokens:
    def test_short_prompt_keeps_the_configured_ceiling(self):
        assert verifier_max_tokens("x" * 400, 4096) == 4096

    def test_long_prompt_lowers_the_reply_budget(self):
        prompt = "x" * 20000  # about 5000 prompt tokens
        assert verifier_max_tokens(prompt, 4096) == GROQ_FREE_TIER_TOKENS_PER_MINUTE - 5000

    @pytest.mark.parametrize("chars", [0, 4000, 16000, 24000, 28000])
    def test_prompt_plus_reply_stay_inside_the_free_tier_budget(self, chars):
        prompt = "x" * chars
        assert chars // 4 + verifier_max_tokens(prompt, 4096) <= GROQ_FREE_TIER_TOKENS_PER_MINUTE

    def test_never_drops_below_a_usable_floor(self):
        assert verifier_max_tokens("x" * 80000, 4096) == MIN_VERIFIER_MAX_TOKENS

    def test_configured_ceiling_is_respected(self):
        assert verifier_max_tokens("x" * 400, 1024) == 1024


class TestVerifyRequest:
    @pytest.fixture
    def sent(self, monkeypatch):
        state = {}

        async def fake_generate_json(**kwargs):
            state.update(kwargs)
            return {"key_points": [], "misconceptions": []}

        monkeypatch.setattr(interview_grading.llm_client, "generate_json", fake_generate_json)
        return state

    async def test_verify_caps_max_tokens_for_a_long_transcript(self, sent):
        question = InterviewQuestion(text="What is lazy evaluation in Spark?")
        transcript = "Spark is lazy. " * 1000

        await interview_grading._verify(Settings(), question, transcript, CLAIMS, [])

        assert sent["max_tokens"] == verifier_max_tokens(sent["prompt"], 4096)
        assert sent["max_tokens"] < 4096
        assert len(sent["prompt"]) // 4 + sent["max_tokens"] <= GROQ_FREE_TIER_TOKENS_PER_MINUTE

    async def test_verify_uses_the_configured_ceiling_for_a_short_transcript(self, sent):
        question = InterviewQuestion(text="What is lazy evaluation in Spark?")

        await interview_grading._verify(
            Settings(interview_verifier_max_tokens=2048), question, "Nothing runs until an action.", CLAIMS, []
        )

        assert sent["max_tokens"] == 2048
