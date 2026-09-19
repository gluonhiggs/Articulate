"""Conservative correction of mis-heard technical terms in an ASR transcript, driven by a pack glossary."""

from __future__ import annotations

import math
import re
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Optional, Sequence

import simplemma

from backend.data.oxford import WORD_TO_CEFR

MAX_NGRAM_WORDS = 4
FUZZY_MATCH_RATIO = 0.88
MIN_FUZZY_COMPACT_CHARS = 5
MIN_COMPACT_CHARS = 2

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:['.\-][A-Za-z0-9]+)*")
_NGRAM_GAP_RE = re.compile(r"[\s\-]+")
_CAMEL_PART_RE = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|[0-9]+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]")
_DOUBLED_RE = re.compile(r"(.)\1+")


@dataclass(frozen=True)
class GlossaryEntry:
    term: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class _SpokenForm:
    term: str
    compact: str
    phonetic: str
    word_count: int


def compact_form(text: str) -> str:
    return _NON_ALNUM_RE.sub("", text.lower())


def phonetic_key(compact: str) -> str:
    key = compact.replace("ph", "f").replace("c", "k").replace("q", "k").replace("z", "s").replace("x", "ks")
    return _DOUBLED_RE.sub(r"\1", key.replace("y", "i"))


def split_camel_case(term: str) -> str:
    """'PySpark' -> 'py spark', 'PostgreSQL' -> 'postgre sql', 'S3' -> 's 3'."""
    return " ".join(_CAMEL_PART_RE.findall(term)).lower()


def _length_bounds(length: int) -> tuple[int, int]:
    """Lengths that can still reach FUZZY_MATCH_RATIO against a string of this length."""
    r = FUZZY_MATCH_RATIO
    return math.ceil(r * length / (2 - r)), math.floor(length * (2 - r) / r)


class _SpokenFormIndex:
    def __init__(self, entries: Iterable[GlossaryEntry]) -> None:
        forms: dict[tuple[str, str], _SpokenForm] = {}
        for entry in entries:
            for text in (entry.term, split_camel_case(entry.term), entry.term.lower(), *entry.aliases):
                compact = compact_form(text)
                if len(compact) < MIN_COMPACT_CHARS:
                    continue
                word_count = max(1, len(_TOKEN_RE.findall(text)))
                key = (entry.term, compact)
                if key not in forms or word_count > forms[key].word_count:
                    forms[key] = _SpokenForm(entry.term, compact, phonetic_key(compact), word_count)

        self.term_by_compact: dict[str, str] = {}
        for form in forms.values():
            self.term_by_compact.setdefault(form.compact, form.term)
        fuzzy = [form for form in forms.values() if len(form.compact) >= MIN_FUZZY_COMPACT_CHARS]
        self._by_compact_len = sorted(fuzzy, key=lambda form: len(form.compact))
        self._compact_lens = [len(form.compact) for form in self._by_compact_len]
        self._by_phonetic_len = sorted(fuzzy, key=lambda form: len(form.phonetic))
        self._phonetic_lens = [len(form.phonetic) for form in self._by_phonetic_len]

    def __bool__(self) -> bool:
        return bool(self.term_by_compact)

    def fuzzy_candidates(self, compact: str, phonetic: str) -> list[_SpokenForm]:
        low, high = _length_bounds(len(compact))
        by_compact = self._by_compact_len[bisect_left(self._compact_lens, low) : bisect_right(self._compact_lens, high)]
        low, high = _length_bounds(len(phonetic))
        by_phonetic = self._by_phonetic_len[
            bisect_left(self._phonetic_lens, low) : bisect_right(self._phonetic_lens, high)
        ]
        return list({id(form): form for form in (*by_compact, *by_phonetic)}.values())


def _is_common_word(token: str) -> bool:
    word = token.lower()
    return word in WORD_TO_CEFR or simplemma.lemmatize(word, lang="en") in WORD_TO_CEFR


def _anchored_ratio(heard: str, spoken: str) -> float:
    """
    SequenceMatcher ratio, or 0 unless both strings match at their first and last character.

    Without the anchors an n-gram could absorb a neighbouring word ("spark sql in") or a
    different word form ("panda" -> "Pandas") and still clear the ratio.
    """
    matcher = SequenceMatcher(None, heard, spoken, autojunk=False)
    blocks = [block for block in matcher.get_matching_blocks() if block.size]
    if not blocks:
        return 0.0
    first, last = blocks[0], blocks[-1]
    if first.a or first.b or last.a + last.size != len(heard) or last.b + last.size != len(spoken):
        return 0.0
    return matcher.ratio()


def _best_term(ngram_text: str, word_count: int, index: _SpokenFormIndex) -> Optional[tuple[str, float]]:
    compact = compact_form(ngram_text)
    if len(compact) < MIN_COMPACT_CHARS:
        return None
    exact = index.term_by_compact.get(compact)
    if exact is not None:
        return exact, 2.0
    if word_count == 1 and _is_common_word(ngram_text):
        return None

    phonetic = phonetic_key(compact)
    best: Optional[tuple[str, float]] = None
    for form in index.fuzzy_candidates(compact, phonetic):
        if abs(word_count - form.word_count) > 1:
            continue
        ratio = max(_anchored_ratio(compact, form.compact), _anchored_ratio(phonetic, form.phonetic))
        if ratio >= FUZZY_MATCH_RATIO and (best is None or ratio > best[1]):
            best = (form.term, ratio)
    return best


def apply_corrections(raw_transcript: str, corrections: Sequence[dict]) -> str:
    """Rebuild the corrected transcript from the raw one and corrections with raw offsets."""
    parts: list[str] = []
    cursor = 0
    for correction in sorted(corrections, key=lambda c: c["start"]):
        parts.append(raw_transcript[cursor : correction["start"]])
        parts.append(correction["replacement"])
        cursor = correction["end"]
    parts.append(raw_transcript[cursor:])
    return "".join(parts)


def correct_transcript(transcript: str, entries: Iterable[GlossaryEntry]) -> tuple[str, list[dict]]:
    """
    Replace mis-heard glossary terms with their canonical spelling.

    Returns the corrected text and corrections as {start, end, original, replacement},
    where start/end are offsets in the original transcript.
    """
    index = _SpokenFormIndex(entries)
    tokens = list(_TOKEN_RE.finditer(transcript))
    if not index or not tokens:
        return transcript, []

    candidates: list[tuple[int, float, int, int, str]] = []
    for word_count in range(min(MAX_NGRAM_WORDS, len(tokens)), 0, -1):
        for first in range(len(tokens) - word_count + 1):
            last = first + word_count - 1
            gaps = (transcript[tokens[i].end() : tokens[i + 1].start()] for i in range(first, last))
            if not all(_NGRAM_GAP_RE.fullmatch(gap) for gap in gaps):
                continue
            match = _best_term(transcript[tokens[first].start() : tokens[last].end()], word_count, index)
            if match is not None:
                candidates.append((word_count, match[1], first, last, match[0]))

    candidates.sort(key=lambda c: (-c[0], -c[1], c[2]))
    claimed_tokens: set[int] = set()
    corrections: list[dict] = []
    for _, _, first, last, term in candidates:
        token_range = range(first, last + 1)
        if any(i in claimed_tokens for i in token_range):
            continue
        claimed_tokens.update(token_range)
        start, end = tokens[first].start(), tokens[last].end()
        original = transcript[start:end]
        # A case-only match still claims its tokens so a shorter overlapping n-gram cannot rewrite them.
        if original.lower() != term.lower():
            corrections.append({"start": start, "end": end, "original": original, "replacement": term})

    corrections.sort(key=lambda c: c["start"])
    return apply_corrections(transcript, corrections), corrections
