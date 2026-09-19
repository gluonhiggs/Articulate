"""English delivery score for an interview answer, computed from ASR word timings and grammar issues (no LLM)."""

from __future__ import annotations

import re
from typing import Any, Optional, Sequence

from backend.services.vocab import mtld

MIN_WORDS_FOR_SCORE = 20
MIN_WORDS_FOR_LEXICAL = 50

RATE_ANCHORS = ((60, 0), (90, 40), (120, 100), (170, 100), (210, 70), (240, 40), (300, 0))
PAUSE_ANCHORS = ((3, 100), (12, 30), (20, 0))
GRAMMAR_ANCHORS = ((0, 100), (2, 76), (5, 40), (8.5, 0))
LEXICAL_ANCHORS = ((20, 20), (40, 50), (80, 100))
COMPONENT_WEIGHTS = {"rate": 0.30, "pauses": 0.30, "grammar": 0.25, "lexical": 0.15}

_WORD_CHARS_RE = re.compile(r"[^a-z0-9']+")


def piecewise_linear(value: float, anchors: Sequence[tuple[float, float]]) -> float:
    """Interpolate between (x, y) anchors sorted by x; clamps to the first/last y outside the range."""
    if value <= anchors[0][0]:
        return anchors[0][1]
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
        if value <= x1:
            return y0 + (y1 - y0) * (value - x0) / (x1 - x0)
    return anchors[-1][1]


def _timed_words(words: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [w for w in words if isinstance(w.get("start"), (int, float)) and isinstance(w.get("end"), (int, float))]


def compute_delivery(
    words: Sequence[dict[str, Any]],
    grammar_issues: Optional[Sequence[dict[str, Any]]],
    gap_threshold: float,
) -> dict[str, Any]:
    """
    Delivery metrics and 0-100 score shaped like InterviewDeliveryOut.

    grammar_issues is None when the grammar checker was unavailable; that component is
    then left out and the remaining weights are renormalized.
    """
    timed = _timed_words(words)
    word_count = len(timed)
    speaking_seconds = max(0.0, timed[-1]["end"] - timed[0]["start"]) if timed else 0.0

    long_pauses = 0
    pause_seconds = 0.0
    for previous, current in zip(timed, timed[1:]):
        gap = current["start"] - previous["end"]
        if gap >= gap_threshold:
            long_pauses += 1
            pause_seconds += gap

    articulation_seconds = speaking_seconds - pause_seconds
    words_per_minute = word_count / articulation_seconds * 60 if word_count and articulation_seconds > 0 else None
    pauses_per_100 = long_pauses / word_count * 100 if word_count else None
    grammar_per_100 = len(grammar_issues) / word_count * 100 if grammar_issues is not None and word_count else None

    lexical_diversity = None
    if word_count >= MIN_WORDS_FOR_LEXICAL:
        tokens = [token for w in timed if (token := _WORD_CHARS_RE.sub("", str(w.get("word", "")).lower()))]
        lexical_diversity = mtld(tokens)

    components: dict[str, int] = {}
    if words_per_minute is not None:
        components["rate"] = round(piecewise_linear(words_per_minute, RATE_ANCHORS))
    if pauses_per_100 is not None:
        components["pauses"] = round(piecewise_linear(pauses_per_100, PAUSE_ANCHORS))
    if grammar_per_100 is not None:
        components["grammar"] = round(piecewise_linear(grammar_per_100, GRAMMAR_ANCHORS))
    if lexical_diversity is not None:
        components["lexical"] = round(piecewise_linear(lexical_diversity, LEXICAL_ANCHORS))

    score = None
    if word_count >= MIN_WORDS_FOR_SCORE and components:
        total_weight = sum(COMPONENT_WEIGHTS[name] for name in components)
        score = round(sum(COMPONENT_WEIGHTS[name] * value for name, value in components.items()) / total_weight)

    return {
        "score": score,
        "words": word_count,
        "speaking_seconds": round(speaking_seconds, 2),
        "words_per_minute": round(words_per_minute, 1) if words_per_minute is not None else None,
        "long_pauses": long_pauses,
        "pauses_per_100_words": round(pauses_per_100, 1) if pauses_per_100 is not None else None,
        "grammar_available": grammar_issues is not None,
        "grammar_errors_per_100_words": round(grammar_per_100, 1) if grammar_per_100 is not None else None,
        "grammar_issues": [
            {"text": issue["text"], "message": issue["message"], "replacements": list(issue.get("replacements", []))}
            for issue in grammar_issues or []
        ],
        "lexical_diversity": round(lexical_diversity, 1) if lexical_diversity is not None else None,
        "components": components,
    }
