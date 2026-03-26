"""Tests for the deterministic scoring signals computed in _run_pipeline().

These tests validate the inline logic for fluency gap rate and CEFR vocabulary
distribution by running the same computation with known inputs.
"""
from __future__ import annotations

import pytest

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
        if (
            cur_start is not None
            and prev_end is not None
            and cur_start - prev_end >= GAP_THRESHOLD
        ):
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
        # "the", "and", "for" are stop words — should not inflate A1 count
        words = [_w("the"), _w("and"), _w("for")]
        signal = compute_vocab_signal(words, "the and for")
        # All tokens filtered → matched=0 → CEFR insufficient
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
        # Gap is 0.1s < 0.5s threshold → not counted
        words = [
            {"word": "hello", "start": 0.0, "end": 0.4},
            {"word": "world", "start": 0.5, "end": 0.9},
        ]
        gap_count, disfluent, _ = _compute_fluency(words)
        assert gap_count == 0
        assert len(disfluent) == 0

    def test_gap_exactly_at_threshold_is_counted(self):
        # Gap is exactly 0.5s = threshold → counted
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
            {"word": "um", "start": 1.0, "end": 1.2},   # gap 0.8s
            {"word": "think", "start": 1.3, "end": 1.6},  # no gap
            {"word": "uh", "start": 3.0, "end": 3.2},   # gap 1.4s
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
