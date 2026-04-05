# Grammar Context: Concrete Before/After Examples

**Date:** 2026-04-04  
**Purpose:** Show exactly what the LLM receives today versus after two proposed improvements:
1. Richer LanguageTool (LT) output format (error rate, rule grouping, sentence attribution)
2. A spaCy structural-grammar pass (sentence complexity, clause types, tense inventory)

---

## Sample Transcript

```
I go to school every day but yesterday I goed there by bus.
My friend and me was very tired because we have walk a long way.
The teacher which teach us is very kind.
```

This is three sentences, 41 words, 4 distinct grammar errors.

---

## Part 1 - LanguageTool Output: Current vs. Proposed

### Step 1 - What LT fires on this transcript

LT analyses each match and returns a list of `Match` objects. Simulating the four errors:

| # | Matched span | Offset | Error length | rule_id | Replacement(s) | Message |
|---|---|---|---|---|---|---|
| 1 | `goed` | 41 | 4 | `EN_IRREGULAR_VERB_PAST_TENSE` | `["went"]` | Did you mean 'went'? |
| 2 | `me was` | 64 | 6 | `SUBJECT_VERB_AGREEMENT` | `["I was"]` | Use 'I was' as the subject. |
| 3 | `have walk` | 100 | 9 | `MISSING_VERB_FORM` | `["have walked"]` | Use the past participle 'walked'. |
| 4 | `which teach` | 125 | 11 | `GRAMMAR` | `["who teaches"]` | Use a relative pronoun for people. |

All four pass the `filtered_matches` step (none are whitelisted, all are grammar-category rules).

---

### Step 2 - Current `grammar_context` (exactly what the code produces today)

The code at `backend/api/attempts.py` lines 247–256 is:

```python
grammar_errors = [
    f"{m.rule_id}: '{transcript[m.offset:m.offset + m.error_length]}'"
    f" → {list(m.replacements[:2])}"
    for m in filtered_matches[:8]
]
grammar_context = (
    "; ".join(grammar_errors)
    if grammar_errors
    else "no grammar errors detected"
)
```

Applied to the four matches above, `grammar_context` becomes the following **single flat string**:

```
EN_IRREGULAR_VERB_PAST_TENSE: 'goed' → ['went']; SUBJECT_VERB_AGREEMENT: 'me was' → ['I was']; MISSING_VERB_FORM: 'have walk' → ['have walked']; GRAMMAR: 'which teach' → ['who teaches']
```

That is the entire value interpolated into `{grammar_context}` in the prompt template at line 14 of `score_part1.txt`.

**What the LLM does not know from this string:**
- How many sentences the transcript has (it cannot compute an error rate).
- Whether the errors cluster in one sentence or are spread across the response.
- Whether the same rule fires multiple times (repeated pattern vs. one-off slip).
- Any structural information about sentence complexity.

---

### Step 3 - Proposed LT output format

The proposed format adds three layers on top of the existing match list: a header with aggregate counts, a rule-frequency grouping, and per-error sentence attribution.

```
GRAMMAR ERRORS: 4 errors in 3 sentences (error rate: 1.33 per sentence)

By rule:
  EN_IRREGULAR_VERB_PAST_TENSE (1 hit): 'goed' → ['went']
  SUBJECT_VERB_AGREEMENT (1 hit): 'me was' → ['I was']
  MISSING_VERB_FORM (1 hit): 'have walk' → ['have walked']
  GRAMMAR (1 hit): 'which teach' → ['who teaches']

By sentence:
  S1: EN_IRREGULAR_VERB_PAST_TENSE: 'goed' → ['went']
  S2: SUBJECT_VERB_AGREEMENT: 'me was' → ['I was'] | MISSING_VERB_FORM: 'have walk' → ['have walked']
  S3: GRAMMAR: 'which teach' → ['who teaches']
```

With a denser, more systematic transcript, the rule-frequency block becomes load-bearing. For example:

```
GRAMMAR ERRORS: 6 errors in 4 sentences (error rate: 1.50 per sentence)

By rule:
  SUBJECT_VERB_AGREEMENT (3 hits): 'she go' → ['she goes'] | 'they was' → ['they were'] | 'he don't' → ['he doesn't']
  EN_IRREGULAR_VERB_PAST_TENSE (2 hits): 'goed' → ['went'] | 'buyed' → ['bought']
  MISSING_VERB_FORM (1 hit): 'have walk' → ['have walked']
```

The scorer can now distinguish "this learner has a systematic SVA deficit (3/6 errors)" from "scattered one-off mistakes", which maps directly to IELTS GRA band descriptors that use the word "systematic".

---

## Part 2 - spaCy Pass: What It Is and What It Adds

### What "spaCy pass" means

After LT runs, the same transcript string is fed to a loaded `spacy.Language` model (e.g. `en_core_web_sm`). The call is:

```python
doc = nlp(transcript)
```

This runs spaCy's full pipeline: tokenizer, POS tagger, morphological analyser, dependency parser, and sentence boundary detector. The result is a `Doc` object where every token has `.pos_`, `.tag_`, `.dep_`, `.head`, `.morph`, and every sentence span is available via `doc.sents`. No network call, no LLM - pure rule-based/statistical NLP running locally in a few milliseconds.

---

### What spaCy extracts from the sample transcript

#### Sentence segmentation

spaCy's dependency-based sentence splitter identifies three sentences:

| ID | Text |
|----|------|
| S1 | `I go to school every day but yesterday I goed there by bus.` |
| S2 | `My friend and me was very tired because we have walk a long way.` |
| S3 | `The teacher which teach us is very kind.` |

Sentence count: **3**. This is the denominator used in the error-rate calculation above.

---

#### Sentence complexity - subordinate clause detection

spaCy's dependency labels identify the internal structure of each sentence. The relevant labels are:

- `advcl` - adverbial clause modifier (`because`, `when`, `if`, …)
- `relcl` - relative clause modifier (`who`, `which`, `that` modifying a noun)
- `ccomp` - clausal complement (object clause after a verb of saying/thinking)
- `xcomp` - open clausal complement (non-finite complement)
- `acl`   - adjectival clause (participial modifier on a noun)

Applied to the sample:

| Sentence | Subordinate clause token | Dep label | Clause type | Notes |
|----------|--------------------------|-----------|-------------|-------|
| S1 | `go` (main clause) | root | - | coordinated clauses (`but`), no subordination |
| S2 | `walk` | `advcl` | adverbial (`because`) | `because we have walk a long way` |
| S3 | `teach` | `relcl` | relative | `which teach us` modifying `teacher` |

Sentences S2 and S3 are **complex** (they contain at least one subordinate clause). S1 is a compound sentence (coordinate conjunction `but`) - compound is structurally simpler than complex.

**Summary:** 2 of 3 sentences are complex (67%).

---

#### Tense/aspect inventory from verb tokens

spaCy's morphological analyser tags each finite verb with tense and aspect features:

| Token | POS | Tag | Tense | Aspect | Notes |
|-------|-----|-----|-------|--------|-------|
| `go` | VERB | VBZ → VBP | Present | Simple | Correct for habitual present |
| `goed` | VERB | VBD | Past | Simple | Non-standard; should be `went` |
| `was` | AUX | VBD | Past | Simple | Agreement error (`me was`) |
| `have` | AUX | VBP | Present | - | Auxiliary in `have walk` |
| `walk` | VERB | VB | - | - | Missing past participle morphology |
| `teach` | VERB | VBP | Present | Simple | Agreement error; should be `teaches` |
| `is` | AUX | VBZ | Present | Simple | Correct |

Tense forms in use: **present simple, past simple, present perfect (attempted but malformed)**.

---

### What the spaCy fields add to `grammar_context`

The proposed additional block appended after the LT section:

```
STRUCTURAL ANALYSIS (spaCy):
  Sentences: 3 | Complex sentences: 2/3 (67%)
  Subordinate clause types used: advcl (because-clause), relcl (relative clause)
  Tense/aspect inventory: present simple, past simple, present perfect (attempted)
  Tense errors detected: past simple irregular ('goed'), present perfect aspect malformed ('have walk')
```

This block costs the LLM roughly 4 lines of context but gives it the structural evidence it needs to award or withhold the GRA band-6 descriptor: "uses a mix of simple and complex structures".

---

## Part 3 - Full `grammar_context` Value: Before and After

### BEFORE (current - single flat string)

This is the exact value substituted into `{grammar_context}` in `score_part1.txt` line 14:

```
EN_IRREGULAR_VERB_PAST_TENSE: 'goed' → ['went']; SUBJECT_VERB_AGREEMENT: 'me was' → ['I was']; MISSING_VERB_FORM: 'have walk' → ['have walked']; GRAMMAR: 'which teach' → ['who teaches']
```

The LLM prompt line 14 becomes:

```
GRAMMAR SIGNALS: EN_IRREGULAR_VERB_PAST_TENSE: 'goed' → ['went']; SUBJECT_VERB_AGREEMENT: 'me was' → ['I was']; MISSING_VERB_FORM: 'have walk' → ['have walked']; GRAMMAR: 'which teach' → ['who teaches']
```

**What the LLM must infer by itself:**
- Sentence count and error rate (it has to re-read the transcript and count).
- Whether errors are clustered or spread (it has to re-parse the transcript).
- Whether the learner uses complex sentences at all (it has to re-parse for clause structure).
- What tenses are in use (it has to re-read the transcript).

The LLM is doing linguistic analysis that the pipeline should be doing for it.

---

### AFTER (LT refactor + spaCy pass)

The value substituted into `{grammar_context}` becomes:

```
GRAMMAR ERRORS: 4 errors in 3 sentences (error rate: 1.33 per sentence)

By rule:
  EN_IRREGULAR_VERB_PAST_TENSE (1 hit): 'goed' → ['went']
  SUBJECT_VERB_AGREEMENT (1 hit): 'me was' → ['I was']
  MISSING_VERB_FORM (1 hit): 'have walk' → ['have walked']
  GRAMMAR (1 hit): 'which teach' → ['who teaches']

By sentence:
  S1: EN_IRREGULAR_VERB_PAST_TENSE: 'goed' → ['went']
  S2: SUBJECT_VERB_AGREEMENT: 'me was' → ['I was'] | MISSING_VERB_FORM: 'have walk' → ['have walked']
  S3: GRAMMAR: 'which teach' → ['who teaches']

STRUCTURAL ANALYSIS (spaCy):
  Sentences: 3 | Complex sentences: 2/3 (67%)
  Subordinate clause types used: advcl (because-clause), relcl (relative clause)
  Tense/aspect inventory: present simple, past simple, present perfect (attempted)
  Tense errors detected: past simple irregular ('goed'), present perfect aspect malformed ('have walk')
```

The prompt line 14 becomes:

```
GRAMMAR SIGNALS: GRAMMAR ERRORS: 4 errors in 3 sentences (error rate: 1.33 per sentence)

By rule:
  EN_IRREGULAR_VERB_PAST_TENSE (1 hit): 'goed' → ['went']
  SUBJECT_VERB_AGREEMENT (1 hit): 'me was' → ['I was']
  MISSING_VERB_FORM (1 hit): 'have walk' → ['have walked']
  GRAMMAR (1 hit): 'which teach' → ['who teaches']

By sentence:
  S1: EN_IRREGULAR_VERB_PAST_TENSE: 'goed' → ['went']
  S2: SUBJECT_VERB_AGREEMENT: 'me was' → ['I was'] | MISSING_VERB_FORM: 'have walk' → ['have walked']
  S3: GRAMMAR: 'which teach' → ['who teaches']

STRUCTURAL ANALYSIS (spaCy):
  Sentences: 3 | Complex sentences: 2/3 (67%)
  Subordinate clause types used: advcl (because-clause), relcl (relative clause)
  Tense/aspect inventory: present simple, past simple, present perfect (attempted)
  Tense errors detected: past simple irregular ('goed'), present perfect aspect malformed ('have walk')
```

---

### Side-by-side comparison of LLM knowledge

| Question the LLM needs to answer | BEFORE | AFTER |
|---|---|---|
| How many grammar errors are there? | Count them from the flat string | Stated: 4 |
| What is the per-sentence error rate? | Cannot compute (no sentence count) | Stated: 1.33/sentence |
| Are any error types repeated (systematic)? | Must scan rule_ids manually | Stated in "By rule" block with counts |
| Which sentence has the most errors? | Must cross-reference error spans with transcript | Stated: S2 (2 errors) |
| Does the learner use complex sentences? | Must re-parse the transcript | Stated: 2/3 sentences complex |
| What clause types are attempted? | Must re-parse the transcript | Stated: advcl, relcl |
| What tenses are in use? | Must re-read the transcript | Stated: present simple, past simple, present perfect |
| Are tense errors local or tense-wide? | Cannot determine | Stated: irregular past + malformed perfect |

The "after" context makes 8 pieces of evidence that the LLM previously had to reconstruct (potentially incorrectly, especially on longer transcripts) into explicit, pre-computed signals. This is particularly important for longer Part 2/3 responses where the LLM may not accurately track clause structure across 150+ word transcripts entirely on its own.
