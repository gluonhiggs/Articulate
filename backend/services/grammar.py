from __future__ import annotations

import logging
import re
import threading
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

_lt_tool = None
_lt_tool_init_attempted = False
_lt_lock = threading.Lock()


def get_lt_tool():
    global _lt_tool, _lt_tool_init_attempted
    with _lt_lock:
        if _lt_tool_init_attempted:
            return _lt_tool
        _lt_tool_init_attempted = True
    try:
        import language_tool_python  # type: ignore[import]

        _lt_tool = language_tool_python.LanguageTool("en-US")
        _lt_tool.picky = True  # enable stricter rule set (sent as request param to /check)
        logger.info("LanguageTool initialized (local, picky=True)")
    except Exception as exc:
        logger.warning("LanguageTool local unavailable (Java required): %s", exc)
        try:
            import language_tool_python  # type: ignore[import]

            # Fallback: sends transcript to languagetool.org - no Java needed.
            _lt_tool = language_tool_python.LanguageToolPublicAPI("en-US")
            logger.info("LanguageTool initialized (public API fallback)")
        except Exception as exc2:
            logger.warning("LanguageTool public API also unavailable: %s", exc2)
            _lt_tool = None
    return _lt_tool


# Whisper (Groq API) may capitalise the first word of segments separated by
# pauses. LanguageTool flags these as UPPERCASE_SENTENCE_START and related
# casing/punctuation rules - transcription artefacts, not speaker errors, so
# they must not be reported as grammar mistakes.
#
# Kept: GRAMMAR, CONFUSED_WORDS, MISC, TYPOS - all genuine error categories.

_LT_FILTERED_RULE_IDS: frozenset[str] = frozenset(
    {
        # VAD segment-boundary capitalisation - primary transcription artefact
        "UPPERCASE_SENTENCE_START",
        # Whitespace / formatting - concepts absent from speech
        "WHITESPACE_RULE",
        "EN_QUOTES",
        # Punctuation absence - spoken language has no terminal punctuation
        "COMMA_PARENTHESIS_WHITESPACE",
        "PUNCTUATION_PARAGRAPH_END",
        "UNLIKELY_OPENING_PUNCTUATION",
        # Style rules outside the IELTS speaking rubric
        "TOO_LONG_SENTENCE",
        "ENGLISH_WORD_REPEAT_BEGINNING_RULE",
    }
)

_LT_FILTERED_CATEGORIES: frozenset[str] = frozenset(
    {
        "CASING",  # all casing rules - meaningless in speech
        "TYPOGRAPHY",  # formatting rules - meaningless in speech
        "PUNCTUATION",  # missing / wrong punctuation - transcription artefact
        "STYLE",  # subjective style - not an IELTS speaking criterion
        "REDUNDANCY",  # wordy phrasing - not penalised in IELTS speaking
        # Word repetition and REP_PASSIVE_VOICE: advice with no correction to make, and
        # word variety is already measured separately by MTLD. Counting these as errors
        # both buried the real mistakes and lowered the delivery score for no fault.
        "REPETITIONS_STYLE",
        # Dialect preference ("afterwards" -> "afterward"), never a mistake either way.
        "BRITISH_ENGLISH",
        "AMERICAN_ENGLISH",
    }
)

# Rules that belong to filtered categories but catch genuine errors worth surfacing.
_LT_WHITELISTED_RULE_IDS: frozenset[str] = frozenset(
    {
        "BORED_OF",  # STYLE: 'bored of' -> 'bored with/by' - real preposition error
    }
)


def is_speech_artifact(match) -> bool:
    return match.rule_id in _LT_FILTERED_RULE_IDS or (
        match.rule_id not in _LT_WHITELISTED_RULE_IDS and match.category in _LT_FILTERED_CATEGORIES
    )


def _term_spans(text: str, terms: Iterable[str]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for term in terms:
        term = term.strip()
        if not term:
            continue
        pattern = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", re.IGNORECASE)
        spans.extend((m.start(), m.end()) for m in pattern.finditer(text))
    return spans


def check_grammar(text: str, ignore_terms: Iterable[str] = ()) -> Optional[list[dict]]:
    """
    Grammar issues in spoken text, or None when LanguageTool is unavailable.

    Blocking (LanguageTool may start Java): run it in an executor. Spelling matches are
    dropped because ASR output has no spelling errors, only mis-hearings.
    """
    lt = get_lt_tool()
    if lt is None:
        return None
    try:
        matches = lt.check(text)
    except Exception as exc:
        logger.warning("LanguageTool check failed: %s", exc)
        return None

    ignored = _term_spans(text, ignore_terms)
    issues: list[dict] = []
    for m in matches:
        if is_speech_artifact(m) or m.category == "TYPOS" or m.rule_id.startswith("MORFOLOGIK"):
            continue
        start, end = m.offset, m.offset + m.error_length
        if any(start < span_end and span_start < end for span_start, span_end in ignored):
            continue
        issues.append(
            {
                "text": text[start:end],
                "message": m.message,
                "replacements": list(m.replacements[:3]),
                "offset": start,
                "rule_id": m.rule_id,
            }
        )
    return issues
