# Articulate

An IELTS Speaking practice app. Record your responses, get Whisper transcription via Groq API, and receive band scores (Fluency, Vocabulary, Grammar, Pronunciation) from a cloud LLM.

---

## Prerequisites

| Tool | Why | Install |
|------|-----|---------|
| **Python 3.11+** | Backend runtime | [python.org](https://www.python.org/downloads/) |
| **[uv](https://docs.astral.sh/uv/)** | Python package manager | `pip install uv` |
| **[Bun](https://bun.sh/)** | Frontend build & dev server | [bun.sh](https://bun.sh/) |
| **Groq API key** | Whisper transcription | [console.groq.com](https://console.groq.com) (free tier) |
| **LLM API key** | Scoring LLM (Gemini, Groq, or any OpenAI-compatible API) | [aistudio.google.com](https://aistudio.google.com/apikey) (free) |
| **Java 11+** | LanguageTool grammar checker *(optional - auto-installed on Windows)* | [adoptium.net](https://adoptium.net/) |

---

## Installation

```sh
# 1. Clone the repository
git clone https://github.com/gluonhiggs/Articulate.git
cd Articulate

# 2. Create your config file
cp .env.example .env
# Edit .env - fill in GROQ_API_KEY and LLM_API_KEY

# 3. Install Python dependencies
uv sync

# 4. Install frontend dependencies
cd frontend && bun install && cd ..
```

---

## Running

```sh
./run.sh        # Linux
.\run.ps1       # Windows
```

The script will:
1. Load `.env`
2. Install Java if missing (for LanguageTool grammar checking)
3. Build the frontend if source files changed since the last build
4. Start the Vite dev server (port **5173**) in a new terminal window
5. Start the FastAPI backend (port **8000**)

Open **http://localhost:5173** in your browser.

> **Interactive API docs:** http://localhost:8000/docs

---

## Environment Variables

Edit `.env` to customise. All have defaults.

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | *(required)* | Groq API key for Whisper transcription |
| `GROQ_WHISPER_MODEL` | `whisper-large-v3-turbo` | Groq Whisper model |
| `LLM_API_KEY` | *(required)* | API key for cloud LLM (Gemini, Groq, etc.) |
| `LLM_MODEL` | `gemma-3-27b-it` | LLM model name (overridable at runtime via sidebar) |
| `LLM_BASE_URL` | Gemini API endpoint | LLM endpoint - swap to use a different provider |
| `MAX_AUDIO_SIZE_MB` | `500` | Total audio storage cap |
| `AUDIO_RETENTION_DAYS` | `90` | Delete audio older than N days |
| `TTS_VOICE` | `af_heart` | Kokoro TTS voice |
| `TTS_CACHE_MAX_MB` | `100` | TTS cache size cap |

---
See [ARCHITECTURE.md](ARCHITECTURE.md) for a full system overview, API reference, and database schema.
