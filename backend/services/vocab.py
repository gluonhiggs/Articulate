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
from collections import defaultdict
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


# ── Signal 3: Sentence complexity ────────────────────────────────────────────
# Universal Dependencies arc labels whose presence on any token makes the
# containing sentence "complex" for IELTS GRA purposes.
# Handled directly (dep in set):
#   advcl  — adverbial clause modifier  (because/when/if/although…)
#   ccomp  — clausal complement          (I think that…, she said…)
#   relcl  — relative clause modifier    (the book that I read)
#   acl    — adjectival / participial clause (the person sitting next to me)
# Handled via separate SCONJ POS guard (see compute_sentence_complexity):
#   mark   — subordinating conjunction: fires when pos_==SCONJ
# Intentionally excluded:
#   xcomp  — infinitive complement ("I want to go") — not an IELTS complex sentence
#   csubj  — clausal subject (rare in spoken English, omission is harmless)
_SUBORDINATE_ARCS_DIRECT: frozenset[str] = frozenset({
    "advcl",
    "ccomp",
    "relcl",
    "acl",
})


def _map_complexity_band(
    complex_sentence_rate: float,
    error_density_ratio: float,
) -> str:
    """Map (complex_sentence_rate, error_density_ratio) to an IELTS GRA band hint.

    Two-dimensional heuristic grounded in rubric qualitative language:
      B4 — "structures are repetitive" → almost no complex sentences
      B5 — complex attempted but error-prone (density ratio ≥ 2.0)
      B6 — complex used with limited flexibility
      B7 — "a range of structures flexibly used"

    These thresholds are heuristics, not rubric-specified numbers.
    The LLM should override if the transcript contradicts the signal.
    """
    if complex_sentence_rate < 0.20:
        return "B4"
    if complex_sentence_rate < 0.45:
        if error_density_ratio >= 2.0:
            return "B5"
        if error_density_ratio >= 1.5:
            return "B6"
        return "B7"
    # complex_sentence_rate >= 0.45
    if error_density_ratio >= 2.0:
        return "B6"
    if error_density_ratio >= 1.5:
        return "B6-B7"
    return "B7"


def compute_sentence_complexity(
    transcript: str,
    sent_spans: list[tuple[int, int]],
    filtered_matches: list,
) -> dict:
    """Signal 3: Subordinate-clause rate and error-concentration ratio.

    Args:
        transcript:       Full response text.
        sent_spans:       (start, end) character offsets per sentence
                          (from _sentence_spans in attempts.py).
        filtered_matches: LanguageTool match objects with .offset attribute.

    Returns a dict containing at minimum:
        band_hint (str)  — e.g. "B5", "B6-B7", "insufficient_data"
        detail    (str)  — one-line signal string for grammar_context

    All other keys (n_sentences, n_complex, etc.) are informational.
    Degrades gracefully when spaCy is unavailable or transcript is too short.
    """
    nlp = _get_spacy()
    if nlp is None:
        return {
            "band_hint": "unavailable",
            "detail": "complexity: spaCy unavailable",
        }

    n_sentences = len(sent_spans)
    if n_sentences < 3:
        return {
            "band_hint": "insufficient_data",
            "detail": "complexity: insufficient data (< 3 sentences)",
        }

    # ── Classify each sentence as complex (has subordinate clause) or simple ──
    complex_sents: set[int] = set()
    try:
        for idx, (s_start, s_end) in enumerate(sent_spans):
            sent_text = transcript[s_start:s_end]
            sent_doc = nlp(sent_text)
            for token in sent_doc:
                dep = token.dep_
                if dep in _SUBORDINATE_ARCS_DIRECT:
                    complex_sents.add(idx)
                    break
                if dep == "mark" and token.pos_ == "SCONJ":
                    complex_sents.add(idx)
                    break
    except Exception as exc:
        logger.warning("spaCy complexity parse failed: %s", exc)
        return {
            "band_hint": "unavailable",
            "detail": "complexity: parse failed",
        }

    n_complex = len(complex_sents)
    n_simple = n_sentences - n_complex
    complex_sentence_rate = n_complex / n_sentences

    # ── Map each LT error to its sentence index ───────────────────────────────
    errors_by_sent: defaultdict[int, set[int]] = defaultdict(set)
    for m in filtered_matches:
        for i, (s, e) in enumerate(sent_spans):
            if s <= m.offset < e:
                errors_by_sent[i].add(m.offset)
                break

    n_errors_complex = sum(len(errors_by_sent[i]) for i in complex_sents)
    n_errors_simple = sum(
        len(errors_by_sent[i]) for i in range(n_sentences) if i not in complex_sents
    )

    # ── Error density ratio ───────────────────────────────────────────────────
    # (errors per complex sentence) / (errors per simple sentence)
    # Ratio > 1 → errors concentrate in complex sentences (accuracy gap at
    # higher structural ambition). Avoids the base-rate problem of proportion.
    density_complex = n_errors_complex / n_complex if n_complex > 0 else 0.0
    density_simple = n_errors_simple / n_simple if n_simple > 0 else 0.0

    if density_simple == 0:
        # No errors in simple sentences
        error_density_ratio = 3.0 if density_complex > 0 else 1.0
    else:
        error_density_ratio = round(density_complex / density_simple, 2)

    band_hint = _map_complexity_band(complex_sentence_rate, error_density_ratio)

    detail = (
        f"complexity: {n_complex}/{n_sentences} complex sentences "
        f"({round(complex_sentence_rate * 100)}%), "
        f"error density ratio {error_density_ratio:.2f} "
        f"(complex {density_complex:.2f} err/sent vs simple {density_simple:.2f} err/sent); "
        f"band_hint={band_hint}"
    )

    return {
        "n_sentences": n_sentences,
        "n_complex": n_complex,
        "n_simple": n_simple,
        "complex_sentence_rate": round(complex_sentence_rate, 3),
        "n_errors_complex": n_errors_complex,
        "n_errors_simple": n_errors_simple,
        "error_density_ratio": error_density_ratio,
        "band_hint": band_hint,
        "detail": detail,
    }


# ── Response length label ─────────────────────────────────────────────────────
def _mtld(words: list[str], threshold: float = 0.72) -> float:
    """Measure of Textual Lexical Diversity (McCarthy & Jarvis 2010).

    Bidirectional: average of forward and backward pass.
    Matches the reference algorithm in McCarthy & Jarvis (2010, p. 385)
    and the lexicalrichness library — without its scipy/pandas/matplotlib deps.
    """
    def _one_pass(seq: list[str]) -> float:
        types: set[str] = set()
        token_count = 0
        factor_count = 0.0
        ttr = 1.0

        for w in seq:
            token_count += 1
            types.add(w)
            ttr = len(types) / token_count
            if ttr <= threshold:
                factor_count += 1
                types = set()
                token_count = 0

        # Partial factor for the trailing segment
        if token_count > 0:
            factor_count += (1 - ttr) / (1 - threshold)

        # Edge case: TTR never fell to threshold (e.g. all-unique words)
        if factor_count == 0:
            overall_ttr = len(set(seq)) / len(seq)
            factor_count = 1.0 if overall_ttr == 1.0 else (1 - overall_ttr) / (1 - threshold)

        return len(seq) / factor_count

    if len(words) < 2:
        return 0.0
    return (_one_pass(words) + _one_pass(list(reversed(words)))) / 2


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
            mtld_score = round(_mtld(word_list), 1)
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
