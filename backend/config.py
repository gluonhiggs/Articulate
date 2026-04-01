from __future__ import annotations

from functools import lru_cache

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
