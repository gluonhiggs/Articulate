"""Vocabulary signal computation for the IELTS scoring pipeline."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from backend.data.oxford import WORD_TO_CEFR, WORD_TO_DATA

logger = logging.getLogger(__name__)


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
        content_words = [
            w["word"].lower().strip(".,!?;:'\"()[]")
            for w in words
            if len(w.get("word", "").strip()) > 2
        ]

        counts: Dict[str, int] = {"A1": 0, "A2": 0, "B1": 0, "B2": 0, "C1": 0}
        matched = 0
        flagged_ipa: list[tuple[str, str]] = []  # (word, phon_n_am) for B2+ words
        for word in content_words:
            lemma = simplemma.lemmatize(word, lang="en")
            level = WORD_TO_CEFR.get(lemma) or WORD_TO_CEFR.get(word)
            if level and level in counts:
                counts[level] += 1
                matched += 1
                if level in ("B2", "C1"):
                    data = WORD_TO_DATA.get(lemma) or WORD_TO_DATA.get(word)
                    if data and data.get("phon_n_am"):
                        flagged_ipa.append((word, data["phon_n_am"]))

        total = len(content_words)
        if matched == 0 or total == 0:
            cefr_part = "CEFR: insufficient data (too few matched words)"
        else:
            high = counts["B2"] + counts["C1"]
            pct = {lvl: round(counts[lvl] / matched * 100) for lvl in counts}
            cefr_part = (
                f"CEFR ({matched}/{total} words matched): "
                f"A1:{pct['A1']}% A2:{pct['A2']}% B1:{pct['B1']}% "
                f"B2:{pct['B2']}% C1:{pct['C1']}% — {high} B2+ words"
            )
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
