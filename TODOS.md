# Articulate - TODOS


## Deferred from Plan (2026-03-18)

- Per-criterion sparklines on the dashboard - score tags per attempt are sufficient for now
- wav2vec2 phoneme alignment (Tier 2 pronunciation) - PC-only, separate project
- ML-based test forecast - needs question embeddings + topic clustering
- Test coverage for Groq/LLM API integration paths - requires live API keys, not suitable for CI

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
