"""Vocabulary signal computation for the IELTS scoring pipeline."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from backend.data.oxford import WORD_TO_CEFR, WORD_TO_DATA

logger = logging.getLogger(__name__)

# English function words excluded from CEFR distribution.
# Counting determiners, prepositions, auxiliaries, pronouns etc. as "A1 vocabulary"
# distorts the distribution — speakers at band 7 still use "the" and "and".
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
    # common function words that pass len > 2 filter
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "her",
    "was", "one", "our", "out", "who", "get", "now", "him", "his", "how",
    "its", "two", "own", "did", "let", "put", "say", "she", "too", "use",
    "way", "yes", "ago", "due", "per", "via", "etc", "lot", "bit",
    # relative / question words often used as connectors
    "that", "than", "then", "also", "just", "even", "like", "well",
    "much", "many", "own", "same", "very", "also", "back", "after",
    "think", "know", "said", "want", "going", "gonna", "wanna", "kind",
    "sort", "mean", "okay", "yeah", "really", "actually",
})


def compute_vocab_signal(words: List[Dict[str, Any]], transcript: str) -> str:
    """
    Compute vocabulary signal from Whisper word timestamps + transcript text.

    Pipeline:
      content words → simplemma.lemmatize() → Oxford 5000 lookup (5 900+ words)
      → CEFR level distribution + IPA refs for B2+ words
      transcript text → LexicalRichness.mtld() → lexical diversity score

    Returns a signal string for the LLM scoring prompt.
    Degrades gracefully: returns "insufficient vocabulary data" on any failure.

    Example output:
      "CEFR (89/140 words matched): A1:38% A2:25% B1:20% B2:14% C1:3% — 25 B2+ words;
       lexical diversity MTLD=72.4 (upper-intermediate)"
    """
    # Lazy imports — these packages are optional; pipeline still works if missing
    try:
        import simplemma
        from lexicalrichness import LexicalRichness
    except ImportError as exc:
        logger.warning("Vocab signal deps not installed (%s) — run `uv sync`", exc)
        return "insufficient vocabulary data"

    try:
        # ── CEFR level distribution ───────────────────────────────────────
        # Strip punctuation, lower-case, drop very short tokens and function
        # words so the CEFR distribution reflects lexical choices only.
        content_words = [
            token
            for w in words
            for token in [w.get("word", "").lower().strip(".,!?;:'\"()[]—-")]
            if len(token) > 2 and token not in _STOP_WORDS
        ]

        counts: Dict[str, int] = {"A1": 0, "A2": 0, "B1": 0, "B2": 0, "C1": 0}
        matched = 0
        seen_lemmas: set[str] = set()           # unique lemmas for type diversity
        unmatched_lemmas: list[str] = []         # distinct content lemmas not in Oxford 5000
        seen_unmatched: set[str] = set()
        flagged_ipa: list[tuple[str, str]] = []  # (word, phon_n_am) for B2+ words
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
                # Collect distinct unmatched lemmas — may be C2+, proper nouns, or errors
                if lemma not in seen_unmatched:
                    seen_unmatched.add(lemma)
                    unmatched_lemmas.append(lemma)

        total = len(content_words)
        unique_lemmas = len(seen_lemmas)
        if matched == 0 or total == 0:
            cefr_part = "CEFR: insufficient data (too few matched words)"
        else:
            high = counts["B2"] + counts["C1"]
            pct = {lvl: round(counts[lvl] / matched * 100) for lvl in counts}
            # Unique lemma ratio: how varied is the vocabulary (works for short texts too)
            unique_ratio = round(unique_lemmas / total * 100) if total > 0 else 0
            cefr_part = (
                f"CEFR ({matched}/{total} content words matched, "
                f"{unique_lemmas} unique lemmas, {unique_ratio}% variety): "
                f"A1:{pct['A1']}% A2:{pct['A2']}% B1:{pct['B1']}% "
                f"B2:{pct['B2']}% C1:{pct['C1']}% — {high} B2+ words"
            )
            # Report unmatched words (capped at 8) — these may be C2+ or specialist vocab
            if unmatched_lemmas:
                sample = ", ".join(unmatched_lemmas[:8])
                cefr_part += f" | unmatched (possible C2+/specialist): {sample}"
            if flagged_ipa:
                ipa_hints = "; ".join(
                    f"{w} {ipa}" for w, ipa in flagged_ipa[:5]
                )
                cefr_part += f" | B2+ pronunciation refs: {ipa_hints}"

        # ── Lexical diversity (MTLD) ──────────────────────────────────────
        # MTLD (Measure of Textual Lexical Diversity) is an objective score the
        # LLM cannot compute from the transcript text alone — that's why it's
        # included here rather than letting the LLM infer it.
        # Reference ranges: <50 basic, 50-70 intermediate, 70-90 upper-intermediate, 90+ advanced
        word_list = transcript.lower().split()
        if len(word_list) >= 50:
            lex = LexicalRichness(transcript)
            mtld_score = round(lex.mtld(threshold=0.72), 1)
            if mtld_score < 50:
                level_hint = "basic"
            elif mtld_score < 70:
                level_hint = "intermediate"
            elif mtld_score < 90:
                level_hint = "upper-intermediate"
            else:
                level_hint = "advanced"
            mtld_part = f"lexical diversity MTLD={mtld_score} ({level_hint})"
        else:
            mtld_part = "lexical diversity: insufficient data (<50 words)"

        return f"{cefr_part}; {mtld_part}"

    except Exception as exc:
        logger.warning("Vocab signal computation failed: %s", exc)
        return "insufficient vocabulary data"
