# Lexical Resource — Signals Reference

This file maps every distinct signal needed to score the **Lexical Resource** criterion
to its evidence in `BAND-SCORES.original.md`.

At the UI level this criterion is labelled "Vocabulary". Underneath, the rubric assesses
seven distinct properties. Five are fully or partially computable; two can only be assessed
by the LLM reading the transcript.

---

## How scoring works (overview)

```
Audio → Whisper → transcript + word dicts
                        │
                 compute_vocab_signal()
                        │
          ┌─────────────┴──────────────┐
          │  computed signals bundled  │   + raw transcript
          │  into vocab_signal string  │   + BAND-SCORES.md
          └─────────────┬──────────────┘
                        ▼
                       LLM
                        │
                        ▼
              vocabulary score (0–9, 0.5 steps)
```

The LLM uses the computed signals as objective anchors and reads the transcript
directly for signals it must judge subjectively.

---

## The 7 signals

### Signal 1 — Vocabulary Range (breadth across topics)

**What it is:** How wide is the speaker's vocabulary? Can they discuss any topic, or
only familiar/personal ones?

**Band evidence from BAND-SCORES.original.md:**

| Band | Exact wording |
|------|---------------|
| 9 | "Uses vocabulary with full flexibility and precision **in all topics**" |
| 8 | "Uses a wide vocabulary resource readily and flexibly **to discuss all topics**" |
| 7 | "Uses vocabulary resource flexibly **to discuss a variety of topics**" |
| 6 | "Has a wide enough vocabulary **to discuss topics at length**" |
| 5 | "Manages to talk about **familiar and unfamiliar topics** but uses vocabulary with limited flexibility" |
| 4 | "Is able to talk about **familiar topics** but can only convey basic meaning on **unfamiliar topics**" |
| 3 | "Uses simple vocabulary to convey **personal information**" / "Has insufficient vocabulary for **less familiar topics**" |
| 2 | "Only produces isolated words or memorised utterances" |
| 1 | No rateable language |

**Measurability:** Partially computable.
- CEFR distribution of content words (after stop-word filtering) is a proxy for range.
  A Band 5 speaker dominates with A1/A2 words; a Band 7 speaker shows sustained B1/B2.
- Total content word count (response length) captures the "at length" vs "basic meaning"
  distinction: very short answers are a Band 5–6 ceiling regardless of word choice.
- **What we cannot compute:** Whether the vocabulary is appropriate *for the topic asked*
  (e.g., using cooking vocabulary on an economics question). LLM judges this from context.

**Status:** ✅ Fully implemented — CEFR distribution + B2+ count + response word count (with
band-aligned label: very short / short / adequate / extended) all in `vocab_signal`.

---

### Signal 2 — Vocabulary Sophistication (less common / advanced items)

**What it is:** Does the speaker reach beyond common A1–B1 words? Do they use B2/C1
words — the "less common" items the rubric references at Band 7–8?

**Band evidence:**

| Band | Exact wording |
|------|---------------|
| 9 | "Uses idiomatic language naturally and accurately" (implies mastery of full range) |
| 8 | "Uses less common and idiomatic vocabulary **skilfully**, with occasional inaccuracies" |
| 7 | "Uses **some** less common and idiomatic vocabulary" |
| 6 | (no explicit mention — implied by the gap between B6 and B7) |
| 5 | "Limited flexibility" — implicitly relies on common vocabulary |
| 4 | "Frequent errors in word choice" — attempts advanced words incorrectly |
| 3 | "Simple vocabulary only" |

**Measurability:** ✅ Computable.
- B2/C1 token proportion from CEFR distribution.
- Unmatched content words (not in Oxford 5000) reported as possible C2+/specialist vocab.

**Status:** ✅ Implemented — `vocab_signal` reports B2+ count and unmatched words.

---

### Signal 3 — Precision & Accuracy in Word Choice

**What it is:** Does the speaker choose the *right* word — the one that fits the meaning
precisely? Or do they choose near-miss words that are wrong but understandable?

**Band evidence:**

| Band | Exact wording |
|------|---------------|
| 9 | "Full flexibility and **precise use** in all contexts" |
| 8 | "To convey **precise meaning**" |
| 7 | "**Some inappropriate choices**" (precision is not yet consistent) |
| 6 | "Vocabulary use **may be inappropriate** but meaning is clear" |
| 4 | "Makes **frequent errors in word choice**" |

**Measurability:** ❌ LLM-only.
Computing precision requires knowing what the speaker *meant* to say — i.e., comparing
intended meaning to word chosen. This requires reading the sentence in context and
knowing whether a word fits. No purely statistical method can do this reliably.

**Status:** ❌ Not computable. LLM infers from transcript against rubric.

---

### Signal 4 — Idiomatic Language

**What it is:** Does the speaker use fixed expressions, idioms, and collocational chunks
that native speakers reach for naturally ("a wide range", "it goes without saying",
"on the other hand")?

**Band evidence:**

| Band | Exact wording |
|------|---------------|
| 9 | "Uses idiomatic language **naturally and accurately**" |
| 8 | "Less common and **idiomatic** vocabulary skilfully" |
| 7 | "Some less common and **idiomatic** vocabulary" |
| 6 | (not mentioned — absence of idioms is implied at this level) |
| 5–2 | (not mentioned) |

**Measurability:** Partially computable.
- A curated list of IELTS-relevant formulaic phrases (`backend/data/idioms.py`) is matched
  against the transcript. Density is computed as matches per 100 words and mapped to a
  band-aligned label (none → Band 5–6, limited → Band 6, adequate → Band 6–7, good → Band 7,
  high → Band 7–8+).
- **Limitation:** The list is a fixed lower-bound — idioms not on it are invisible to the
  counter. The prompts explicitly instruct the LLM to detect additional idiomatic language
  from the transcript and weigh it in the score.

**Status:** ✅ Implemented — `_compute_idiom_signal()` in `vocab_signal`.
LLM also reads transcript for idioms beyond the list (prompt instruction in place).

---

### Signal 5 — Collocation Awareness

**What it is:** Does the speaker know which words go together? ("make a decision" not
"do a decision"; "heavy rain" not "big rain"; "try new recipes" not "cook new recipes").
Collocation errors are distinct from grammar errors — the grammar is fine but the word
combination sounds unnatural to a native speaker.

**Band evidence:**

| Band | Exact wording |
|------|---------------|
| 8 | "Occasional inaccuracies in **word choice and collocation**" |
| 7 | "Some awareness of style and **collocation**, with some inappropriate choices" |
| 6 | (not mentioned — collocational errors at Band 6 are subsumed under "inappropriacies") |

Note: Collocation only appears explicitly at Band 7–8. This is why it is the primary
discriminator between Band 6 and Band 7.

**Measurability:** Partially computable.
- spaCy dependency parsing extracts verb→object (`dobj`/`obj`) and adjective→noun (`amod`)
  pairs from the transcript. Very common pairs (e.g. `have→time`, `make→decision`) are
  filtered out via `_COMMON_NATURAL_PAIRS` to keep the inventory concise.
- The extracted pairs are passed as a raw inventory to the LLM, which evaluates naturalness.
  This avoids false positives from a fixed lookup table — the LLM's linguistic knowledge
  judges any pair regardless of whether it's in a predefined list.
- **Limitation:** spaCy extracts surface pairs but cannot detect omitted collocations (e.g.
  if the speaker avoided "heavy rain" by saying "big rain" — the pair `big→rain` will appear
  and the LLM should flag it). Pairs not mentioned in the transcript are invisible.

**Status:** ✅ Implemented — `_compute_collocation_signal()` sends pair inventory to LLM.
LLM evaluates each pair for naturalness (prompt instruction in place).

---

### Signal 6 — Paraphrase Ability

**What it is:** When the speaker doesn't know or can't retrieve a word, can they
describe it another way? Does the paraphrase succeed in conveying the same meaning?

**Band evidence:**

| Band | Exact wording |
|------|---------------|
| 8–9 | "Uses paraphrase **effectively as required**" |
| 7 | "Uses paraphrase **effectively**" |
| 6 | "**Generally** paraphrases successfully" |
| 5 | "Attempts to use paraphrase but with **mixed success**" |
| 4 | "**Rarely** attempts paraphrase" |
| 3–2 | (not mentioned — implies no paraphrase strategy) |

**Measurability:** ❌ LLM-only.
Detecting whether a speaker has paraphrased (rather than used the word directly), and
whether that paraphrase successfully conveyed the intended meaning, requires semantic
understanding that is beyond statistical signals.

**Status:** ❌ Not computable. LLM infers from transcript.

---

### Signal 7 — Lexical Diversity / Flexibility

**What it is:** Does the speaker repeat the same words, or do they vary their vocabulary?
At higher bands, speakers avoid word repetition and deploy a broad range of forms.

**Band evidence:**

| Band | Exact wording |
|------|---------------|
| 9 | "**Total flexibility** and precise use" |
| 8 | "**Readily and flexibly** used to discuss all topics" |
| 7 | "Vocabulary resource **flexibly** used" |
| 6 | "Wide enough vocabulary" (adequate but not described as flexible) |
| 5 | "**Limited flexibility**" |

**Measurability:** ✅ Computable.
- **MTLD** (Measure of Textual Lexical Diversity): objective measure of how long the text
  runs before vocabulary starts repeating. Valid for responses ≥ 50 words.
- **Unique lemma ratio**: unique distinct lemmas ÷ total content word tokens. Works for
  short Part 1 responses where MTLD cannot be computed.
- Both are in `vocab_signal`.

**Status:** ✅ Implemented — MTLD + unique lemma ratio in `vocab_signal`.

---

## Summary table

| # | Signal | Bands it distinguishes | Computable? | Status |
|---|--------|------------------------|-------------|--------|
| 1 | Vocabulary Range | B2 ↔ B3 ↔ B4 ↔ B5 ↔ B6 ↔ B7 ↔ B9 | Partially | ✅ CEFR distribution + word count + length label |
| 2 | Vocabulary Sophistication (less common words) | B6 ↔ B7 ↔ B8 ↔ B9 | Yes | ✅ B2+ count + unmatched words |
| 3 | Precision / Accuracy in word choice | B4 ↔ B6 ↔ B7 ↔ B8 ↔ B9 | No | LLM-only (reads transcript) |
| 4 | Idiomatic Language | B7 ↔ B8 ↔ B9 | Partially | ✅ Density from `idioms.py` (lower-bound) + LLM reads transcript for remainder |
| 5 | Collocation Awareness | **B6 ↔ B7** ↔ B8 | Partially | ✅ spaCy pair inventory → LLM evaluates naturalness |
| 6 | Paraphrase Ability | B4 ↔ B5 ↔ B6 ↔ B7 | No | LLM-only (reads transcript) |
| 7 | Lexical Diversity / Flexibility | B5 ↔ B6 ↔ B7 ↔ B8 ↔ B9 | Yes | ✅ MTLD + unique lemma ratio |

**Remaining gap:** Signals 3 and 6 are LLM-only and always will be — they require semantic
understanding. Signals 4 and 5 have known limitations (fixed list / surface-only extraction)
but the prompts instruct the LLM to compensate with its own transcript reading.

---

## What `vocab_signal` currently sends to the LLM

Five sections, newline-separated:

```
response length: {N} words (very short|short|adequate|extended)

CEFR ({matched}/{total_content} content words matched, {unique} unique lemmas, {ratio}% variety):
A1:{pct}% A2:{pct}% B1:{pct}% B2:{pct}% C1:{pct}% — {high} B2+ words
[| unmatched (possible C2+/specialist): {words}]
[| B2+ refs: {word /ipa/; ...}]

lexical diversity MTLD={score} ({level})   OR   lexical diversity: insufficient data (<50 words) …

idiomatic density: {per_100}/100 words ({level}); matched: 'phrase' | 'phrase' | …

collocation pairs (spaCy): verb→obj: [v→n, …]; adj→noun: [adj→n, …]
```

Signal coverage:

| Section | Signals covered |
|---|---|
| Response length | Signal 1 (length proxy for "at length" vs "basic meaning") |
| CEFR distribution | Signal 1 (range), Signal 2 (sophistication via B2+) |
| Lexical diversity | Signal 7 (flexibility/repetition) |
| Idiomatic density | Signal 4 (lower-bound; LLM supplements from transcript) |
| Collocation pairs | Signal 5 (raw inventory; LLM judges naturalness) |
| LLM transcript reading | Signal 3 (precision), Signal 4 (remainder), Signal 6 (paraphrase) |

---

## Known limitations and future improvements

| Area | Limitation | Possible improvement |
|---|---|---|
| Signal 4 (idioms) | Fixed phrase list — unlisted idioms not counted | Two-pass: ask LLM to extract idioms first, then compute density |
| Signal 5 (collocation) | spaCy extracts surface pairs only — cannot detect avoided collocations | Bigram frequency against COCA/BNC corpus for objective naturalness score |
| Signal 3 (precision) | LLM-only, no anchor | Inherently uncomputable — acceptable as-is |
| Signal 6 (paraphrase) | LLM-only, no anchor | Inherently uncomputable — acceptable as-is |
