"""Tests for the deterministic scoring signals computed in _run_pipeline().

These tests validate the inline logic for fluency gap rate and CEFR vocabulary
distribution by running the same computation with known inputs.
"""

from __future__ import annotations

from backend.data.oxford import WORD_TO_CEFR, WORD_TO_DATA
from backend.services.vocab import compute_vocab_signal

# ---------------------------------------------------------------------------
# CEFR vocabulary signal helpers
# ---------------------------------------------------------------------------

GAP_THRESHOLD = 0.5  # mirrors Settings.gap_threshold default


def _w(word: str) -> dict:
    """Build a minimal word dict (no timestamps) for vocab signal tests."""
    return {"word": word}


def _compute_fluency(words: list[dict]) -> tuple[int, set[str], float]:
    """Replicate the fluency signal loop from _run_pipeline()."""
    gap_count = 0
    disfluent: set[str] = set()
    for i in range(1, len(words)):
        cur_start = words[i].get("start")
        prev_end = words[i - 1].get("end")
        if cur_start is not None and prev_end is not None and cur_start - prev_end >= GAP_THRESHOLD:
            gap_count += 1
            disfluent.add(words[i]["word"].lower())
    total = len(words)
    gaps_per_100 = round(gap_count / total * 100, 1) if total > 0 else 0.0
    return gap_count, disfluent, gaps_per_100


class TestCEFRWordlist:
    def test_wordlist_is_non_empty(self):
        assert len(WORD_TO_CEFR) > 4000

    def test_a1_word_present(self):
        assert "house" in WORD_TO_CEFR

    def test_levels_are_valid_cefr(self):
        valid_levels = {"A1", "A2", "B1", "B2", "C1"}
        for word, level in list(WORD_TO_CEFR.items())[:50]:
            assert level in valid_levels, f"Unexpected level {level!r} for word {word!r}"

    def test_b2_words_exist(self):
        b2_words = [w for w, lvl in WORD_TO_CEFR.items() if lvl == "B2"]
        assert len(b2_words) > 100, "Expected at least 100 B2 words"

    def test_us_alias_resolves(self):
        # "color" (US) should resolve to same level as "colour" (UK)
        assert "color" in WORD_TO_CEFR
        assert WORD_TO_CEFR["color"] == WORD_TO_CEFR["colour"]

    def test_b2_word_has_ipa(self):
        # Any B2 word should have a North American IPA transcription
        b2_word = next(w for w, lvl in WORD_TO_CEFR.items() if lvl == "B2")
        assert WORD_TO_DATA[b2_word]["phon_n_am"] != ""


class TestCEFRSignal:
    """Tests for compute_vocab_signal() in backend.services.vocab."""

    def test_no_words_returns_insufficient(self):
        signal = compute_vocab_signal([], "")
        assert "insufficient" in signal

    def test_stop_words_excluded_from_cefr_distribution(self):
        # "the", "and", "for" are stop words - should not inflate A1 count
        words = [_w("the"), _w("and"), _w("for")]
        signal = compute_vocab_signal(words, "the and for")
        # All tokens filtered -> matched=0 -> CEFR insufficient
        assert "insufficient" in signal

    def test_short_words_filtered_out(self):
        # Words with len <= 2 (after stripping) are excluded
        words = [_w("is"), _w("a"), _w("to")]
        signal = compute_vocab_signal(words, "is a to")
        assert "insufficient" in signal

    def test_only_a1_content_words(self):
        # "house" (A1) is a content word and not a stop word
        words = [_w("house"), _w("house"), _w("house")]
        signal = compute_vocab_signal(words, "house house house")
        # A1:100% and 0 B2+ words
        assert "0 B2+ words" in signal
        assert "A1:100%" in signal

    def test_b2_word_detected(self):
        # "abandon" is B2 in Oxford 5000 and not a stop word; "house" is A1
        words = [_w("abandon"), _w("house")]
        signal = compute_vocab_signal(words, "abandon house")
        assert "B2+" in signal  # from "X B2+ words"
        assert "B2:50%" in signal  # 1 of 2 matched words is B2

    def test_unmatched_words_reported(self):
        # "entrepreneurial" is C2+ / outside Oxford 5000
        words = [_w("entrepreneurial"), _w("house")]
        signal = compute_vocab_signal(words, "entrepreneurial house")
        assert "unmatched" in signal
        assert "entrepreneurial" in signal

    def test_unique_lemma_ratio_present(self):
        words = [_w("house"), _w("financial"), _w("plan")]
        signal = compute_vocab_signal(words, "house financial plan")
        assert "unique lemmas" in signal

    def test_punctuation_stripped_from_words(self):
        # "house." should match the same as "house"
        words = [_w("house."), _w("house,")]
        signal = compute_vocab_signal(words, "house. house,")
        assert "A1:100%" in signal

    def test_response_length_in_signal(self):
        # Word count (Signal 1 gap fix) must appear in output
        words = [_w("house"), _w("abandon"), _w("creative")]
        signal = compute_vocab_signal(words, "house abandon creative")
        assert "response length:" in signal
        assert "3 words" in signal

    def test_short_response_labelled(self):
        words = [_w("house")]
        signal = compute_vocab_signal(words, "house")
        assert "very short" in signal or "short" in signal


class TestIdiomSignal:
    """Tests for idiomatic / formulaic phrase detection."""

    def test_known_phrase_detected(self):
        from backend.services.vocab import _compute_idiom_signal

        signal = _compute_idiom_signal("On the other hand, I think this is important.", 10)
        assert "on the other hand" in signal

    def test_no_phrases_gives_none_label(self):
        from backend.services.vocab import _compute_idiom_signal

        signal = _compute_idiom_signal("house big car dog run", 5)
        assert "none detected" in signal

    def test_multiple_phrases_counted(self):
        from backend.services.vocab import _compute_idiom_signal

        text = "In my opinion, to some extent this is true. On the other hand, it depends on the situation."
        signal = _compute_idiom_signal(text, len(text.split()))
        # Should detect at least 3 phrases
        assert "matched:" in signal

    def test_empty_transcript(self):
        from backend.services.vocab import _compute_idiom_signal

        signal = _compute_idiom_signal("", 0)
        assert "insufficient" in signal


class TestCollocationSignal:
    """Tests for collocation pair extraction (spaCy inventory for LLM evaluation)."""

    def test_returns_string_always(self):
        from backend.services.vocab import _compute_collocation_signal

        result = _compute_collocation_signal("I went to school today.")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_output_starts_with_prefix(self):
        from backend.services.vocab import _compute_collocation_signal

        signal = _compute_collocation_signal("She cooked a delicious meal.")
        assert signal.startswith("collocation pairs")

    def test_common_pair_skipped(self):
        # "make a decision" is in _COMMON_NATURAL_PAIRS - should not appear in inventory
        from backend.services.vocab import _compute_collocation_signal, _get_spacy

        signal = _compute_collocation_signal("She made a decision to leave.")
        if _get_spacy() is not None:
            assert "make->decision" not in signal

    def test_unusual_pair_reported_in_inventory(self):
        # "do a mistake" - verb->obj pair "do->mistake" should appear in inventory
        from backend.services.vocab import _compute_collocation_signal, _get_spacy

        signal = _compute_collocation_signal("He did a mistake in his work.")
        if _get_spacy() is not None:
            assert "do->mistake" in signal

    def test_adj_noun_pair_extracted(self):
        # "delicious meal" - adj->noun pair should appear
        from backend.services.vocab import _compute_collocation_signal, _get_spacy

        signal = _compute_collocation_signal("She cooked a delicious meal.")
        if _get_spacy() is not None:
            assert "delicious->meal" in signal


class TestFluencySignal:
    def test_empty_words_zero_gaps(self):
        gap_count, disfluent, gaps_per_100 = _compute_fluency([])
        assert gap_count == 0
        assert len(disfluent) == 0
        assert gaps_per_100 == 0.0

    def test_single_word_no_gaps(self):
        words = [{"word": "hello", "start": 0.0, "end": 0.5}]
        gap_count, disfluent, gaps_per_100 = _compute_fluency(words)
        assert gap_count == 0

    def test_no_gap_below_threshold(self):
        # Gap is 0.1s < 0.5s threshold -> not counted
        words = [
            {"word": "hello", "start": 0.0, "end": 0.4},
            {"word": "world", "start": 0.5, "end": 0.9},
        ]
        gap_count, disfluent, _ = _compute_fluency(words)
        assert gap_count == 0
        assert len(disfluent) == 0

    def test_gap_exactly_at_threshold_is_counted(self):
        # Gap is exactly 0.5s = threshold -> counted
        words = [
            {"word": "hello", "start": 0.0, "end": 0.4},
            {"word": "um", "start": 0.9, "end": 1.1},  # 0.9 - 0.4 = 0.5 >= 0.5
        ]
        gap_count, disfluent, _ = _compute_fluency(words)
        assert gap_count == 1
        assert "um" in disfluent

    def test_large_gap_counted_and_word_flagged(self):
        words = [
            {"word": "hello", "start": 0.0, "end": 0.4},
            {"word": "um", "start": 1.5, "end": 1.8},  # 1.1s gap
        ]
        gap_count, disfluent, gaps_per_100 = _compute_fluency(words)
        assert gap_count == 1
        assert "um" in disfluent
        assert gaps_per_100 == 50.0  # 1 gap / 2 words * 100

    def test_multiple_gaps(self):
        words = [
            {"word": "I", "start": 0.0, "end": 0.2},
            {"word": "um", "start": 1.0, "end": 1.2},  # gap 0.8s
            {"word": "think", "start": 1.3, "end": 1.6},  # no gap
            {"word": "uh", "start": 3.0, "end": 3.2},  # gap 1.4s
        ]
        gap_count, disfluent, _ = _compute_fluency(words)
        assert gap_count == 2
        assert "um" in disfluent
        assert "uh" in disfluent

    def test_missing_timestamps_skipped(self):
        # Word without 'start' should not count as a gap
        words = [
            {"word": "hello", "end": 0.4},
            {"word": "world"},  # no start or end
        ]
        gap_count, disfluent, _ = _compute_fluency(words)
        assert gap_count == 0


# ---------------------------------------------------------------------------
# Pronunciation signal (4-tier system)
# ---------------------------------------------------------------------------


def _build_disfluent_words(words: list[dict], disfluent: set[str]) -> list[dict]:
    """Replicate the disfluent_words list comprehension from _run_pipeline() in attempts.py."""
    return [w for w in words if w["word"].lower() in disfluent]


class TestPronunciationSignal:
    """Verify compute_pronunciation_signal tier bucketing and edge cases."""

    def _sig(self, words):
        from backend.services.vocab import compute_pronunciation_signal

        return compute_pronunciation_signal(words)

    def test_cloud_mode_all_ones(self):
        # All probs exactly 1.0 -> Groq/cloud mode detected
        words = [
            {"word": "friends", "probability": 1.0},
            {"word": "charming", "probability": 1.0},
        ]
        assert self._sig(words) == "not available (cloud mode)"

    def test_cloud_mode_requires_all_ones(self):
        # Mixed probs - NOT cloud mode even if some are 1.0
        words = [
            {"word": "friends", "probability": 1.0},
            {"word": "charming", "probability": 0.85},
        ]
        result = self._sig(words)
        assert result != "not available (cloud mode)"
        assert "total: 2 words" in result

    def test_empty_words_list(self):
        assert self._sig([]) == "not available (no word data)"

    def test_no_probability_fields(self):
        words = [{"word": "friends"}, {"word": "charming"}]
        assert self._sig(words) == "not available (no word data)"

    def test_four_tier_bucketing(self):
        words = [
            {"word": "good", "probability": 0.95},  # clear
            {"word": "morning", "probability": 0.85},  # imprecise
            {"word": "world", "probability": 0.75},  # unclear
            {"word": "especial", "probability": 0.60},  # poor
        ]
        result = self._sig(words)
        assert "clear: 25%" in result
        assert "imprecise: 25%" in result
        assert "unclear: 25%" in result
        assert "poor: 25%" in result
        assert "total: 4 words" in result
        assert "especial" in result  # poor tier listed
        assert "world" in result  # unclear tier listed
        assert "morning" in result  # imprecise tier listed
        assert "good" not in result  # clear tier not listed

    def test_boundary_values(self):
        # Exactly on boundary: 0.9 -> clear, 0.8 -> imprecise, 0.7 -> unclear
        words = [
            {"word": "a", "probability": 0.9},
            {"word": "b", "probability": 0.8},
            {"word": "c", "probability": 0.7},
        ]
        result = self._sig(words)
        assert "clear: 33%" in result
        assert "imprecise: 33%" in result
        assert "unclear: 33%" in result
        assert "poor: 0%" in result  # always present in aggregate line

    def test_all_clear_no_tier_lines(self):
        # All clear -> aggregate line only, no per-tier word lines
        words = [
            {"word": "hello", "probability": 0.95},
            {"word": "world", "probability": 0.92},
        ]
        result = self._sig(words)
        lines = result.strip().split("\n")
        assert len(lines) == 1
        assert "clear: 100%" in lines[0]

    def test_poor_words_sorted_worst_first(self):
        # Words within poor tier sorted ascending by probability (worst first)
        words = [
            {"word": "comfortable", "probability": 0.65},
            {"word": "especial", "probability": 0.45},
        ]
        result = self._sig(words)
        poor_line = [line for line in result.split("\n") if "poorly pronounced" in line.lower()][0]
        assert poor_line.index("especial") < poor_line.index("comfortable")

    def test_missing_probability_words_ignored(self):
        # Words without probability field are excluded from count
        words = [
            {"word": "friends", "probability": 0.95},
            {"word": "charming"},  # no probability
        ]
        result = self._sig(words)
        assert "total: 1 words" in result


class TestDisfluuentWords:
    """Verify disfluency-based word extraction (now separate from mispronounced)."""

    def test_disfluent_word_captured(self):
        words = [{"word": "um", "probability": 1.0}]
        assert _build_disfluent_words(words, disfluent={"um"}) == [{"word": "um", "probability": 1.0}]

    def test_non_disfluent_word_excluded(self):
        words = [{"word": "friends", "probability": 1.0}]
        assert _build_disfluent_words(words, disfluent=set()) == []

    def test_low_probability_disfluent_word_captured(self):
        # A word that is both low-confidence AND after a pause -> goes to disfluent_words
        words = [{"word": "um", "probability": 0.3}]
        assert _build_disfluent_words(words, disfluent={"um"}) == [{"word": "um", "probability": 0.3}]
