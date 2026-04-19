from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path as _Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,  # Loaded externally via export before starting server
        case_sensitive=False,
        extra="ignore",
    )

    profile: str = ""
    groq_api_key: str = ""
    groq_whisper_model: str = "whisper-large-v3-turbo"
    # ── Transcription mode ──────────────────────────────────────────────────
    # "" = interactive terminal prompt at first startup (result saved to .env)
    # "groq"  = Mode 2: Groq API, fast, no per-word pronunciation signal
    # "local" = Mode 1: faster-whisper, real word probabilities, full pronunciation scoring
    transcription_mode: str = ""
    # Model override for local mode. "" = auto: "large-v3-turbo" (GPU) / "small" (CPU).
    local_whisper_model: str = ""
    # Device override for local mode. "auto" probes CUDA and falls back to CPU.
    local_whisper_device: str = "auto"
    # Compute type override. "" = auto: "float16" (GPU) / "int8" (CPU).
    local_whisper_compute_type: str = ""
    llm_model: str = "gemma-3-27b-it"
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    llm_api_key: str = ""
    pronunciation_tier: int = 1
    max_audio_size_mb: int = 300
    audio_retention_days: int = 60
    db_path: str = "data/articulate.db"
    audio_dir: str = "data/audio"
    tts_cache_dir: str = "data/tts_cache"
    tts_voice: str = "af_heart"
    tts_cache_max_mb: int = 100
    low_confidence_threshold: float = 0.6
    gap_threshold: float = 0.5
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # ── Desktop / packaged app overrides ────────────────────────────────────
    # Set ARTICULATE_DATA_DIR to relocate db/audio/tts paths to OS user-data dir.
    data_dir: str = ""
    # Set ARTICULATE_PORT to override the uvicorn port (Electron picks a free port).
    port: int = 8000
    # Set ARTICULATE_HF_HOME to redirect HuggingFace model cache (Kokoro weights).
    hf_home: str = ""

    @model_validator(mode="after")
    def _apply_desktop_overrides(self) -> "Settings":
        if self.data_dir:
            import os as _os

            base = self.data_dir
            if not self.db_path.startswith(base):
                self.db_path = _os.path.join(base, "articulate.db")
            if not self.audio_dir.startswith(base):
                self.audio_dir = _os.path.join(base, "audio")
            if not self.tts_cache_dir.startswith(base):
                self.tts_cache_dir = _os.path.join(base, "tts_cache")
        if self.hf_home:
            os.environ["HF_HOME"] = self.hf_home
            os.environ["HUGGINGFACE_HUB_CACHE"] = os.path.join(self.hf_home, "hub")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


_runtime_model: str | None = None


def get_active_model() -> str:
    """Return runtime override if set, else the configured default."""
    return _runtime_model if _runtime_model is not None else get_settings().llm_model


def set_runtime_model(model: str) -> None:
    global _runtime_model
    _runtime_model = model


# ── Transcription mode persistence ───────────────────────────────────────────


def get_mode_file() -> _Path:
    """Return the path to data/mode (one-word transcription mode store)."""
    return _Path(get_settings().db_path).parent / "mode"


def write_mode_file(mode: str) -> None:
    """Write *mode* ('groq' or 'local') to data/mode, creating data/ if needed."""
    p = get_mode_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(mode, encoding="utf-8")
