# Pronunciation Signal Design

**Date:** 2026-04-08
**Status:** Approved

## Problem

Pronunciation is the only IELTS scoring criterion with no dedicated computed signal. The LLM currently receives `mispronounced_words` — a flat comma-separated string of word strings with a binary threshold (< 0.6), mixing two unrelated signals: low STT confidence (pronunciation evidence) and pause-based disfluency (fluency evidence). This gives the LLM no aggregate picture of pronunciation quality and no severity distinction between words.

## Goal

Replace `mispronounced_words` with a structured `pronunciation_signal` that gives the LLM:
1. An aggregate distribution of pronunciation quality across the full response
2. Per-word detail grouped by severity tier
3. Explicit band anchors derived from official IELTS descriptors

## Design

### Confidence Tiers

STT per-word confidence (probability) is used as a proxy for pronunciation clarity. The threshold is raised from 0.6 to 0.9 — any word below 0.9 is considered imperfect to some degree.

| Tier | Probability range | Meaning |
|------|-------------------|---------|
| clear | ≥ 0.9 | Well-articulated, not included in signal detail |
| imprecise | 0.8 – 0.9 | Minor deviation, unlikely to affect clarity |
| unclear | 0.7 – 0.8 | Noticeable mispronunciation, occasional lack of clarity |
| poor | < 0.7 | Likely seriously mispronounced or unintelligible |

### Signal Format

Two-layer output string:

```
clear: 87% | imprecise: 8% (0.8–0.9) | unclear: 4% (0.7–0.8) | poor: 2% (<0.7) | total: 52 words
poorly pronounced (<0.7): especial, comfortable
unclear (0.7–0.8): thought, world
imprecise (0.8–0.9): morning, study
```

- Tiers with zero words are omitted from the word list
- If total words is zero or all probabilities are 1.0 (Groq cloud mode), signal is `"not available (cloud mode)"`

### Band Anchors

Derived from official IELTS pronunciation descriptors in BAND-SCORES.md:

| Band | Distribution |
|------|-------------|
| 8–9 | clear_pct ≥ 95%, poor_pct ≈ 0% — "effortlessly/easily understood" |
| 7–8 | clear_pct 85–95%, few unclear/poor |
| 6–7 | clear_pct 75–85%, some unclear, few poor — "occasional lack of clarity" |
| 5–6 | clear_pct 65–75%, moderate unclear/poor |
| 4–5 | clear_pct 50–65%, significant poor_pct — "frequently mispronounced, requires effort" |
| 3–4 | clear_pct 30–50%, most words unclear/poor |
| 2–3 | clear_pct < 30% |

### Disfluent Words

`disfluent_words` (words preceded by a pause ≥ 0.5s) is kept as a separate variable in `attempts.py` and is NOT included in `pronunciation_signal`. It will be addressed in a future fluency signal improvement.

## Implementation Scope

### New function

`compute_pronunciation_signal(words: list[dict]) -> str` in `backend/services/vocab.py`

- Input: raw STT words list (each dict has `word`, `start`, `end`, `probability`)
- Returns the two-layer signal string
- Returns `"not available (cloud mode)"` when all probabilities are exactly 1.0 (Groq indicator) or word list is empty. A local-mode response where all words happen to score ≥ 0.9 still returns a normal signal showing `clear: 100%`.

### Files changed

| File | Change |
|------|--------|
| `backend/services/vocab.py` | Add `compute_pronunciation_signal()` |
| `backend/api/attempts.py` | Remove `mispronounced_words` variable, call `compute_pronunciation_signal(words)` directly, pass `pronunciation_signal` to `score_attempt()` |
| `backend/services/scoring.py` | Replace `mispronounced_words: List[str]` param with `pronunciation_signal: str`, update `_build_prompt()` template replace |
| `backend/prompts/score_part1.txt` | Replace `{mispronounced_words}` with `{pronunciation_signal}`, update Pronunciation criterion with band anchors and tier explanation |
| `backend/prompts/score_part2.txt` | Same as score_part1.txt |
| `backend/prompts/score_part3.txt` | Same as score_part1.txt |
| `backend/scripts/eval_scoring.py` | Replace `mispronounced_words=[]` with `pronunciation_signal=""` |
| `tests/test_signals.py` | Add `TestPronunciationSignal` class |

### Prompt changes (Pronunciation criterion)

Replace current single-line pronunciation criterion with:

```
**Pronunciation**
Clarity and intelligibility across the full response.

Use PRONUNCIATION SIGNAL to anchor your score:
- `clear_pct` = % of words prob ≥ 0.9 — proxy for well-articulated speech
- `imprecise_pct` = % of words 0.8–0.9 — minor deviation, unlikely to affect clarity
- `unclear_pct` = % of words 0.7–0.8 — noticeable mispronunciation, occasional lack of clarity
- `poor_pct` = % of words < 0.7 — likely seriously mispronounced or unintelligible

Band anchors (from official IELTS descriptors):
- clear_pct ≥ 95%, poor_pct ≈ 0%          → Band 8–9 ("effortlessly/easily understood")
- clear_pct 85–95%, few unclear/poor        → Band 7–8
- clear_pct 75–85%, some unclear, few poor  → Band 6–7 ("occasional lack of clarity")
- clear_pct 65–75%, moderate unclear/poor   → Band 5–6
- clear_pct 50–65%, significant poor_pct    → Band 4–5 ("frequently mispronounced, requires effort")
- clear_pct 30–50%, most words unclear/poor → Band 3–4
- clear_pct < 30%                           → Band 2–3

Specific words are listed per tier so you can reference them in feedback_text.
If signal is "not available (cloud mode)", score pronunciation conservatively
based on transcript legibility alone.
```

## Testing

`TestPronunciationSignal` covers:
- All-clear local mode response (all prob ≥ 0.9 but not all exactly 1.0) → returns `clear: 100%` signal
- Groq mode (all prob exactly = 1.0) → `"not available (cloud mode)"`
- Mixed response with words across all tiers
- Empty words list → `"not available (cloud mode)"`
- Tier with zero words → that line omitted from word list
- Percentages sum correctly
- Words sorted/grouped correctly per tier
