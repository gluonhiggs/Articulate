"""Tests for the deterministic scoring signals computed in _run_pipeline().

These tests validate the inline logic for fluency gap rate and CEFR vocabulary
distribution by running the same computation with known inputs.
"""
from __future__ import annotations

import pytest

from backend.data.cefr_wordlist import CEFR

# ---------------------------------------------------------------------------
# CEFR vocabulary signal
# ---------------------------------------------------------------------------

GAP_THRESHOLD = 0.5  # mirrors Settings.gap_threshold default


def _compute_vocab_signal(words: list[dict]) -> str:
    """Replicate the CEFR signal logic from _run_pipeline()."""
    content_words = [
        w["word"].lower().strip(".,!?;:'\"")
        for w in words
        if len(w.get("word", "")) > 2
    ]
    known = [w for w in content_words if w in CEFR]
    high_level = sum(1 for w in known if CEFR[w] in ("B2", "C1"))
    if not known:
        return "insufficient vocabulary data"
    pct = round(high_level / len(known) * 100)
    return f"{high_level}/{len(known)} known words are B2+ ({pct}%)"


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
        assert len(CEFR) > 100

    def test_a1_word_present(self):
        # "house" is universally A1 — sanity check the dict loaded
        assert "house" in CEFR

    def test_levels_are_valid_cefr(self):
        valid_levels = {"A1", "A2", "B1", "B2", "C1"}
        for word, level in list(CEFR.items())[:50]:
            assert level in valid_levels, f"Unexpected level {level!r} for word {word!r}"

    def test_b2_words_exist(self):
        b2_words = [w for w, lvl in CEFR.items() if lvl == "B2"]
        assert len(b2_words) > 10, "Expected at least 10 B2 words in wordlist"


class TestCEFRSignal:
    def test_no_words_returns_insufficient(self):
        signal = _compute_vocab_signal([])
        assert signal == "insufficient vocabulary data"

    def test_short_words_filtered_out(self):
        # Words with len <= 2 are excluded from content_words
        words = [{"word": "is"}, {"word": "a"}, {"word": "to"}]
        signal = _compute_vocab_signal(words)
        assert signal == "insufficient vocabulary data"

    def test_unknown_words_return_insufficient(self):
        words = [{"word": "xyzabc"}, {"word": "qqqrrr"}, {"word": "zzznnn"}]
        signal = _compute_vocab_signal(words)
        assert signal == "insufficient vocabulary data"

    def test_only_a1_words_zero_b2_percent(self):
        # "house" is A1 — should give 0% B2+
        words = [{"word": "house"}, {"word": "house"}, {"word": "house"}]
        signal = _compute_vocab_signal(words)
        assert "0%" in signal or "0/" in signal

    def test_b2_word_detected(self):
        # Find any B2 word in the dict to test with
        b2_word = next(w for w, lvl in CEFR.items() if lvl == "B2" and len(w) > 2)
        a1_word = next(w for w, lvl in CEFR.items() if lvl == "A1" and len(w) > 2)
        words = [{"word": b2_word}, {"word": a1_word}]
        signal = _compute_vocab_signal(words)
        assert "B2+" in signal
        assert "50%" in signal  # 1 of 2 known words is B2+

    def test_punctuation_stripped_from_words(self):
        # "house." should be treated same as "house"
        words = [{"word": "house."}]
        signal = _compute_vocab_signal(words)
        # "house" (A1) is known → 0% B2+
        assert "0/" in signal or "insufficient" in signal


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
