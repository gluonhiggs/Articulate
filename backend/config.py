from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,  # Loaded externally via export before starting server
        case_sensitive=False,
        extra="ignore",
    )

    profile: str = "laptop"
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    ollama_model: str = "gemma3:1b"
    ollama_base_url: str = "http://localhost:11434"
    ollama_gpu_layers: int = 0
    pronunciation_tier: int = 1
    max_audio_size_mb: int = 300
    audio_retention_days: int = 60
    db_path: str = "data/articulate.db"
    audio_dir: str = "data/audio"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
