"""Pure interview grading rules: quote evidence checks, verdict merging, content score and follow-up choice."""

from __future__ import annotations

import heapq
import re
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Optional, Sequence

MIN_QUOTE_WORDS = 3
FUZZY_QUOTE_RATIO = 0.9
MAX_FUZZY_QUOTE_WORDS = 60
FUZZY_CANDIDATE_STARTS = 10
MAX_VOTE_WORK = 200_000
MAX_KEY_POINTS_PER_QUOTE = 2
CORE_WEIGHT = 3
INCORRECT_CAP = 39
CORE_NOT_COVERED_CAP = 69
STRONG_MIN = 70
DEVELOPING_MIN = 40

VERDICT_CREDIT = {"covered": 1.0, "partial": 0.5, "missing": 0.0, "incorrect": 0.0}
_PROPOSER_RANK = {"incorrect": -1, "missing": 0, "partial": 1, "covered": 2}
_VERIFIER_RANK = {"contradicted": -1, "not_supported": 0, "partial": 1, "supported": 2}
_RANK_TO_VERDICT = {rank: verdict for verdict, rank in _PROPOSER_RANK.items()}
_FOLLOW_UP_TRIGGER_ORDER = {"incorrect": 0, "missing": 1, "partial": 2}

QUOTE_NOT_FOUND_REASON = "The quote given as evidence was not found in the transcript, so this point is not credited."
QUOTE_REUSED_REASON = (
    "The same part of the answer was already credited to two other key points, so this point is not credited."
)

NEGATION_WORDS = frozenset(
    "not no never none nor neither nothing nobody nowhere cannot without isnt arent wasnt werent dont doesnt "
    "didnt cant couldnt wont wouldnt shouldnt hasnt havent hadnt mustnt neednt mightnt shant aint".split()
)

_WORD_RE = re.compile("[A-Za-z0-9'\N{RIGHT SINGLE QUOTATION MARK}]+")
_APOSTROPHE_RE = re.compile("['\N{RIGHT SINGLE QUOTATION MARK}]")


def _word_spans(text: str) -> list[tuple[str, int, int]]:
    """Normalized words with their character offsets in text."""
    spans = []
    for match in _WORD_RE.finditer(text):
        word = _APOSTROPHE_RE.sub("", match.group()).lower()
        if word:
            spans.append((word, match.start(), match.end()))
    return spans


def normalize_text(text: str) -> str:
    """Lowercase, drop apostrophes, turn other punctuation into spaces and collapse whitespace."""
    return " ".join(word for word, _, _ in _word_spans(text))


def _negation_count(words: Iterable[str]) -> int:
    return sum(word in NEGATION_WORDS for word in words)


@dataclass(frozen=True)
class QuoteMatch:
    """Where a quote matched: the word window [start, end) and the original text it covers."""

    start: int
    end: int
    text: str

    def overlaps(self, other: "QuoteMatch") -> bool:
        """True when the two windows share more than half of the shorter one."""
        shared = min(self.end, other.end) - max(self.start, other.start)
        return 2 * shared > min(self.end - self.start, other.end - other.start)


class QuoteIndex:
    """Finds where a quote appears (exactly or nearly verbatim) in one text."""

    def __init__(self, text: str) -> None:
        self._text = text
        spans = _word_spans(text)
        self._words = [word for word, _, _ in spans]
        self._offsets = [(start, end) for _, start, end in spans]
        self._padded = f" {' '.join(self._words)} "
        self._positions: dict[str, list[int]] = defaultdict(list)
        for i, word in enumerate(self._words):
            self._positions[word].append(i)

    def contains(self, quote: Optional[str]) -> bool:
        return self.find(quote) is not None

    def find(self, quote: Optional[str]) -> Optional[QuoteMatch]:
        quote_words = [word for word, _, _ in _word_spans(quote or "")]
        n = len(quote_words)
        if n < MIN_QUOTE_WORDS or n > len(self._words):
            return None
        joined = " ".join(quote_words)
        position = self._padded.find(f" {joined} ")
        if position != -1:
            return self._match(self._padded.count(" ", 0, position + 1) - 1, n)
        if n > MAX_FUZZY_QUOTE_WORDS:
            return None
        start = self._fuzzy_start(quote_words, joined)
        return None if start is None else self._match(start, n)

    def _match(self, start: int, length: int) -> QuoteMatch:
        end = start + length
        return QuoteMatch(start, end, self._text[self._offsets[start][0] : self._offsets[end - 1][1]])

    def _fuzzy_start(self, quote_words: list[str], joined: str) -> Optional[int]:
        n = len(quote_words)
        min_votes = max(2, n // 2)
        postings = sorted(
            ((offset, word, self._positions.get(word, [])) for offset, word in enumerate(quote_words)),
            key=lambda item: len(item[2]),
        )
        # Only windows that share aligned words with the quote can reach the fuzzy ratio, so window starts are
        # voted for instead of scoring every window. Only the rarest words may add new starts: a start none of
        # them voted for cannot reach min_votes from the rest, which only confirm or drop existing candidates.
        # The work cap keeps a long repetitive source from stalling the search.
        votes: dict[int, int] = defaultdict(int)
        seeding_words = n - min_votes + 1
        work = 0
        for rank, (offset, word, positions) in enumerate(postings):
            work += len(positions) if rank < seeding_words else len(votes)
            if work > MAX_VOTE_WORK:
                break
            if rank < seeding_words:
                for position in positions:
                    votes[position - offset] += 1
                continue
            words_left_after = n - rank - 1
            for start in list(votes):
                index = start + offset
                if 0 <= index < len(self._words) and self._words[index] == word:
                    votes[start] += 1
                elif votes[start] + words_left_after < min_votes:
                    del votes[start]
        best_starts = heapq.nsmallest(
            FUZZY_CANDIDATE_STARTS,
            (start for start, count in votes.items() if count >= min_votes),
            key=lambda start: (-votes[start], start),
        )

        # A near-verbatim quote that adds or drops a negation says the opposite of the text.
        quote_negations = _negation_count(quote_words)
        matcher = SequenceMatcher(None, autojunk=False)
        matcher.set_seq2(joined)
        tried: set[int] = set()
        for start in best_starts:
            for window_start in (start, start - 1, start + 1):
                if window_start in tried or window_start < 0 or window_start + n > len(self._words):
                    continue
                tried.add(window_start)
                window = self._words[window_start : window_start + n]
                matcher.set_seq1(" ".join(window))
                if (
                    matcher.real_quick_ratio() >= FUZZY_QUOTE_RATIO
                    and matcher.quick_ratio() >= FUZZY_QUOTE_RATIO
                    and matcher.ratio() >= FUZZY_QUOTE_RATIO
                    and _negation_count(window) == quote_negations
                ):
                    return window_start
        return None


def quote_in_text(quote: Optional[str], text: str) -> bool:
    return QuoteIndex(text).contains(quote)


def apply_quote_rules(claims: Sequence[dict], transcript_index: QuoteIndex) -> list[dict]:
    """
    Downgrade key point claims whose evidence does not hold up.

    claims: dicts with verdict, quote and reason, in key point order. A non-missing verdict needs its
    quote in the transcript, and the quote is replaced by the transcript words it matched. Evidence
    overlapping what two other key points already claimed credits no further key point.
    """
    claimed: list[QuoteMatch] = []
    checked: list[dict] = []
    for claim in claims:
        result = dict(claim)
        if result["verdict"] != "missing":
            match = transcript_index.find(result.get("quote"))
            if match is None:
                result.update(verdict="missing", reason=QUOTE_NOT_FOUND_REASON)
            else:
                result["quote"] = match.text
                if result["verdict"] in ("covered", "partial"):
                    if sum(match.overlaps(other) for other in claimed) >= MAX_KEY_POINTS_PER_QUOTE:
                        result.update(verdict="missing", reason=QUOTE_REUSED_REASON)
                    claimed.append(match)
        if result["verdict"] == "missing":
            result["quote"] = None
        checked.append(result)
    return checked


def merge_verdict(proposer_verdict: str, verifier_verdict: Optional[str]) -> str:
    """The lower of the two opinions; a contradiction always ends as incorrect."""
    if verifier_verdict is None:
        return proposer_verdict
    rank = min(_PROPOSER_RANK[proposer_verdict], _VERIFIER_RANK.get(verifier_verdict, 0))
    return _RANK_TO_VERDICT[rank]


def content_score(results: Iterable[tuple[int, str]], misconception_count: int) -> tuple[int, str]:
    """
    Weighted key point credit as 0-100 plus a band.

    results: (weight, verdict) per approved key point; must not be empty.
    """
    results = list(results)
    total_weight = sum(weight for weight, _ in results)
    if total_weight <= 0:
        raise ValueError("content_score needs at least one weighted key point")
    earned = sum(weight * VERDICT_CREDIT[verdict] for weight, verdict in results)
    score = int(100 * earned / total_weight + 0.5)

    core_verdicts = [verdict for weight, verdict in results if weight == CORE_WEIGHT]
    if misconception_count > 0 or "incorrect" in core_verdicts:
        return min(score, INCORRECT_CAP), "incorrect"
    if any(verdict != "covered" for verdict in core_verdicts):
        score = min(score, CORE_NOT_COVERED_CAP)
    if score >= STRONG_MIN:
        return score, "strong"
    if score >= DEVELOPING_MIN:
        return score, "developing"
    return score, "weak"


@dataclass(frozen=True)
class FollowUpOption:
    question_id: int
    position: int
    trigger_key_point_uid: Optional[str]


def choose_follow_up(
    options: Sequence[FollowUpOption],
    verdicts: dict[str, str],
    weights: dict[str, int],
    band: Optional[str],
) -> Optional[int]:
    """
    Pick the follow-up question id to ask next.

    options: gradable follow-ups of the answered question (non-retired, with an approved key point).
    verdicts/weights: final verdict and weight per key point uid of the answered question.
    """
    triggered = []
    for option in options:
        verdict = verdicts.get(option.trigger_key_point_uid) if option.trigger_key_point_uid else None
        if verdict in _FOLLOW_UP_TRIGGER_ORDER:
            weight = weights.get(option.trigger_key_point_uid, 0)
            triggered.append((_FOLLOW_UP_TRIGGER_ORDER[verdict], -weight, option.position, option.question_id))
    if triggered:
        return min(triggered)[3]
    if band == "strong":
        untriggered = [option for option in options if not option.trigger_key_point_uid]
        if untriggered:
            return min(untriggered, key=lambda option: (option.position, option.question_id)).question_id
    return None
