# Lexical Resource — Signals Reference

This file maps every distinct signal needed to score the **Lexical Resource** criterion
to its evidence in `BAND-SCORES.original.md`.

At the UI level this criterion is labelled "Vocabulary". Underneath, the rubric assesses
seven distinct properties. Three are computable; two are partially computable (not yet
implemented); two can only be assessed by the LLM reading the transcript.

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

**Status:** ✅ Partially implemented — CEFR distribution + B2+ count in `vocab_signal`.
❌ Word count (response length) not yet included in signal.

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

**Measurability:** Partially computable (not yet implemented).
- Formulaic sequence density: compare the speaker's n-grams (bigrams/trigrams) against a
  native-speaker corpus. High overlap = uses natural idiomatic chunks.
- A simpler proxy: a curated list of IELTS-relevant collocational phrases can be matched
  against the transcript.

**Status:** ❌ Not implemented. LLM must infer from transcript.

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

**Measurability:** Partially computable (not yet implemented).
- Bigram/trigram frequency against a native corpus (COCA or BNC) can score how natural
  a word pair is. Low-frequency pairs in native corpora = likely collocation error.
- This is the highest-value missing signal for Band 6 vs Band 7 discrimination.

**Status:** ❌ Not implemented. LLM must infer from reading transcript.

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
| 1 | Vocabulary Range | B2 ↔ B3 ↔ B4 ↔ B5 ↔ B6 ↔ B7 ↔ B9 | Partially | ✅ CEFR distribution — ❌ word count missing |
| 2 | Vocabulary Sophistication (less common words) | B6 ↔ B7 ↔ B8 ↔ B9 | Yes | ✅ B2+ count + unmatched words |
| 3 | Precision / Accuracy in word choice | B4 ↔ B6 ↔ B7 ↔ B8 ↔ B9 | No | LLM-only |
| 4 | Idiomatic Language | B7 ↔ B8 ↔ B9 | Partially | ❌ Not implemented |
| 5 | Collocation Awareness | **B6 ↔ B7** ↔ B8 | Partially | ❌ Not implemented |
| 6 | Paraphrase Ability | B4 ↔ B5 ↔ B6 ↔ B7 | No | LLM-only |
| 7 | Lexical Diversity / Flexibility | B5 ↔ B6 ↔ B7 ↔ B8 ↔ B9 | Yes | ✅ MTLD + unique lemma ratio |

**Critical gap:** Signal 5 (Collocation) is the boundary between Band 6 and Band 7 but
is not yet computed. The LLM must detect collocation errors from the raw transcript with
no numerical anchor — the most error-prone part of the current scoring pipeline.

---

## What `vocab_signal` currently sends to the LLM

```
CEFR ({matched}/{total} content words matched, {unique} unique lemmas, {ratio}% variety):
A1:{pct}% A2:{pct}% B1:{pct}% B2:{pct}% C1:{pct}% — {high} B2+ words
| unmatched (possible C2+/specialist): {words}
| B2+ pronunciation refs: {word /ipa/; ...}
lexical diversity MTLD={score} ({level}) OR insufficient data (<50 words)
```

Covers: Signal 1 (via CEFR distribution), Signal 2 (via B2+ count), Signal 7 (via
MTLD and unique lemma ratio).

Signals 3, 4, 5, 6 — the LLM infers from the raw transcript and BAND-SCORES.md.

---

## Planned improvements (priority order)

1. **Add response word count** to `vocab_signal` — trivial, fixes Signal 1 gap.
   Explicitly tells LLM when an answer is too short to assess "at length" (Band 6 floor).

2. **Add collocation score** — compute bigram frequency against a reference corpus
   (COCA or pre-built BNC frequency list). Fixes Signal 5 gap — the most critical one
   for Band 6↔7 discrimination.

3. **Add idiomatic/formulaic density** — n-gram overlap against a curated phrase list.
   Fixes Signal 4 gap for Band 7↔8 discrimination.
