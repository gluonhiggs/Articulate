# Articulate — TODOS

## Backend

### Warn on orphaned Part 3 questions at startup

**What:** After `_seed_questions()` completes, query for Part 3 questions with `parent_id IS NULL`
and log a `logger.warning()` for each one, including the question text. This makes silent
bad-data errors visible.

**Why:** If a seed question's `parent_text` doesn't match any Part 2 question (typo, ordering
issue, or the parent wasn't seeded yet), the Part 3 question is inserted with `parent_id = NULL`.
It then disappears from the Part 3 grouped UI with no error message anywhere.

**Pros:** Catches data integrity issues immediately at startup. Very small change (~5 lines).

**Cons:** Adds one extra DB query at startup (fast, in-memory is fine).

**Context:** Identified during eng review (2026-03-18). The seeding logic already handles this
gracefully — this TODO is just about making the silent failure visible. Start in
`backend/database.py` in `_seed_questions()`, after the `await session.commit()` call.

**Depends on / blocked by:** Nothing.

---

## Deferred from Plan (2026-03-18)

- Per-criterion sparklines on the dashboard — score tags per attempt are sufficient for now
- wav2vec2 phoneme alignment (Tier 2 pronunciation) — PC-only, separate project
- ML-based test forecast — needs question embeddings + topic clustering
- Test coverage for Whisper/Ollama integration paths — requires live models, not suitable for CI

---

## Prompt Version Tracking (deferred 2026-03-18)

**What:** Store a `prompt_version` field on each `Attempt` row so that score comparisons only
compare attempts scored with the same prompt revision.

**Why:** When prompts change (e.g., BAND-SCORES.md upgrade, new error examples), scores shift.
Without versioning, historic attempts appear to have improved or regressed when the prompt changed.

**How:** Add a `prompt_version` column to `attempts` (e.g. `"v2"` string), populate it in
`score_attempt()` from a constant in `scoring.py`. UI: show a warning badge when comparing
attempts across prompt versions.

**Blocked by:** Small enough user base that drift isn't observable yet. Revisit when &gt;100 attempts
are in the DB.
