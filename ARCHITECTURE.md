# Articulate — System Architecture Reference

> Auto-generated from codebase exploration. Keep in sync when adding features.

---

## 1. System Overview

Articulate is a full-stack IELTS Speaking practice app. Users record mock responses, which are transcribed by Whisper (local ML), evaluated by an Ollama LLM, and returned with band scores, error highlights, and feedback. The backend is FastAPI + SQLite; the frontend is a React/TypeScript SPA. All AI runs locally — no external API calls except optional LanguageTool grammar checking.

**Swagger UI (interactive API docs):** `http://localhost:8000/docs`
**ReDoc (readable API docs):** `http://localhost:8000/redoc`

---

## 2. Request Lifecycle — Score Attempt

```
Browser                          FastAPI Backend                    External
──────                           ──────────────                     ────────
Record audio (WebM/MP4)
  │
  ├─ POST /api/v1/attempts/submit
  │    FormData: audio + question_id
  │                                ├─ Save audio to data/audio/
  │                                ├─ INSERT Attempt (status=processing)
  │                                ├─ Spawn BackgroundTask
  │  ← 202 { id, status }         └─ return immediately
  │
  ├─ Poll GET /attempts/{id}/status (every 1.5s, 3min timeout)
  │                                │
  │                                ├─ [status: transcribing]
  │                                │   └─ Whisper → transcript + word timestamps
  │                                │
  │                                ├─ [status: scoring]
  │                                │   ├─ Gap rate → fluency_context
  │                                │   ├─ CEFR match → vocab_signal
  │                                │   ├─ LanguageTool → grammar_context (Java, optional)
  │                                │   ├─ Low-confidence words → flagged_words
  │                                │   ├─ Build prompt (template + all signals)
  │                                │   └─ POST Ollama /api/generate ──────────→ LLM
  │                                │       model=get_active_model()             │
  │                                │       temperature=0.3                      │
  │                                │       num_predict=1024                     │
  │                                │       num_ctx=8192                         │
  │                                │   ← JSON { fluency, vocabulary,           ←┘
  │                                │            grammar, pronunciation,
  │                                │            error_highlights, feedback_text }
  │                                │
  │                                ├─ [status: ready]
  │                                │   ├─ Clamp scores to 0–9 (0.5 steps)
  │                                │   ├─ Compute overall = mean(4 criteria)
  │                                │   ├─ UPDATE Attempt (all scores, feedback)
  │                                │   ├─ UPDATE DailyActivity (attempts_count, intensity)
  │                                │   └─ UPDATE UserStats (streak, estimated_band)
  │
  └─ Render scores in UI
```

**Attempt status transitions:**
```
processing → transcribing → scoring → ready
                                    ↘ failed:transcription
                                    ↘ failed:empty_audio
                                    ↘ failed:scoring
                                    ↘ failed (generic)
```

Attempts stuck >10 minutes in a non-ready state are auto-marked `failed` when `/attempts/history` is fetched.

---

## 3. Folder Structure

```
Articulate/
├── backend/
│   ├── main.py                  # FastAPI app, lifespan hooks, CORS, router registration, SPA fallback
│   ├── config.py                # Settings (pydantic-settings), get_active_model(), set_runtime_model()
│   ├── database.py              # Async SQLAlchemy engine, init_db(), session factory, question seeding
│   ├── models.py                # ORM tables: Question, Attempt, DailyActivity, UserStats
│   ├── schemas.py               # Pydantic I/O models: QuestionOut, AttemptOut, SystemInfoOut, SetModelRequest…
│   ├── constants.py             # PROMPTS_DIR, PROJECT_ROOT, BAND_ROLLING_WINDOW, HEATMAP_DAYS
│   │
│   ├── api/
│   │   ├── attempts.py          # /submit, /status, /history, /improve, /pronunciation, /audio
│   │   ├── questions.py         # /part1, /part2, /part3, /{id}, /sample-answer, /topic-vocab, /forecast, /bulk
│   │   ├── dashboard.py         # /dashboard — streaks, estimated_band, heatmap
│   │   ├── system.py            # GET /info, PATCH /model
│   │   └── tts.py               # /pronounce (word TTS), /{question_id} (question TTS)
│   │
│   ├── services/
│   │   ├── transcription.py     # Whisper loader, _sync_transcribe(), warmup_probe(), CUDA fallback
│   │   ├── scoring.py           # score_attempt(): signals → prompt → Ollama → parse → clamp
│   │   ├── ollama_client.py     # Singleton httpx client, generate(), ConnectError retry, latency logging
│   │   ├── audio.py             # save_audio(), cleanup_old_audio() (by age then by total size)
│   │   ├── tts.py               # Kokoro TTS, get_or_generate_tts(), cache eviction
│   │   ├── improve.py           # generate_improvement(): rewrite at target band
│   │   └── ai_assist.py         # generate_sample_answer(), generate_topic_vocab()
│   │
│   ├── prompts/
│   │   ├── score_part1.txt      # Scoring prompt for Part 1 (Q&A)
│   │   ├── score_part2.txt      # Scoring prompt for Part 2 (Cue card)
│   │   ├── score_part3.txt      # Scoring prompt for Part 3 (Discussion)
│   │   ├── improve.txt          # Rewrite prompt (+1 band)
│   │   ├── sample_answer.txt    # Model answer generation
│   │   └── topic_vocab.txt      # Advanced vocabulary extraction
│   │
│   └── data/
│       ├── cefr_wordlist.py     # Dict: word → CEFR level (A1–C2), used for vocab signal
│       └── seed_questions.json  # Initial question bank, loaded by init_db() (additive, no duplicates)
│
├── frontend/
│   └── src/
│       ├── main.tsx             # React root, QueryClient provider
│       ├── App.tsx              # BrowserRouter, Routes, Layout
│       │
│       ├── api/
│       │   └── client.ts        # All API calls (see section 5)
│       │
│       ├── types/
│       │   └── index.ts         # TS interfaces: Question, Attempt, SystemInfo, DashboardData…
│       │
│       ├── hooks/
│       │   ├── useRecorder.ts   # MediaRecorder state, blob collection, permission error handling
│       │   └── usePolling.ts    # Polls /status every 1.5s, 3-min timeout
│       │
│       ├── store/
│       │   └── recordingStore.ts # Zustand: idle|preparing|recording|uploading|polling|done|error
│       │
│       ├── pages/
│       │   ├── Home.tsx                 # /          — Dashboard
│       │   ├── Part1Practice.tsx        # /practice/part1
│       │   ├── Part2Practice.tsx        # /practice/part2
│       │   ├── Part3Practice.tsx        # /practice/part3
│       │   ├── QuestionDetail.tsx       # /practice/part{1,2,3}/questions/:id
│       │   ├── MockTest.tsx             # /mock-test
│       │   ├── Forecast.tsx             # /forecast
│       │   └── PartTabSwitcher.tsx      # Shared tab bar
│       │
│       └── components/
│           ├── ErrorBoundary.tsx
│           ├── layout/
│           │   ├── Layout.tsx           # Sidebar + Outlet wrapper
│           │   └── Sidebar.tsx          # Nav links, system info, inline model editor
│           ├── recording/
│           │   ├── RecordingBar.tsx     # Sticky bottom bar: record/stop/upload/poll/results
│           │   └── CountdownTimer.tsx
│           ├── questions/
│           │   ├── QuestionCard.tsx     # Question preview with latest score
│           │   ├── ActiveAttemptCard.tsx # In-progress attempt (polling display)
│           │   ├── PrevAttemptCard.tsx  # Historical attempt (score, audio, feedback)
│           │   ├── ScoreBadge.tsx       # Overall band badge
│           │   ├── ScoreCircle.tsx      # Circular criterion display
│           │   ├── ScoreTags.tsx        # Fluency/Vocab/Grammar/Pronun tag row (shows X.X)
│           │   ├── ImproveSection.tsx   # "Generate improved version" + result
│           │   ├── InlineCorrectedText.tsx # Highlight error_highlights in transcript
│           │   └── utils.ts
│           ├── ai-panel/
│           │   ├── RightPanel.tsx       # Sample answer + vocabulary tabs
│           │   ├── PronunciationRightPanel.tsx # Per-word confidence
│           │   └── RightPanelPlaceholder.tsx
│           └── dashboard/
│               ├── ActivityHeatmap.tsx  # 6-month heatmap
│               └── StreakCard.tsx
│
├── data/                        # Runtime data (gitignored)
│   ├── articulate.db            # SQLite database
│   ├── audio/                   # Recorded audio files ({attempt_id}.webm/.mp4)
│   └── tts_cache/               # Kokoro-generated WAV files
│
├── certs/                       # Optional TLS certs (cert.pem + key.pem → enables HTTPS)
├── BAND-SCORES.md               # IELTS band descriptors Band 3–9, injected into every scoring prompt
├── BAND-SCORES.original.md      # Full official band descriptors (source of truth)
├── pyproject.toml               # Python deps + uv config
├── run.ps1                      # Windows startup script (env load, CUDA torch check, uvicorn)
├── .env.pc                      # PC profile settings (large-v3, gemma3:12b, CUDA)
└── .env.laptop                  # Laptop profile settings (base, gemma3:1b, CPU)
```

---

## 4. API Routes

### Attempts — `/api/v1/attempts`

| Method | Path | Purpose | Returns |
|--------|------|---------|---------|
| POST | `/submit` | Upload audio, create attempt, trigger pipeline | `{id, status}` 202 |
| GET | `/{id}/status` | Poll status (1.5s interval from frontend) | `AttemptStatusOut` |
| GET | `/history/{question_id}` | All attempts for a question | `AttemptOut[]` |
| POST | `/{id}/improve` | Rewrite transcript at +1 band | `ImproveOut` |
| GET | `/{id}/pronunciation` | Per-word confidence scores | `{words: PronunciationWord[]}` |
| GET | `/{id}/audio` | Stream recorded audio file | FileResponse |

### Questions — `/api/v1/questions`

| Method | Path | Purpose | Returns |
|--------|------|---------|---------|
| GET | `/part1` | List Part 1 Q&A questions | `Question[]` |
| GET | `/part2` | List Part 2 cue cards | `Question[]` |
| GET | `/part3` | List Part 3 discussion groups | `Part3GroupOut[]` |
| GET | `/{id}` | Single question detail | `Question` |
| GET | `/forecast` | Topics ranked by recency + frequency | `ForecastEntry[]` |
| POST | `/{id}/sample-answer` | Generate model answer | `SampleAnswerResponse` |
| POST | `/{id}/topic-vocab` | Generate advanced vocabulary list | `TopicVocabResponse` |
| POST | `/bulk` | Bulk import questions | `{inserted, skipped}` |
| POST | `/` | Create single question | `Question` 201 |

### System — `/api/v1/system`

| Method | Path | Purpose | Returns |
|--------|------|---------|---------|
| GET | `/info` | Config, Whisper model, Ollama reachability, active model | `SystemInfoOut` |
| PATCH | `/model` | Switch active Ollama model at runtime (server-side, no restart) | `SystemInfoOut` |

### Dashboard — `/api/v1/dashboard`

| Method | Path | Purpose | Returns |
|--------|------|---------|---------|
| GET | `/` | Streaks, estimated band, 180-day heatmap | `DashboardOut` |

### TTS — `/api/v1/tts`

| Method | Path | Purpose | Returns |
|--------|------|---------|---------|
| GET | `/pronounce?text=…` | TTS for a word or phrase | FileResponse (WAV) |
| GET | `/{question_id}` | TTS for full question text | FileResponse (WAV) |

> **Note:** No authentication on any endpoint. Single-user only (UserStats.id = 1 hardcoded).

---

## 5. Frontend API Client (`src/api/client.ts`)

```typescript
// Questions
fetchPart1Questions(hideAnswered)           → Question[]
fetchPart2Questions(category, hideAnswered) → Question[]
fetchPart3Questions(category, hideAnswered) → Part3Group[]
fetchQuestion(id)                           → Question
fetchForecast()                             → ForecastEntry[]
fetchSampleAnswer(questionId)               → SampleAnswerResponse   // 60s timeout
fetchTopicVocab(questionId)                 → TopicVocabResponse      // 60s timeout

// Attempts
submitAttempt(questionId, audioBlob)        → { id, status }
fetchAttemptStatus(attemptId)               → Attempt
fetchAttemptHistory(questionId)             → Attempt[]
fetchImprovedVersion(attemptId)             → ImproveResponse         // 60s timeout
fetchPronunciationDetails(attemptId)        → { words: PronunciationWord[] }
getAttemptAudioUrl(attemptId)               → string  (URL, no fetch)

// System & Dashboard
fetchDashboard()                            → DashboardData
fetchSystemInfo()                           → SystemInfo
patchOllamaModel(model)                     → SystemInfo
```

Default timeout: 10s. Scoring/TTS/AI features: 60s.

---

## 6. Key Services

### `services/scoring.py`
Orchestrates the full scoring pipeline:
1. Load prompt template (cached in `_prompt_cache` after first disk read)
2. Load BAND-SCORES.md (cached in `_BAND_DESCRIPTORS` at module import — **restart required to pick up changes**)
3. Interpolate template with question, transcript, signals
4. Call `ollama_client.generate()` with `temperature=0.3`, `num_predict=1024`
5. Parse JSON response with fallback repair for truncation
6. Clamp all 4 criteria to 0–9 in 0.5 steps
7. Return overall = mean of 4 criteria

### `services/transcription.py`
- Lazy-loads Whisper once (thread-safe) into a dedicated single-thread executor
- CUDA fallback: load-time failure → CPU; runtime failure → sets `_force_cpu_fallback`, retries once
- Returns `{transcript, words: [{word, start, end, probability}]}`
- Empty audio → raises immediately without hanging

### `services/ollama_client.py`
- Singleton `httpx.AsyncClient` (connection pooling)
- Retries once on `ConnectError` (handles Ollama cold-start)
- Logs: `model=`, `prompt_len=`, `resp_len=`, `latency_ms=` on every call — **use this to verify which model is active**

### `services/tts.py`
- Kokoro TTS pipeline, lazy-loaded on first request
- Cache: `data/tts_cache/{question_id}.wav`
- Evicts oldest files when cache exceeds `TTS_CACHE_MAX_MB`

### `services/audio.py`
- Phase 1: Delete audio files older than `AUDIO_RETENTION_DAYS`
- Phase 2: If still over `MAX_AUDIO_SIZE_MB`, delete oldest until within limit

---

## 7. Database Schema

### `questions`
| Column | Type | Notes |
|--------|------|-------|
| id | PK | |
| part | str | `"1"`, `"2"`, `"3"` |
| topic | str? | |
| category | str? | `person`, `object`, `activity`, `place` |
| parent_question_id | FK? | Part 3 → Part 2 parent |
| text | str | Unique for dedup during seeding |
| bullet_points | JSON str? | Part 2 cue card points |
| topic_tag | str? | e.g. `environment`, `technology` |
| source | str? | e.g. `Cambridge 17` |
| last_seen_date | date? | When topic last appeared in real IELTS |

### `attempts`
| Column | Type | Notes |
|--------|------|-------|
| id | PK | |
| question_id | FK | Indexed |
| audio_path | str? | Relative path |
| transcript | str? | |
| score | float? | Overall band (mean of 4 criteria) |
| fluency | float? | 0–9, 0.5 steps |
| vocabulary | float? | 0–9, 0.5 steps |
| grammar | float? | 0–9, 0.5 steps |
| pronunciation | float? | 0–9, 0.5 steps |
| feedback_text | str? | 1-sentence improvement tip |
| error_highlights | JSON? | `[{word, type, correction, explanation}]` |
| word_timestamps | JSON? | `[{word, start, end, probability}]` |
| duration_seconds | int? | |
| status | str | Indexed. See status transitions above |
| created_at | datetime | Indexed |

### `daily_activity`
| Column | Type | Notes |
|--------|------|-------|
| date | date | Unique |
| attempts_count | int | |
| intensity | int | 0–4 (for heatmap color) |

### `user_stats` (single row, id=1)
| Column | Type | Notes |
|--------|------|-------|
| current_streak | int | Consecutive days ending today |
| longest_streak | int | |
| total_attempts | int | |
| estimated_band | float? | Rolling average of last 10 ready attempts |

---

## 8. Configuration (Environment Variables)

Set via `.env.pc` or `.env.laptop`, loaded by `run.ps1`. All have defaults in `config.py`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `PROFILE` | `laptop` | Label shown in sidebar |
| `WHISPER_MODEL` | `base` | `base`, `small`, `medium`, `large-v3` |
| `WHISPER_DEVICE` | `cpu` | `cpu` or `cuda` |
| `WHISPER_COMPUTE_TYPE` | `int8` | `int8`, `float16`, `float32` |
| `OLLAMA_MODEL` | `gemma3:1b` | Default model; overridable at runtime via PATCH /model |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama HTTP endpoint |
| `OLLAMA_GPU_LAYERS` | `0` | GPU layers to offload (0=CPU, 99=all) |
| `MAX_AUDIO_SIZE_MB` | `300` | Total audio directory size cap |
| `AUDIO_RETENTION_DAYS` | `60` | Delete audio older than N days |
| `DB_PATH` | `data/articulate.db` | SQLite file |
| `AUDIO_DIR` | `data/audio` | Audio storage |
| `TTS_CACHE_DIR` | `data/tts_cache` | TTS cache |
| `TTS_VOICE` | `af_heart` | Kokoro voice |
| `TTS_CACHE_MAX_MB` | `100` | TTS cache size cap |
| `LOW_CONFIDENCE_THRESHOLD` | `0.6` | Whisper word probability below this → flagged for pronunciation |
| `GAP_THRESHOLD` | `0.5` | Pause (seconds) before a word → counted as fluency gap |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Comma-separated allowed origins |

**Runtime model override:** `PATCH /api/v1/system/model` sets `_runtime_model` in memory. Survives page refresh, resets on server restart. Env var is the durable default.

---

## 9. Prompt Templates

All prompts are in `backend/prompts/`. Loaded from disk once at startup, cached in memory.
**Changing a prompt file requires server restart.**

| File | Used by | Placeholders |
|------|---------|-------------|
| `score_part1.txt` | scoring.py | `{band_descriptors}`, `{question_text}`, `{transcript}`, `{flagged_words}`, `{fluency_context}`, `{vocab_signal}`, `{grammar_context}` |
| `score_part2.txt` | scoring.py | Same as above |
| `score_part3.txt` | scoring.py | Same as above |
| `improve.txt` | improve.py | `{question_text}`, `{transcript}`, `{current_band}`, `{target_band}` |
| `sample_answer.txt` | ai_assist.py | `{question_text}`, `{target_band}`, `{part}`, `{word_count}` |
| `topic_vocab.txt` | ai_assist.py | `{question_text}` |

---

## 10. Known Constraints & Caveats

| Area | Issue |
|------|-------|
| **Auth** | None. All endpoints public. Single-user only (`user_stats.id = 1`). |
| **Model validation** | PATCH /model accepts any string. Bad model name fails silently on next score. Verify via backend logs: `Ollama generate: model=…` |
| **Prompt caching** | `BAND-SCORES.md` + prompt `.txt` files loaded at import. Must restart server after editing. |
| **CUDA (Windows)** | Partial DLL presence can pass import check but fail inference. `_force_cpu_fallback` flag handles this with one retry. |
| **Whisper hang** | Dedicated single-thread executor queues requests rather than spawning threads. Long transcriptions block the queue. |
| **Polling timeout** | 3 minutes, client-side only. Stuck attempt not auto-cancelled on backend. |
| **Score display** | Criteria shown as `X.X` (e.g. `5.5`). Overall score is the arithmetic mean of the 4 criteria, rounded to nearest 0.5. |
| **Audio format** | Prefers WebM/Opus; falls back to WebM then MP4. Android may send MP4. |
| **Part 3 orphans** | If `parent_question_id` resolution fails during seeding, questions are orphaned. Logged as warning. |
| **No cascade delete** | Deleting a question leaves orphaned attempt rows. |
| **LanguageTool** | Optional. Requires Java JRE. If unavailable, `grammar_context = "grammar checker unavailable"`. The LLM still scores grammar from the transcript directly. |
| **TTS cache key** | Pronunciation endpoint uses `pronounce_{hash}` as fake question_id to avoid collision. |
