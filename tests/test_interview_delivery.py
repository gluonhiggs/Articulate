"""Unit tests for the interview delivery score."""

from __future__ import annotations

import pytest

from backend.services.interview_delivery import (
    GRAMMAR_ANCHORS,
    LEXICAL_ANCHORS,
    PAUSE_ANCHORS,
    RATE_ANCHORS,
    compute_delivery,
    piecewise_linear,
)

GAP = 0.5


def _words(count: int, seconds_per_word: float, pause_every: int = 0, pause: float = 1.0):
    words, t = [], 0.0
    for i in range(count):
        if pause_every and i and i % pause_every == 0:
            t += pause
        words.append({"word": f"w{i}", "start": round(t, 3), "end": round(t + seconds_per_word, 3)})
        t += seconds_per_word
    return words


@pytest.mark.parametrize(
    ("wpm", "expected"),
    [
        (50, 0),
        (60, 0),
        (75, 20),
        (90, 40),
        (105, 70),
        (120, 100),
        (150, 100),
        (170, 100),
        (190, 85),
        (210, 70),
        (240, 40),
        (270, 20),
        (300, 0),
        (400, 0),
    ],
)
def test_rate_anchors(wpm, expected):
    assert piecewise_linear(wpm, RATE_ANCHORS) == pytest.approx(expected)


@pytest.mark.parametrize(("per_100", "expected"), [(0, 100), (3, 100), (7.5, 65), (12, 30), (16, 15), (20, 0), (30, 0)])
def test_pause_anchors(per_100, expected):
    assert piecewise_linear(per_100, PAUSE_ANCHORS) == pytest.approx(expected)


@pytest.mark.parametrize(("per_100", "expected"), [(0, 100), (1, 88), (2, 76), (5, 40), (8.5, 0), (12, 0)])
def test_grammar_anchors(per_100, expected):
    assert piecewise_linear(per_100, GRAMMAR_ANCHORS) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("mtld", "expected"), [(10, 20), (20, 20), (30, 35), (40, 50), (60, 75), (80, 100), (120, 100)]
)
def test_lexical_anchors(mtld, expected):
    assert piecewise_linear(mtld, LEXICAL_ANCHORS) == pytest.approx(expected)


def test_steady_speech_scores_high():
    delivery = compute_delivery(_words(60, 0.4), grammar_issues=[], gap_threshold=GAP)
    assert delivery["words"] == 60
    assert delivery["words_per_minute"] == pytest.approx(150.0)
    assert delivery["long_pauses"] == 0
    assert delivery["grammar_available"] is True
    assert delivery["grammar_errors_per_100_words"] == 0.0
    assert delivery["components"]["rate"] == 100
    assert delivery["components"]["pauses"] == 100
    assert delivery["components"]["grammar"] == 100
    assert delivery["lexical_diversity"] is not None
    assert delivery["score"] >= 90


def test_long_pauses_are_excluded_from_speaking_rate():
    words = _words(40, 0.4, pause_every=5, pause=2.0)
    delivery = compute_delivery(words, grammar_issues=[], gap_threshold=GAP)
    assert delivery["long_pauses"] == 7
    assert delivery["words_per_minute"] == pytest.approx(150.0)
    assert delivery["pauses_per_100_words"] == 17.5
    assert delivery["components"]["pauses"] == round(piecewise_linear(17.5, PAUSE_ANCHORS))
    assert delivery["speaking_seconds"] == pytest.approx(30.0)


def test_grammar_unavailable_renormalizes_weights():
    words = _words(30, 0.4)
    delivery = compute_delivery(words, grammar_issues=None, gap_threshold=GAP)
    assert delivery["grammar_available"] is False
    assert delivery["grammar_errors_per_100_words"] is None
    assert "grammar" not in delivery["components"]
    assert "lexical" not in delivery["components"]
    assert delivery["score"] == 100


def test_grammar_issues_reduce_score_and_are_listed():
    issues = [{"text": "he go", "message": "Agreement", "replacements": ["he goes"], "offset": 0}] * 3
    delivery = compute_delivery(_words(30, 0.4), grammar_issues=issues, gap_threshold=GAP)
    assert delivery["grammar_errors_per_100_words"] == 10.0
    assert delivery["components"]["grammar"] == 0
    # The offset travels with the issue so the UI can highlight the phrase in the transcript.
    assert delivery["grammar_issues"][0] == {
        "text": "he go",
        "message": "Agreement",
        "replacements": ["he goes"],
        "offset": 0,
    }
    assert delivery["score"] == round((0.30 * 100 + 0.30 * 100 + 0.25 * 0) / 0.85)


def test_fewer_than_twenty_words_has_no_score():
    delivery = compute_delivery(_words(19, 0.4), grammar_issues=[], gap_threshold=GAP)
    assert delivery["score"] is None
    assert delivery["words"] == 19
    assert delivery["words_per_minute"] is not None


def test_no_words():
    delivery = compute_delivery([], grammar_issues=None, gap_threshold=GAP)
    assert delivery["score"] is None
    assert delivery["words"] == 0
    assert delivery["words_per_minute"] is None
    assert delivery["components"] == {}
