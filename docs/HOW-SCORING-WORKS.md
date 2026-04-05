Mock IELTS Part 1 response

  Question: What do you do in your free time?

  Response (band ~6 speaker):
  ▎ "Well, I really enjoy spending time outdoors. I like hiking and sometimes cycling with my friends. I also read books, especially novels about adventure. I think it helps me relax and forget about daily problems. Sometimes I cook new recipes     
  because I find it quite satisfying and creative."

  ---
  Step 1 — Whisper produces word dicts

  Each word comes out as a dict with timing and confidence:

  words = [
    {"word": "Well",        "start": 0.00, "end": 0.24, "probability": 0.97},
    {"word": "I",           "start": 0.24, "end": 0.30, "probability": 0.99},
    {"word": "really",      "start": 0.30, "end": 0.54, "probability": 0.96},
    {"word": "enjoy",       "start": 0.54, "end": 0.82, "probability": 0.98},
    {"word": "spending",    "start": 0.82, "end": 1.10, "probability": 0.97},
    {"word": "time",        "start": 1.10, "end": 1.28, "probability": 0.99},
    {"word": "outdoors",    "start": 1.28, "end": 1.80, "probability": 0.93},
    {"word": "I",           "start": 1.90, "end": 1.95, "probability": 0.99},
    {"word": "like",        "start": 1.95, "end": 2.10, "probability": 0.98},
    {"word": "hiking",      "start": 2.10, "end": 2.50, "probability": 0.91},
    {"word": "and",         "start": 2.50, "end": 2.60, "probability": 0.99},
    {"word": "sometimes",   "start": 2.60, "end": 3.00, "probability": 0.98},
    {"word": "cycling",     "start": 3.00, "end": 3.40, "probability": 0.89},
    {"word": "with",        "start": 3.40, "end": 3.52, "probability": 0.99},
    {"word": "my",          "start": 3.52, "end": 3.60, "probability": 0.99},
    {"word": "friends",     "start": 3.60, "end": 3.95, "probability": 0.98},
    ...
    {"word": "satisfying",  "start": 8.20, "end": 8.80, "probability": 0.87},
    {"word": "and",         "start": 8.80, "end": 8.90, "probability": 0.99},
    {"word": "creative",    "start": 8.90, "end": 9.30, "probability": 0.95},
  ]

  ---
  Step 2 — _run_pipeline() in attempts.py computes 4 signals in parallel

  Signal A: fluency_context

  Scans consecutive word pairs. Gap = words[i].start - words[i-1].end. Any gap ≥ 0.5s is a "long pause" and the word after it is marked disfluent.

  Gap before "I" (second sentence): 1.90 - 1.80 = 0.10s  → OK
  Gap before "sometimes" (last sentence): ~7.00 - 6.85 = 0.15s → OK
  (No gaps ≥ 0.5s in this response)

  → fluency_context = "0 long pause(s) in 46 words (0.0/100 words)"
  → disfluent = set()  (empty)

  Signal B: flagged_words

  Words where probability < low_confidence_threshold (default ~0.85) OR word is disfluent:

  "cycling"  → prob 0.89 → OK (above threshold)
  "satisfying" → prob 0.87 → OK
  All words above threshold in this response.
  Disfluent set is empty.

  → flagged_words = ""  (none)

  Signal C: grammar_context

  LanguageTool runs on the full transcript. For this response it finds nothing major:

  → grammar_context = "no grammar errors detected"

  Signal D: vocab_signal — this is the main one

  compute_vocab_signal(words, transcript) is called. Let's trace it fully.

  ---
  Step 3 — Inside compute_vocab_signal()

  3a. Build content_words — strip punctuation, filter stop words and short tokens

  # Raw word list (lowercased, punctuation stripped):
  raw = ["well", "i", "really", "enjoy", "spending", "time", "outdoors",
         "i", "like", "hiking", "and", "sometimes", "cycling", "with",
         "my", "friends", "i", "also", "read", "books", "especially",
         "novels", "about", "adventure", "i", "think", "it", "helps",
         "me", "relax", "and", "forget", "about", "daily", "problems",
         "sometimes", "i", "cook", "new", "recipes", "because", "i",
         "find", "it", "quite", "satisfying", "and", "creative"]

  # After len > 2 AND not in _STOP_WORDS:
  # ✗ "i"        → len=1 (filtered)
  # ✗ "really"   → in _STOP_WORDS (filtered)
  # ✓ "well"     → keep
  # ✓ "enjoy"    → keep
  # ✓ "spending" → keep
  # ✓ "time"     → keep
  # ✓ "outdoors" → keep
  # ✗ "like"     → in _STOP_WORDS (filtered)
  # ✓ "hiking"   → keep
  # ✗ "and"      → in _STOP_WORDS (filtered)
  # ✓ "sometimes"→ keep
  # ✓ "cycling"  → keep
  # ✗ "with"     → in _STOP_WORDS (filtered)
  # ✗ "my"       → in _STOP_WORDS (filtered)
  # ✓ "friends"  → keep
  # ✗ "also"     → in _STOP_WORDS (filtered)
  # ✓ "read"     → keep
  # ✓ "books"    → keep
  # ✓ "especially"→ keep
  # ✓ "novels"   → keep
  # ✗ "about"    → in _STOP_WORDS (filtered)
  # ✓ "adventure"→ keep
  # ✗ "think"    → in _STOP_WORDS (filtered)
  # ✗ "it"       → in _STOP_WORDS (filtered)
  # ✓ "helps"    → keep
  # ✗ "me"       → in _STOP_WORDS (filtered)
  # ✓ "relax"    → keep
  # ✗ "forget"   → NOT in stop words → keep ✓  (content verb)
  # ✗ "about"    → filtered
  # ✓ "daily"    → keep
  # ✓ "problems" → keep
  # ✓ "cook"     → keep
  # ✓ "new"      → keep
  # ✓ "recipes"  → keep
  # ✗ "because"  → in _STOP_WORDS (filtered)
  # ✓ "find"     → keep (not in stop words)
  # ✓ "quite"    → keep
  # ✓ "satisfying"→ keep
  # ✓ "creative" → keep

  content_words = [
    "well", "enjoy", "spending", "time", "outdoors",
    "hiking", "sometimes", "cycling", "friends",
    "read", "books", "especially", "novels", "adventure",
    "helps", "relax", "forget", "daily", "problems",
    "cook", "new", "recipes", "find", "quite",
    "satisfying", "creative"
  ]
  # total = 26 content words

  3b. Lemmatize each word → look up Oxford 5000

  # word           lemma (simplemma)   Oxford 5000 level
  # ─────────────────────────────────────────────────────
  # "well"       → "well"            →  A1
  # "enjoy"      → "enjoy"           →  A2
  # "spending"   → "spend"           →  A2
  # "time"       → "time"            →  A1
  # "outdoors"   → "outdoors"        →  B2
  # "hiking"     → "hike"            →  ❌ not in Oxford 5000  ← unmatched
  # "sometimes"  → "sometimes"       →  A1
  # "cycling"    → "cycle"           →  B1
  # "friends"    → "friend"          →  A1
  # "read"       → "read"            →  A1
  # "books"      → "book"            →  A1
  # "especially" → "especially"      →  B1
  # "novels"     → "novel"           →  B2
  # "adventure"  → "adventure"       →  B1
  # "helps"      → "help"            →  A1
  # "relax"      → "relax"           →  B1
  # "forget"     → "forget"          →  A2
  # "daily"      → "daily"           →  B1
  # "problems"   → "problem"         →  A2
  # "cook"       → "cook"            →  A2
  # "new"        → "new"             →  A1
  # "recipes"    → "recipe"          →  B1
  # "find"       → "find"            →  A2
  # "quite"      → "quite"           →  A2
  # "satisfying" → "satisfy"         →  B2
  # "creative"   → "creative"        →  B2

  3c. Tally up

  total = 26 content words
  matched = 25  (hiking was unmatched)

  counts:
    A1: well, time, sometimes, friend, read, book, help, new = 8 tokens  → 32%
    A2: enjoy, spend, forget, problem, cook, find, quite     = 7 tokens  → 28%
    B1: cycle, especially, adventure, relax, daily, recipe   = 6 tokens  → 24%
    B2: outdoors, novel, satisfy, creative                   = 4 tokens  → 16%
    C1: (none)                                               = 0         →  0%

  high (B2+) = 4 tokens
  unique lemmas = 25 (hiking has its own lemma "hike" too)
  unique_ratio = 26/26 = 100%
  unmatched = ["hike"]  (only one)

  B2+ words with IPA (capped at 5):
    outdoors  → /ˌaʊtˈdɔːrz/
    novel     → /ˈnɑːvl/
    satisfy   → /ˈsætɪsfaɪ/
    creative  → /kriˈeɪtɪv/

  3d. MTLD check

  Full transcript word count: ~46 words → below the 50-word threshold → MTLD skipped.

  3e. Final vocab_signal string assembled

  "CEFR (25/26 content words matched, 25 unique lemmas, 100% variety):
   A1:32% A2:28% B1:24% B2:16% C1:0% — 4 B2+ words
   | unmatched (possible C2+/specialist): hike
   | B2+ pronunciation refs: outdoors /ˌaʊtˈdɔːrz/; novel /ˈnɑːvl/;
     satisfy /ˈsætɪsfaɪ/; creative /kriˈeɪtɪv/;
   lexical diversity: insufficient data (<50 words)"

  ---
  Step 4 — LLM receives the full prompt

  The prompt template is filled with all 6 variables. The vocabulary-relevant parts look like this:

  [BAND DESCRIPTORS]
  **Band 6**
  Vocab: Wide enough vocabulary to discuss topics at length and make meaning
  clear despite inappropriacies. Generally paraphrases successfully.

  **Band 7**
  Vocab: Uses vocabulary resource flexibly across a variety of topics. Uses
  some less common and idiomatic vocabulary with some awareness of style and
  collocation, though with some inappropriate choices.

  [COMPUTED SIGNALS]
  Vocabulary signal: CEFR (25/26 content words matched, 25 unique lemmas,
  100% variety): A1:32% A2:28% B1:24% B2:16% C1:0% — 4 B2+ words | ...

  [TRANSCRIPT]
  "Well, I really enjoy spending time outdoors. I like hiking and sometimes
  cycling with my friends. I also read books, especially novels about
  adventure. I think it helps me relax and forget about daily problems.
  Sometimes I cook new recipes because I find it quite satisfying and creative."

  [QUESTION]
  "What do you do in your free time?"

  ---
  Step 5 — LLM's reasoning process (implicit)

  The LLM cross-references the signal numbers against the rubric descriptors:

  ┌───────────────────────────────────────────┬─────────────────────────────────────────────────────┬─────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │               What LLM sees               │                  What rubric says                   │                                             Implication                                             │
  ├───────────────────────────────────────────┼─────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 16% B2 words, 0% C1                       │ Band 7: "less common items"                         │ Borderline — a few advanced words but not sustained                                                 │
  ├───────────────────────────────────────────┼─────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 100% unique lemma ratio                   │ —                                                   │ Good variety, no repetition                                                                         │
  ├───────────────────────────────────────────┼─────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ novel, creative, satisfying in transcript │ Band 6→7 boundary                                   │ Three good B2 choices but all common, no real idioms                                                │
  ├───────────────────────────────────────────┼─────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ No collocation signal                     │ Band 7: "collocation awareness"                     │ LLM reads transcript and notices "cook new recipes" (collocation gap — should be "try new recipes") │
  ├───────────────────────────────────────────┼─────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ MTLD: insufficient data                   │ Band 5-6: "limited flexibility" for short responses │ LLM may penalise slightly for brevity                                                               │
  ├───────────────────────────────────────────┼─────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ No flagged_words                          │ —                                                   │ No pronunciation evidence of vocabulary uncertainty                                                 │
  ├───────────────────────────────────────────┼─────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ hike unmatched                            │ Potential C2+ or specialist                         │ LLM sees "hiking" in transcript, validates it's appropriate                                         │
  └───────────────────────────────────────────┴─────────────────────────────────────────────────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────┘

  LLM output:
  {
    "fluency": 6.5,
    "vocabulary": 6.0,
    "grammar": 6.5,
    "pronunciation": 6.0,
    "feedback_text": "Vocabulary is sufficient for this familiar topic with
      some good B2 choices (outdoors, novels, satisfying, creative), but lacks
      idiomatic expressions and collocation precision — 'cook new recipes'
      would be more natural as 'try new recipes'. No C1 vocabulary used.",
    "error_highlights": [
      {"word": "cook", "type": "uncertain",
       "correction": "try", "explanation": "weak collocation: 'try new recipes' is more natural"}
    ]
  }

  Overall score: (6.5 + 6.0 + 6.5 + 6.0) / 4 = 6.25 → rounded to 6.5

  ---
  What the signal currently cannot tell the LLM

  The collocation error (cook new recipes) was caught by the LLM reading the raw transcript — not by any computed signal. That's the gap: the vocab_signal string has no collocation score, so the LLM might miss it on a bad day or with a weaker model.
   Adding a bigram frequency score against COCA/BNC would anchor that judgment — the computed number would say "collocation score: low (2.3/10)" and the LLM wouldn't have to infer it from scratch.