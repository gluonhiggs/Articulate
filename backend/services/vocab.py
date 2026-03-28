"""Lexical resource signal computation for the IELTS scoring pipeline.

Exposes one public function:
    compute_vocab_signal(words, transcript) -> str

which returns a multi-section signal string consumed by the LLM prompt.
The string covers the three computable signals from LEXICAL-RESOURCE-SIGNALS.md:
  Signal 1 — Vocabulary Range     (CEFR distribution + response word count)
  Signal 2 — Vocabulary Sophistication (B2+ count, unmatched/C2+ words)
  Signal 4 — Idiomatic Language   (formulaic phrase density)
  Signal 5 — Collocation Awareness (spaCy dependency-parsed pair inventory for LLM)
  Signal 7 — Lexical Diversity    (MTLD for long texts, unique lemma ratio)
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from backend.data.oxford import WORD_TO_CEFR, WORD_TO_DATA
from backend.data.idioms import IELTS_PHRASES

logger = logging.getLogger(__name__)

# ── Stop words ────────────────────────────────────────────────────────────────
# English function words excluded from CEFR distribution.
# Counting determiners, prepositions, auxiliaries, pronouns etc. as "A1 vocabulary"
# distorts the distribution — speakers at band 7 still use "the" and "and".
# Basis: the function word / content word distinction from linguistics.
# We do NOT use NLTK/spaCy/scikit-learn stop lists — those are designed for
# information retrieval and are too aggressive for vocabulary level assessment.
_STOP_WORDS: frozenset[str] = frozenset({
    # articles / determiners
    "the", "a", "an", "this", "that", "these", "those", "my", "your", "his",
    "her", "its", "our", "their", "each", "every", "any", "all", "both",
    "few", "more", "most", "other", "some", "such", "no", "nor", "not",
    # pronouns
    "i", "me", "we", "us", "you", "he", "him", "she", "they", "them",
    "who", "whom", "which", "what", "it",
    # prepositions
    "in", "on", "at", "by", "for", "with", "about", "against", "between",
    "into", "through", "during", "before", "after", "above", "below",
    "from", "up", "down", "out", "off", "over", "under", "again", "then",
    "once", "here", "there", "when", "where", "why", "how", "of", "to",
    "as", "per",
    # conjunctions
    "and", "but", "or", "yet", "so", "nor", "although", "because", "since",
    "unless", "until", "while", "whereas", "whether", "though",
    # auxiliary / modal verbs
    "be", "is", "are", "was", "were", "been", "being", "am",
    "have", "has", "had", "having", "do", "does", "did", "done", "doing",
    "will", "would", "shall", "should", "may", "might", "must", "can",
    "could", "need", "dare", "ought",
    # high-frequency function words that pass len > 2
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "her",
    "was", "one", "our", "out", "who", "get", "now", "him", "his", "how",
    "its", "two", "own", "did", "let", "put", "say", "she", "too", "use",
    "way", "yes", "ago", "due", "per", "via", "etc", "lot", "bit",
    # discourse fillers / connectors treated as function words for CEFR purposes
    "that", "than", "then", "also", "just", "even", "like", "well",
    "much", "many", "own", "same", "very", "also", "back", "after",
    "think", "know", "said", "want", "going", "gonna", "wanna", "kind",
    "sort", "mean", "okay", "yeah", "really", "actually",
})

# ── spaCy lazy singleton ───────────────────────────────────────────────────────
_spacy_nlp = None


def _get_spacy() -> Optional[Any]:
    """Return the spaCy en_core_web_sm model, loading it once on first call."""
    global _spacy_nlp
    if _spacy_nlp is None:
        try:
            import spacy
            _spacy_nlp = spacy.load("en_core_web_sm")
        except Exception as exc:
            logger.warning("spaCy unavailable — collocation signal disabled: %s", exc)
            _spacy_nlp = False  # sentinel: don't retry
    return _spacy_nlp if _spacy_nlp is not False else None


# ── Response length label ─────────────────────────────────────────────────────
def _length_label(n: int) -> str:
    """Map raw word count to a Band-descriptor-aligned label."""
    if n < 30:
        return "very short (Band ≤5 ceiling)"
    if n < 60:
        return "short"
    if n < 100:
        return "adequate"
    return "extended"


# ── Signal 4: Idiomatic / formulaic language ──────────────────────────────────
def _compute_idiom_signal(transcript: str, total_words: int) -> str:
    """
    Count idiomatic / formulaic phrase usage from the IELTS phrase list.

    Algorithm: slide an n-gram window over lowercased transcript tokens;
    match against IELTS_PHRASES (sorted longest-first to avoid partial matches).
    Normalise by response length.

    Calibration (per 100 words):
      0       → none detected (Band 5–6)
      1–2     → limited (Band 6)
      2–4     → adequate (Band 6–7)
      4–6     → good (Band 7)
      >6      → high (Band 7–8+)
    """
    if not transcript or total_words == 0:
        return "idiomatic density: insufficient data"

    text = transcript.lower()
    # Remove punctuation except apostrophes (keep contractions)
    text = re.sub(r"[^\w\s']", " ", text)

    matched: list[str] = []
    consumed_spans: list[tuple[int, int]] = []  # avoid double-counting overlapping matches

    for phrase in IELTS_PHRASES:
        idx = 0
        while True:
            pos = text.find(phrase, idx)
            if pos == -1:
                break
            end = pos + len(phrase)
            # Check word boundary — phrase must start/end at word boundary
            before_ok = pos == 0 or text[pos - 1] == " "
            after_ok = end >= len(text) or text[end] == " "
            if before_ok and after_ok:
                # Ensure this span doesn't overlap a longer already-matched phrase
                overlaps = any(s <= pos < e or s < end <= e for s, e in consumed_spans)
                if not overlaps:
                    matched.append(phrase)
                    consumed_spans.append((pos, end))
            idx = pos + 1

    distinct = list(dict.fromkeys(matched))  # deduplicate, preserve order
    count = len(distinct)
    per_100 = round(count / total_words * 100, 1) if total_words > 0 else 0

    if per_100 == 0:
        level = "none detected (Band 5–6 indicator)"
    elif per_100 < 2:
        level = "limited (Band 6)"
    elif per_100 < 4:
        level = "adequate (Band 6–7)"
    elif per_100 < 6:
        level = "good (Band 7)"
    else:
        level = "high (Band 7–8+)"

    examples = " | ".join(f"'{p}'" for p in distinct[:4])
    base = f"idiomatic density: {per_100}/100 words ({level})"
    return f"{base}; matched: {examples}" if examples else base


# ── Signal 5: Collocation awareness ──────────────────────────────────────────
# Very high-frequency verb→object pairs that are universally natural and
# too common to be informative — skip them so the LLM inventory stays concise.
_COMMON_NATURAL_PAIRS: frozenset[tuple[str, str]] = frozenset({
    ("have", "time"), ("have", "idea"), ("have", "problem"), ("have", "effect"),
    ("get", "chance"), ("get", "idea"), ("get", "job"), ("get", "result"),
    ("do", "work"), ("do", "job"), ("do", "thing"), ("do", "research"),
    ("make", "decision"), ("make", "choice"), ("make", "point"), ("make", "sense"),
    ("take", "part"), ("take", "time"), ("take", "step"), ("take", "care"),
    ("give", "example"), ("give", "idea"), ("give", "answer"),
    ("use", "time"), ("use", "language"), ("use", "word"),
    ("see", "thing"), ("see", "point"), ("know", "thing"),
    ("think", "thing"), ("think", "way"), ("say", "thing"),
    ("find", "way"), ("find", "answer"), ("feel", "pressure"),
    ("play", "role"), ("play", "part"), ("face", "problem"), ("face", "challenge"),
    ("build", "skill"), ("learn", "skill"), ("develop", "skill"),
    ("lose", "time"), ("spend", "time"), ("save", "time"),
    ("need", "help"), ("need", "support"), ("need", "time"),
    ("go", "school"), ("go", "work"), ("come", "home"),
})


def _compute_collocation_signal(transcript: str) -> str:
    """
    Extract verb–object and adjective–noun dependency pairs from the transcript
    using spaCy and return them as an inventory string for the LLM to evaluate.

    The LLM (not a hardcoded whitelist) judges whether each pair is natural or
    non-native — this avoids false positives from a fixed lookup table.

    Very common pairs (e.g. have→time, make→decision) are skipped to keep the
    inventory concise and focus the LLM's attention on less obvious choices.

    Returns e.g.:
      "collocation pairs (spaCy): verb→obj: [cook→recipe, do→mistake];
       adj→noun: [creative→person, daily→problem]"
    or a skip message if spaCy is unavailable.
    """
    nlp = _get_spacy()
    if nlp is None:
        return "collocation pairs: unavailable (spaCy not loaded)"

    try:
        doc = nlp(transcript)
    except Exception as exc:
        logger.warning("spaCy parse failed: %s", exc)
        return "collocation pairs: parse failed"

    verb_obj_pairs: list[str] = []
    adj_noun_pairs: list[str] = []

    for token in doc:
        dep = token.dep_
        head = token.head

        # Verb–object: token is the direct object, head is the verb
        if dep in ("dobj", "obj") and head.pos_ == "VERB":
            verb_lemma = head.lemma_.lower()
            noun_lemma = token.lemma_.lower()
            pair = (verb_lemma, noun_lemma)
            if pair not in _COMMON_NATURAL_PAIRS and len(verb_obj_pairs) < 6:
                verb_obj_pairs.append(f"{verb_lemma}→{noun_lemma}")

        # Adjective–noun: token is the modifier (amod), head is the noun
        elif dep == "amod" and head.pos_ == "NOUN":
            adj_lemma = token.lemma_.lower()
            noun_lemma = head.lemma_.lower()
            if len(adj_noun_pairs) < 6:
                adj_noun_pairs.append(f"{adj_lemma}→{noun_lemma}")

    if not verb_obj_pairs and not adj_noun_pairs:
        return "collocation pairs (spaCy): none extracted"

    parts: list[str] = []
    if verb_obj_pairs:
        parts.append(f"verb→obj: [{', '.join(verb_obj_pairs)}]")
    if adj_noun_pairs:
        parts.append(f"adj→noun: [{', '.join(adj_noun_pairs)}]")

    return "collocation pairs (spaCy): " + "; ".join(parts)


# ── Main public function ──────────────────────────────────────────────────────
def compute_vocab_signal(words: List[Dict[str, Any]], transcript: str) -> str:
    """
    Compute lexical resource signal from Whisper word dicts + transcript text.

    Covers LEXICAL-RESOURCE-SIGNALS.md Signals 1, 2, 4, 5, 7.
    Returns a multi-section string for the LLM scoring prompt.
    Degrades gracefully: returns "insufficient vocabulary data" on any failure.
    """
    try:
        import simplemma
        from lexicalrichness import LexicalRichness
    except ImportError as exc:
        logger.warning("Vocab signal deps not installed (%s) — run `uv sync`", exc)
        return "insufficient vocabulary data"

    try:
        # ── Signal 1 (partial): Response length ───────────────────────────
        total_response_words = len(words)
        length_hint = _length_label(total_response_words)

        # ── Signals 1 + 2: CEFR distribution ─────────────────────────────
        # Strip punctuation, lower-case, drop short tokens and function words
        # so CEFR distribution reflects lexical choices only.
        content_words = [
            token
            for w in words
            for token in [w.get("word", "").lower().strip(".,!?;:'\"()[]—-")]
            if len(token) > 2 and token not in _STOP_WORDS
        ]

        counts: Dict[str, int] = {"A1": 0, "A2": 0, "B1": 0, "B2": 0, "C1": 0}
        matched = 0
        seen_lemmas: set[str] = set()
        unmatched_lemmas: list[str] = []
        seen_unmatched: set[str] = set()
        flagged_ipa: list[tuple[str, str]] = []

        for word in content_words:
            lemma = simplemma.lemmatize(word, lang="en")
            seen_lemmas.add(lemma)
            level = WORD_TO_CEFR.get(lemma) or WORD_TO_CEFR.get(word)
            if level and level in counts:
                counts[level] += 1
                matched += 1
                if level in ("B2", "C1"):
                    data = WORD_TO_DATA.get(lemma) or WORD_TO_DATA.get(word)
                    if data and data.get("phon_n_am"):
                        flagged_ipa.append((word, data["phon_n_am"]))
            else:
                if lemma not in seen_unmatched:
                    seen_unmatched.add(lemma)
                    unmatched_lemmas.append(lemma)

        total_content = len(content_words)
        unique_lemmas = len(seen_lemmas)

        if matched == 0 or total_content == 0:
            cefr_part = "CEFR: insufficient data (too few content words)"
        else:
            high = counts["B2"] + counts["C1"]
            pct = {lvl: round(counts[lvl] / matched * 100) for lvl in counts}
            unique_ratio = round(unique_lemmas / total_content * 100)
            cefr_part = (
                f"CEFR ({matched}/{total_content} content words matched, "
                f"{unique_lemmas} unique lemmas, {unique_ratio}% variety): "
                f"A1:{pct['A1']}% A2:{pct['A2']}% B1:{pct['B1']}% "
                f"B2:{pct['B2']}% C1:{pct['C1']}% — {high} B2+ words"
            )
            if unmatched_lemmas:
                sample = ", ".join(unmatched_lemmas[:8])
                cefr_part += f" | unmatched (possible C2+/specialist): {sample}"
            if flagged_ipa:
                ipa_hints = "; ".join(f"{w} {ipa}" for w, ipa in flagged_ipa[:5])
                cefr_part += f" | B2+ refs: {ipa_hints}"

        # ── Signal 7: Lexical diversity (MTLD) ───────────────────────────
        word_list = transcript.lower().split()
        if len(word_list) >= 50:
            lex = LexicalRichness(transcript)
            mtld_score = round(lex.mtld(threshold=0.72), 1)
            if mtld_score < 50:
                lvl = "basic"
            elif mtld_score < 70:
                lvl = "intermediate"
            elif mtld_score < 90:
                lvl = "upper-intermediate"
            else:
                lvl = "advanced"
            diversity_part = f"lexical diversity MTLD={mtld_score} ({lvl})"
        else:
            diversity_part = "lexical diversity: insufficient data (<50 words)"

        # ── Signal 4: Idiomatic / formulaic density ───────────────────────
        idiom_part = _compute_idiom_signal(transcript, total_response_words)

        # ── Signal 5: Collocation awareness ──────────────────────────────
        collocation_part = _compute_collocation_signal(transcript)

        return "\n".join([
            f"response length: {total_response_words} words ({length_hint})",
            cefr_part,
            diversity_part,
            idiom_part,
            collocation_part,
        ])

    except Exception as exc:
        logger.warning("Vocab signal computation failed: %s", exc)
        return "insufficient vocabulary data"
