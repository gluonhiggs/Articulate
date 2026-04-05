# Grammatical Range and Accuracy - Signals Reference

This file maps every distinct signal needed to score the **Grammatical Range and Accuracy** criterion
to its evidence in `BAND-SCORES.md`.

At the UI level this criterion is labelled "Grammar". Underneath, the rubric assesses
seven distinct properties. Three are fully or partially computable; four can only be assessed
by the LLM reading the transcript.

---

## How scoring works (overview)

```
Audio → Whisper → transcript
                      │
              LanguageTool (LT)
                      │
          ┌───────────┴───────────┐
          │  surface error list   │   + raw transcript
          │  in grammar_context   │   + BAND-SCORES.md
          └───────────┬───────────┘
                      ▼
                     LLM
                      │
                      ▼
            grammar score (0–9, 0.5 steps)
```

LT provides a lower-bound surface-error count, most valuable at bands 3–5. For bands 6–9
the rubric shifts toward structural range, flexibility, and error systematicity - properties
LT cannot measure. The LLM reads the transcript directly for all signals beyond surface errors.

---

## The 7 signals

### Signal 1 - Error Rate and Error-Free Sentence Proportion

**What it is:** How frequently do errors occur, and what share of sentences are fully clean?
This is the single most diagnostic quantity across the full band range.

**Band evidence from BAND-SCORES.md:**

| Band | Exact wording |
|------|---------------|
| 9 | "Structures are precise and accurate at all times, apart from 'mistakes' characteristic of native speaker speech." |
| 8 | "The majority of sentences are error free. Occasional inappropriacies and non-systematic errors occur. A few basic errors may persist." |
| 7 | "Error-free sentences are frequent. … Both simple and complex sentences are used effectively despite some errors." |
| 6 | "Though errors frequently occur in complex structures, these rarely impede communication." |
| 5 | "Basic sentence forms are fairly well controlled for accuracy. Complex structures … nearly always contain errors." |
| 4 | "Some short utterances are error-free. … errors are frequent." |
| 3 | "Makes numerous errors except in memorised expressions." |

**Measurability:** Partially computable.
- LT detects surface errors (subject-verb agreement, verb morphology, confused word pairs,
  wrong determiners, some preposition errors, spelling). These dominate at bands 3–5 and
  their density is itself the scoring signal.
- Per-sentence error presence can be derived from LT match offsets: map each match to its
  sentence, report `clean_sentence_rate = n_sentences_with_no_match / n_sentences`. This
  directly anchors the band-7 ("frequent") vs. band-8 ("majority") distinction.
- **What LT misses:** Errors inside complex clauses (wrong tense on an embedded verb, wrong
  relative pronoun), errors of omission (dropped articles, missing auxiliaries), word order
  errors in embedded questions ("I don't know where is it"), and errors that are surface-valid
  but contextually wrong. At bands 6–9 these missed types are exactly where the rubric focuses.

**Status:** ✅ Fully implemented.
- `_sentence_spans()` splits the transcript into sentences by terminal punctuation.
- `grammar_context` reports total error count, sentence count, and `clean_pct` in the header.
- "By rule" groups all errors by `rule_id` with ×N occurrence counts (systematicity signal).
- "By sentence" attributes every error to its sentence with the LT human-readable message.
- All stats are computed from the full `filtered_matches` list - no cap on detail sections.
- The scoring prompt grammar criterion now anchors `clean_pct` to band thresholds:
  Band 8 ≈ ≥70% error-free; Band 7 ≈ 50–69%; Band 6 = errors frequent in complex structures.

---

### Signal 2 - Structural Range and Flexibility

**What it is:** Does the speaker deploy a variety of grammatical constructions - relative
clauses, passives, conditionals, complement clauses, reported speech - or do they cycle
through the same Subject-Verb-Object template?

**Band evidence from BAND-SCORES.md:**

| Band | Exact wording |
|------|---------------|
| 9 | "Structures are precise and accurate at all times" (implies full mastery of the construction inventory) |
| 8 | "Wide range of structures, flexibly used." |
| 7 | "A range of structures flexibly used." |
| 6 | "A variety of structures with limited flexibility." |
| 5 | "Complex structures are attempted but these are limited in range." |
| 4 | "Structures are repetitive." |

**Measurability:** ❌ LLM-only.
Range requires identifying which construction types are used (relative clause, passive,
adverbial clause, nominalization, conditional, etc.) and whether the speaker can move between
them. Flexibility requires cross-sentence comparison to detect when the same template is
reused. No surface metric reliably operationalises either. The LLM must read the transcript
and judge whether the speaker is stuck in simple frames or is actively varying structure.

**Status:** ✅ Best achievable - not computable. Fully implemented as rubric-anchored prompt guidance with explicit enumeration.
The scoring prompt grammar criterion instructs the LLM to scan the transcript and list observed
construction types (relative clauses, passives, conditionals, complement clauses, nominalisations)
in a `grammar_notes` field placed *before* the `grammar` score in the JSON output. Because the
model generates tokens left-to-right, writing the structural inventory first forces the grammar
score to be self-consistent with the noted evidence - preventing impressionistic band assignment.
The rubric ladder uses exact IELTS wording:
Band 4 = "structures are repetitive", "subordinate clauses are rare";
Band 5 = "complex structures are attempted but these are limited in range";
Band 6 = "a variety of structures with limited flexibility";
Band 7 = "a range of structures flexibly used";
Band 8 = "wide range of structures, flexibly used".
All quoted phrases are verbatim from BAND-SCORES.md - no invented thresholds.
Band 9 has no range descriptor in the rubric and is intentionally excluded from the ladder.

---

### Signal 3 - Complex Sentence Usage and Error Locus

**What it is:** Does the speaker attempt and use complex sentences (those containing
subordinate clauses), and do errors concentrate in those complex structures rather than in
simple ones?

**Band evidence from BAND-SCORES.md:**

| Band | Exact wording |
|------|---------------|
| 8–9 | (complex sentences fully controlled - errors not attributed to complex structures) |
| 7 | "Both simple and complex sentences are used effectively despite some errors." |
| 6 | "Produces a mix of short and complex sentence forms … errors frequently occur in complex structures." |
| 5 | "Complex structures are attempted but … nearly always contain errors and may lead to the need for reformulation." |
| 4 | "Can produce basic sentence forms … subordinate clauses are rare." |

**Measurability:** Partially computable.
- spaCy dependency parsing labels a sentence as complex when it contains any of: `advcl`,
  `relcl`, `ccomp`, `xcomp`, `csubj`, `acl` arcs. `complex_sentence_rate` and subordinate
  clause type counts (`advcl ×N, relcl ×N, …`) are directly computable.
- Error locus (band 5/6/7 pattern: errors in complex but not simple sentences) requires
  combining LT match offsets with the spaCy complexity label per sentence. This is computable
  but not yet implemented.
- **What we cannot compute:** Whether complex sentences are used *effectively* (band 7 wording)
  - a structurally present subordinate clause can be grammatically broken. The LLM must judge
  quality beyond mere presence.

**Status:** ✅ Implemented. `compute_grammar_signals()` in `backend/services/vocab.py` runs
a per-sentence spaCy dependency parse (reusing the existing `_get_spacy()` singleton) and
classifies each sentence as complex when it contains any of `advcl`, `ccomp`, `relcl`,
`acl` (adjectival/participial clause), or `mark` (SCONJ-guarded) arcs. It then maps each LT match offset to its sentence and computes
an **error density ratio** - errors-per-complex-sentence divided by errors-per-simple-sentence
- which avoids the base-rate problem of the naïve error proportion. The two-dimensional
`(complex_sentence_rate, error_density_ratio)` pair is mapped to a `band_hint` (B4–B7) and
appended to `grammar_context` as a `complexity:` line. The scoring prompt grammar criterion
now instructs the LLM to treat this band_hint as a directional anchor for structural range,
with an explicit override instruction when the transcript contradicts it (e.g. the parser
missed a conditional or passive visible in the text). `xcomp` is intentionally excluded from
the arc set - infinitive complements ("I want to go") are not IELTS complex sentences.

---

### Signal 4 - Error Systematicity

**What it is:** Are the speaker's errors isolated slips or a repeated pattern? A single SVA
error is a slip; SVA errors firing on every third sentence indicate a fossilised gap.

**Band evidence from BAND-SCORES.md:**

| Band | Exact wording |
|------|---------------|
| 9 | "'Mistakes' characteristic of native speaker speech" (performance slips, not systematic) |
| 8 | "Non-systematic errors occur." |
| 7 | "A few basic errors persist." (persistent = systematic, but not the dominant feature) |
| 4–6 | (systematic errors implied - same rule fires repeatedly) |

**Measurability:** Partially computable.
- LT output includes a `rule_id` field on each match. Grouping matches by `rule_id` and
  reporting counts directly operationalises systematicity: `SVA: 3 occurrences` is a concrete
  signal that this error is fossilised.
- **What LT misses:** Structural systematic errors (e.g. invariable omission of relative
  pronoun, consistent wrong tense in embedded clauses) are invisible to LT, so systematicity
  can only be established for the surface-error classes LT catches.

**Status:** ✅ Implemented. `grammar_context` groups all LT matches by `rule_id` with ×N
occurrence counts in a "By rule:" section. A repeated `rule_id` (e.g. `SUBJECT_VERB_AGREEMENT ×3`)
is a direct signal of a fossilised gap. The scoring prompt instructs the LLM to use these
counts to judge whether errors are systematic.

---

### Signal 5 - Structural Range Markers (tense inventory, passive, conditionals, tree depth)

**What it is:** Concrete measurable proxies for the breadth of the speaker's structural
inventory: how many distinct tense/aspect forms appear, whether passive constructions are
used, whether conditional clauses appear, and how deep the parse trees run.

**Band evidence from BAND-SCORES.md:**

| Band | Exact wording |
|------|---------------|
| 8–9 | "Wide range of structures, flexibly used." / "Structures are precise and accurate at all times." |
| 7 | "A range of structures flexibly used." |
| 6 | "A variety of structures with limited flexibility." |
| 5 | "Limited in range." |
| 4 | "Structures are repetitive." |

Note: Tense variety, passive, and conditionals are not cited verbatim in the rubric but are
canonical sub-components of "range of structures" at bands 6–9.

**Measurability:** ✅ Computable (with spaCy).
- **Tense inventory:** spaCy morphological analysis extracts `{Tense, Aspect, Mood}` feature
  combinations across all verb tokens. Simple present + simple past only → bands 4–5.
  Present perfect, modals, conditionals, past progressive → bands 6–7. Full tense system
  including future-in-the-past and subjunctive-like conditionals → bands 8–9.
- **Passive voice:** Count sentences containing `aux:pass` arc. Presence is a positive signal;
  absence is neutral (short Part 1 responses rarely use passive).
- **Conditional constructions:** Heuristic: `mark` arc with text "if"/"unless" heading an
  `advcl`, combined with a modal in the governing clause. Second-conditional pattern:
  past-tense `if`-clause + `would/could` main clause.
- **Parse tree depth:** Mean and 90th-percentile max token depth from root. Mean < 3 → simple
  sentences dominant. Mean 4–5 → bands 6–7. Mean > 5 → genuine syntactic complexity.
  Should be read alongside clause counts, not in isolation.

**Status:** ✅ Implemented. All four sub-signals are computed in `compute_grammar_signals()`
in `backend/services/vocab.py`, in the same per-sentence spaCy parse loop as Signal 3
(single pass, no double-parsing). Key implementation notes:
- **Tense inventory:** verb group tag-sequence classification (VBD/VBZ/VBN/VBG/MD combos);
  `parataxis` verbs (I think, I mean) excluded to avoid inflating simple_present; `'d`
  contraction emits `past_perfect_possible` since it is ambiguous between "had" and "would".
- **Passive:** `dep_=="auxpass"` with VBG guard - prevents "she's been working"
  (present perfect progressive) from being falsely classified as passive by `en_core_web_sm`.
- **Conditionals:** `if/unless/provided` marker + `advcl` guard (excludes complementizer
  "I wonder if…") + main-clause modal → classified as zero/first/second/third conditional.
- **Tree depth:** mean and p90 token hops to root; punctuation and `parataxis` subtrees
  excluded; run-on caveat surfaced in prompt (high depth + low complex rate = coordination,
  not subordination).
Output appended to `grammar_context` as a `structural_range:` multi-line block. All three
scoring prompts instruct the LLM to use tense count as a direct band anchor, passive and
conditional presence as positive signals, and tree depth as directional (with run-on guard).

---

### Signal 6 - Communication Impact and Native-Speaker Performance Errors

**What it is:** Two related judgement calls: (a) do the errors actually obscure meaning for
the listener? (b) at band 9, are the remaining "errors" real gaps or real-time performance
slips of the kind native speakers also make?

**Band evidence from BAND-SCORES.md:**

| Band | Exact wording |
|------|---------------|
| 9 | "Apart from 'mistakes' characteristic of native speaker speech." |
| 8 | "Occasional inappropriacies and non-systematic errors occur." (do not impede communication) |
| 6 | "Though errors frequently occur in complex structures, these rarely impede communication." |

**Measurability:** ❌ LLM-only.
Intelligibility is a property of error × context × listener, not of error type alone.
Distinguishing a performance slip (anacolutha, false start, recovered agreement failure) from
a fossilised learner error requires pragmatic and contextual knowledge. LT will flag
performance slips as real errors and cannot distinguish them. No surface metric can model
communicative impact.

**Status:** ❌ Not computable. LLM infers from transcript. No supporting signal currently
in `grammar_context`. A partial improvement: the existing disfluency timestamps could flag
spans where self-corrections occur near LT-flagged positions, giving the LLM a weak indicator
of performance-slip context - but this is not yet implemented.

---

### Signal 7 - Turn Length and Reformulation

**What it is:** How long are the speaker's turns, and do failed complex-structure attempts
trigger abandonment and restart? Short turns at band 4 limit the grammatical evidence
available; reformulation at band 5 is a direct consequence of complex-structure overreach.

**Band evidence from BAND-SCORES.md:**

| Band | Exact wording |
|------|---------------|
| 5 | "Complex structures … may lead to the need for reformulation." |
| 4 | "Overall, turns are short." |

**Measurability:** Partially computable.
- **Turn length:** `total_words` and sentence count are already available in the pipeline.
  Average words per sentence is directly computable. These are currently used only for
  fluency context and are not passed explicitly as a GRA signal.
- **Reformulation rate:** Word-level repetitions or filler words occurring within N tokens of
  an LT-flagged span are a noisy proxy for grammatically-triggered restarts. The existing
  disfluency detector captures long-pause events; pauses immediately before LT error spans
  could signal anticipatory difficulty. The two signals (disfluency timestamps + LT offsets)
  are computed independently and never correlated.

**Status:** ✅ Turn length implemented. `grammar_context` now includes a `turn_length:` line
with total word count, sentence count, and average words per sentence - directly anchoring
the band 4 "overall, turns are short" criterion. Reformulation correlation (disfluency
timestamps × LT offsets) remains unimplemented - noisy proxy, low accuracy gain, skipped.

---

## Summary table

| # | Signal | Bands it distinguishes | Computable? | Status |
|---|--------|------------------------|-------------|--------|
| 1 | Error Rate and Error-Free Sentence Proportion | B3 ↔ B4 ↔ B5 ↔ B6 ↔ B7 ↔ B8 ↔ B9 | Partially | ✅ Sentence count, clean_pct, by-rule ×N counts, by-sentence attribution - all errors included; prompt anchors clean_pct to band thresholds |
| 2 | Structural Range and Flexibility | B4 ↔ B5 ↔ B6 ↔ B7 ↔ B8 | No | ✅ Best achievable - rubric ladder of exact IELTS quotes + explicit enumeration instruction; `grammar_notes` field placed before `grammar` score forces self-consistent structural range scoring |
| 3 | Complex Sentence Usage and Error Locus | **B4 ↔ B5** ↔ B6 ↔ B7 | Partially | ✅ `compute_grammar_signals()` computes complex_sentence_rate + error_density_ratio via spaCy dep parse; band_hint appended to grammar_context; prompt anchors LLM to use it as directional signal |
| 4 | Error Systematicity | B7 ↔ **B8** ↔ B9 | Partially | ✅ rule_id ×N grouping in "By rule:" section of grammar_context; prompt instructs LLM to use counts for systematicity |
| 5 | Structural Range Markers (tense, passive, conditionals, tree depth) | B5 ↔ B6 ↔ B7 ↔ B8 ↔ B9 | Yes (with spaCy) | ✅ All four sub-signals in `compute_grammar_signals()` single pass; `structural_range:` block appended to grammar_context |
| 6 | Communication Impact and Native-Speaker Performance Errors | B6 ↔ B8 ↔ B9 | No | ❌ LLM-only (reads transcript) |
| 7 | Turn Length and Reformulation | **B4** ↔ **B5** | Partially | ✅ `turn_length:` line in grammar_context (word count, sentence count, avg words/sent); reformulation skipped (noisy, low value) |

**Remaining gap:** Signals 2 and 6 are LLM-only and always will be - they require semantic
and pragmatic understanding. Signals 3, 4, 5, and 7 are all computable or partially computable
and represent the highest-value improvements to `grammar_context`. Signal 4 requires only a
refactor of existing LT output; no new dependencies.

---

## What `grammar_context` currently sends to the LLM

Structured multi-line format:

```
4 error(s) in 12 sentences (67% error-free)

By rule:
  [GRAMMAR] SUBJECT_VERB_AGREEMENT ×2: 'he go' → ['he goes'] | 'they was' → ['they were']
  [GRAMMAR] MISSING_VERB_FORM ×1: 'have walk' → ['have walked']
  [GRAMMAR] GRAMMAR ×1: 'which teach' → ['who teaches']

By sentence:
  S2: 'he go' → ['he goes'] (Subject-verb agreement: 'He go' should be 'He goes')
  S4: 'have walk' → ['have walked'] (Use the past participle 'walked')
  S7: 'they was' → ['they were'] (Subject-verb agreement)
  S9: 'which teach' → ['who teaches'] (Use a relative pronoun for people)
```

All errors included (no cap). Stats computed from the full filtered match list.

Signal coverage:

| Section | Signals covered |
|---------|-----------------|
| Header (sentence count, clean_pct) | Signal 1 ✅ - band-7 vs. band-8 distinction directly computable |
| By rule (rule_id ×N counts) | Signal 4 ✅ - systematicity: repeated rule_id = fossilised gap |
| By sentence (per-error attribution) | Signal 1 ✅ - error locus visible per sentence |
| LLM transcript reading | Signal 2 (structural range), Signal 3 (complex sentence quality), Signal 6 (communication impact) |
| complexity: line | Signal 3 ✅ - complex_sentence_rate, error_density_ratio, band_hint |
| structural_range: block | Signal 5 ✅ - tense inventory + band hint, passive count, conditional types, tree depth mean/p90 |
| turn_length: line | Signal 7 ✅ - total words, sentence count, avg words/sentence |

---

## Known limitations and future improvements

| Area | Limitation | Possible improvement |
|------|-----------|----------------------|
| Signal 1 (error rate) | ✅ Resolved - sentence count, clean_pct, by-rule ×N, by-sentence all implemented; prompt anchors clean_pct to band thresholds | - |
| Signal 1 (error rate) | LT misses structural errors in complex clauses, errors of omission, word order in embedded questions | Inherently uncomputable by LT - instruct LLM explicitly to look for these in the transcript |
| Signal 4 (systematicity) | ✅ Resolved - rule_id grouping with ×N counts now in grammar_context | - |
| Signal 3 (complex sentence usage) | ✅ Resolved - `compute_grammar_signals()` combines spaCy dep parse (per-sentence) with LT error offsets to produce complex_sentence_rate and error_density_ratio; band_hint in grammar_context | - |
| Signal 5 (range markers) | ✅ Resolved - all four sub-signals in `compute_grammar_signals()` single pass; `structural_range:` block in grammar_context | - |
| Signal 7 (turn length) | ✅ Resolved - `turn_length:` line added to grammar_context | - |
| Signal 7 (reformulation) | Disfluency timestamps and LT error offsets never correlated - noisy proxy, skipped intentionally | Not planned - low accuracy gain for medium engineering effort |
| Signal 2 (structural range) | ✅ Resolved - explicit enumeration instruction added to prompt; `grammar_notes` field before `grammar` score forces observation-before-conclusion ordering | - |
| Signal 6 (communication impact) | LLM-only, no anchor | Inherently uncomputable - acceptable as-is |
