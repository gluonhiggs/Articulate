"""Unit tests for scoring._parse_llm_response() - no API keys required."""
import pytest
from backend.services.scoring import _parse_llm_response, _clamp_band


class TestClampBand:
    def test_valid_midrange(self):
        assert _clamp_band(5.5) == 5.5

    def test_clamps_above_9(self):
        assert _clamp_band(10.0) == 9.0

    def test_clamps_below_0(self):
        assert _clamp_band(-1.0) == 0.0

    def test_rounds_to_half(self):
        assert _clamp_band(5.3) == 5.5

    def test_non_numeric_returns_none(self):
        assert _clamp_band("bad") is None


class TestParseLlmResponse:
    def test_valid_full_response(self):
        raw = '{"fluency":5.5,"vocabulary":5.0,"grammar":4.5,"pronunciation":5.5,"usage_errors":[{"word":"broke","type":"error","correction":"woke","explanation":"wrong word"}],"feedback_text":"Watch verb choice."}'
        result = _parse_llm_response(raw)
        assert result["fluency"] == 5.5
        assert result["score"] == 5.0  # mean of 4 criteria
        assert len(result["usage_errors"]) == 1
        assert result["usage_errors"][0]["word"] == "broke"

    def test_missing_criteria_returns_none(self):
        raw = '{"fluency":5.0}'
        result = _parse_llm_response(raw)
        assert result["fluency"] == 5.0
        assert result["vocabulary"] is None
        assert result["score"] == 5.0  # mean of available scores

    def test_empty_json_returns_nulls(self):
        raw = '{}'
        result = _parse_llm_response(raw)
        assert result["score"] is None
        assert result["usage_errors"] == []

    def test_no_json_returns_nulls(self):
        result = _parse_llm_response("Sorry, I cannot score this.")
        assert result["score"] is None

    def test_json_with_trailing_noise_extracts_via_rfind(self):
        # Valid JSON object followed by trailing text - rfind('}') finds the real closing brace
        raw = '{"fluency":6.0,"vocabulary":5.5,"grammar":5.0,"pronunciation":6.0,"usage_errors":[],"feedback_text":"ok"} some trailing noise'
        result = _parse_llm_response(raw)
        assert result["fluency"] == 6.0

    def test_usage_errors_non_list_becomes_empty(self):
        raw = '{"fluency":5.0,"vocabulary":5.0,"grammar":5.0,"pronunciation":5.0,"usage_errors":"none","feedback_text":"ok"}'
        result = _parse_llm_response(raw)
        assert result["usage_errors"] == []

    def test_error_highlight_uses_correction_field(self):
        raw = '{"fluency":5.0,"vocabulary":5.0,"grammar":5.0,"pronunciation":5.0,"usage_errors":[{"word":"than","type":"error","correction":"then","explanation":"sequence"}],"feedback_text":"ok"}'
        result = _parse_llm_response(raw)
        assert result["usage_errors"][0]["correction"] == "then"

    def test_correction_empty_string_preserved(self):
        raw = '{"fluency":5.0,"vocabulary":5.0,"grammar":5.0,"pronunciation":5.0,"usage_errors":[{"word":"never","type":"error","correction":"","explanation":"redundant"}],"feedback_text":"ok"}'
        result = _parse_llm_response(raw)
        assert result["usage_errors"][0]["correction"] == ""

    def test_markdown_fences_stripped(self):
        raw = '```json\n{"fluency":5.0,"vocabulary":5.0,"grammar":5.0,"pronunciation":5.0,"usage_errors":[],"feedback_text":"ok"}\n```'
        result = _parse_llm_response(raw)
        assert result["fluency"] == 5.0

    def test_truncated_json_salvaged_via_repair(self):
        # LLM truncated at token limit - no closing brace; repair appends '"}'
        raw = '{"fluency":6.0,"vocabulary":5.5,"grammar":5.0,"pronunciation":6.0,"usage_errors":[],"feedback_text":"Good'
        result = _parse_llm_response(raw)
        assert result["fluency"] == 6.0  # scores recovered via truncation repair


class TestLengthLabel:
    def test_very_short(self):
        from backend.services.vocab import _length_label
        label = _length_label(29)
        assert "<=4" in label  # Band <=4 ceiling

    def test_short(self):
        from backend.services.vocab import _length_label
        label = _length_label(79)
        assert "<=5" in label  # Band <=5 ceiling

    def test_moderate(self):
        from backend.services.vocab import _length_label
        label = _length_label(149)
        assert "moderate" in label

    def test_extended(self):
        from backend.services.vocab import _length_label
        label = _length_label(200)
        assert "extended" in label


class TestBuildPromptInjection:
    def test_band_descriptors_placeholder_is_substituted(self):
        """Verify {band_descriptors} is replaced in _build_prompt output."""
        from backend.services.scoring import _build_prompt
        prompt = _build_prompt("Test question?", "1", "test transcript", "")
        assert "{band_descriptors}" not in prompt
        # BAND-SCORES.md content should appear (check for a distinctive phrase)
        assert "Fluency" in prompt or "fluency" in prompt.lower()
