"""Sentence segmentation and the rule that decides which spoken sentences read badly.

Deterministic on purpose: the LLM is only asked to rewrite sentences this module has
already picked, which keeps the prompt small enough for the free tier and makes
"this sentence needs work" a stated rule rather than a model's mood.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Optional, Sequence

MIN_WORDS = 8
RUN_ON_WORDS = 34
MAX_CONNECTIVES = 3
MAX_SENTENCES = 5

_TERMINATOR_RE = re.compile(r"[.!?]+")
_WORD_RE = re.compile(r"[A-Za-z0-9']+")

# Words that chain one clause onto the next. Three or more in a single spoken
# sentence is the shape of an answer that never came to a stop.
_CONNECTIVES: frozenset[str] = frozenset(
    {"and", "but", "so", "because", "or", "then", "also", "which", "while", "although"}
)

REASON_LABELS = {
    "run_on": "very long",
    "chained": "many clauses chained together",
    "grammar": "grammar issue",
}


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Return (start, end) character offsets for each sentence in *text*.

    Splits on terminal punctuation (. ! ?) followed by whitespace or end of string.
    Whisper transcripts include punctuation, making this reliable. Falls back to the
    whole text as a single span when no boundary is found (e.g. very short responses).
    """
    spans: list[tuple[int, int]] = []
    start = 0
    for match in _TERMINATOR_RE.finditer(text):
        end = match.end()
        spans.append((start, end))
        nxt = end
        while nxt < len(text) and text[nxt].isspace():
            nxt += 1
        start = nxt
    if start < len(text):  # trailing text with no terminal punctuation
        spans.append((start, len(text)))
    return spans or [(0, len(text))]


def _connective_count(words: Sequence[str]) -> int:
    # The opening word is a discourse marker ("And then we..."), not a chained clause.
    return sum(1 for word in words[1:] if word in _CONNECTIVES)


def weak_sentences(
    text: str,
    grammar_offsets: Iterable[int] = (),
    limit: int = MAX_SENTENCES,
) -> list[dict[str, Any]]:
    """Sentences worth rewriting, in the order they were spoken.

    A sentence qualifies when it runs past RUN_ON_WORDS, chains more than
    MAX_CONNECTIVES clauses, or contains a grammar issue. Sentences shorter than
    MIN_WORDS are never flagged: there is nothing to untangle.
    """
    offsets = sorted(grammar_offsets)
    picked: list[dict[str, Any]] = []
    for index, (start, end) in enumerate(sentence_spans(text)):
        sentence = text[start:end].strip()
        words = [word.lower() for word in _WORD_RE.findall(sentence)]
        if len(words) < MIN_WORDS:
            continue
        reasons: list[str] = []
        if len(words) > RUN_ON_WORDS:
            reasons.append("run_on")
        if _connective_count(words) > MAX_CONNECTIVES:
            reasons.append("chained")
        if any(start <= offset < end for offset in offsets):
            reasons.append("grammar")
        if reasons:
            picked.append({"index": index, "start": start, "end": end, "text": sentence, "reasons": reasons})

    # Worst first when trimming, so a cap never drops the sentence that needs it most.
    picked.sort(key=lambda item: (-len(item["reasons"]), -len(item["text"])))
    return sorted(picked[:limit], key=lambda item: item["index"])


def _on_word_boundary(haystack: str, start: int, end: int) -> bool:
    before_ok = start == 0 or not (haystack[start - 1].isalnum() and haystack[start].isalnum())
    after_ok = end == len(haystack) or not (haystack[end].isalnum() and haystack[end - 1].isalnum())
    return before_ok and after_ok


def find_span(
    haystack: str, needle: str, expected: Optional[int] = None, whole_word: bool = False
) -> Optional[tuple[int, int]]:
    """Locate *needle* in *haystack*, preferring the occurrence nearest *expected*.

    Grammar offsets are measured against the raw transcript, which the candidate may
    have edited since, so an offset alone cannot be trusted to still point at the text.

    whole_word rejects an occurrence buried inside a longer word. Without it, a flagged
    "make" that the candidate has since corrected to "makes" relocates onto the first
    four letters of the fix, and the correction is then struck through as the mistake.
    """
    if not needle:
        return None
    best: Optional[int] = None
    position = haystack.find(needle)
    while position != -1:
        end = position + len(needle)
        if not whole_word or _on_word_boundary(haystack, position, end):
            if expected is None:
                return (position, end)
            if best is None or abs(position - expected) < abs(best - expected):
                best = position
        position = haystack.find(needle, position + 1)
    return None if best is None else (best, best + len(needle))
