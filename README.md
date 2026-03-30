# Articulate

A local, offline-first IELTS Speaking practice app. Record your responses, get Whisper transcription, and receive band scores (Fluency, Vocabulary, Grammar, Pronunciation) from a local LLM — no cloud required.

---

## Prerequisites

| Tool | Why | Install |
|------|-----|---------|
| **Python 3.11+** | Backend runtime | [python.org](https://www.python.org/downloads/) |
| **[uv](https://docs.astral.sh/uv/)** | Python package manager | `pip install uv` |
| **[Bun](https://bun.sh/)** | Frontend build & dev server | [bun.sh](https://bun.sh/) |
| **[Ollama](https://ollama.com/)** | Local LLM inference (GPU/CPU mode) | [ollama.com](https://ollama.com/) |
| **Java 11+** | LanguageTool grammar checker *(optional — auto-installed on Windows)* | [adoptium.net](https://adoptium.net/) |
| **NVIDIA GPU + CUDA 12.1** | GPU acceleration *(optional — CPU works too)* | [CUDA Toolkit](https://developer.nvidia.com/cuda-12-1-0-download-archive) |

> **API mode alternative:** If you have a Gemini API key you can skip Ollama entirely — see the [Gemini API mode](#gemini-api-mode) section below.

> **Note:** The app runs entirely on your local machine accessed via `localhost`. No HTTPS or certificate setup is required.

---

## Installation

```sh
# 1. Clone the repository
git clone https://github.com/gluonhiggs/Articulate.git
cd Articulate

# 2. Install Python dependencies
uv sync

# 3. Install frontend dependencies
cd frontend && bun install && cd ..
```

---

## Run Profiles

The startup scripts (`run.ps1` / `run.sh`) accept a **profile** argument that controls which `.env.*` file is loaded and which AI models are used.

| Profile | Command | Whisper model | LLM | Device |
|---------|---------|---------------|-----|--------|
| `auto` *(default)* | `.\run.ps1` | auto-detected | auto-detected | auto-detected |
| `pc` | `.\run.ps1 pc` | `large-v3` | `gemma3:12b` | CUDA (GPU) |
| `laptop` | `.\run.ps1 laptop` | `base` | `gemma3:1b` | CPU |
| `gemini` | `.\run.ps1 gemini` | `base` | Gemini API | CPU |

**`auto` mode** (default): reads `.env.gemini` — if `LLM_API_KEY` is set to a real key, uses API mode; otherwise falls back to GPU (`pc`) mode.

---

## Running

### Windows

```powershell
# Pull the Ollama model first (GPU/CPU mode only)
ollama pull gemma3:12b   # or gemma3:1b for laptop

# Start backend + frontend (auto-detects profile)
.\run.ps1

# Or specify a profile explicitly:
.\run.ps1 pc
.\run.ps1 laptop
```

### Linux / macOS

```bash
chmod +x run.sh

# Pull the Ollama model first (GPU/CPU mode only)
ollama pull gemma3:12b

# Start backend + frontend
./run.sh          # auto mode
./run.sh pc       # GPU profile
./run.sh laptop   # CPU profile
```

The script will:
1. Load the matching `.env.<profile>` file
2. Install/verify CUDA torch and GPU extras if on the `pc` profile (Windows)
3. Install Java if missing (for LanguageTool grammar checking)
4. Build the frontend if source files have changed since the last build
5. Start the Vite dev server (port **5173**) in a new terminal window
6. Start the FastAPI backend (port **8000**)

Open **http://localhost:5173** in your browser.

> **Interactive API docs:** http://localhost:8000/docs

---

## Gemini API Mode

If you prefer a cloud LLM over running Ollama locally:

1. Get a [Gemini API key](https://aistudio.google.com/apikey)
2. Create `.env.gemini` in the project root:
   ```
   LLM_API_KEY=your-actual-api-key-here
   ```
3. Run with the `gemini` profile (or just `auto` — it detects the key automatically):
   ```powershell
   .\run.ps1 gemini
   ```

---

## Environment Variables

All variables have defaults. To customise, edit the relevant `.env.<profile>` file.

| Variable | Default | Description |
|----------|---------|-------------|
| `PROFILE` | `laptop` | Label shown in the sidebar |
| `WHISPER_MODEL` | `base` | `base`, `small`, `medium`, `large-v3` |
| `WHISPER_DEVICE` | `cpu` | `cpu` or `cuda` |
| `WHISPER_COMPUTE_TYPE` | `int8` | `int8`, `float16`, `float32` |
| `OLLAMA_MODEL` | `gemma3:1b` | Default LLM (overridable at runtime via sidebar) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `OLLAMA_GPU_LAYERS` | `0` | GPU layers to offload (`0`=CPU, `99`=all) |
| `MAX_AUDIO_SIZE_MB` | `300` | Total audio storage cap |
| `AUDIO_RETENTION_DAYS` | `60` | Delete audio older than N days |
| `TTS_VOICE` | `af_heart` | Kokoro TTS voice |
| `TTS_CACHE_MAX_MB` | `100` | TTS cache size cap |

---
See [ARCHITECTURE.md](ARCHITECTURE.md) for a full system overview, API reference, and database schema.