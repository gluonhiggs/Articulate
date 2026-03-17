from __future__ import annotations

import asyncio
import logging
import wave
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


def evict_tts_cache(cache_dir: str, max_size_mb: int) -> None:
    """Delete oldest .wav files until total cache size is at or below max_size_mb."""
    cache_path = Path(cache_dir)
    if not cache_path.exists():
        return

    wav_files = sorted(cache_path.glob("*.wav"), key=lambda p: p.stat().st_mtime)
    if not wav_files:
        return

    total_bytes = sum(p.stat().st_size for p in wav_files)
    max_bytes = max_size_mb * 1024 * 1024

    if total_bytes <= max_bytes:
        return

    evicted_count = 0
    freed_bytes = 0
    for wav_file in wav_files:
        if total_bytes <= max_bytes:
            break
        try:
            size = wav_file.stat().st_size
            wav_file.unlink()
            total_bytes -= size
            freed_bytes += size
            evicted_count += 1
        except (PermissionError, OSError) as exc:
            logger.warning("Could not evict TTS cache file %s: %s", wav_file, exc)

    if evicted_count:
        logger.info(
            "TTS cache eviction: removed %d file(s), freed %.1f MB",
            evicted_count,
            freed_bytes / (1024 * 1024),
        )

_pipeline = None
_lock = asyncio.Lock()


def _init_kokoro():
    from kokoro import KPipeline

    return KPipeline(lang_code="a")


async def _ensure_pipeline() -> None:
    global _pipeline
    if _pipeline is not None:
        return
    async with _lock:
        if _pipeline is not None:
            return
        logger.info("Loading Kokoro TTS model (first request)…")
        loop = asyncio.get_running_loop()
        _pipeline = await loop.run_in_executor(None, _init_kokoro)
        logger.info("Kokoro TTS model loaded.")


def _synthesize(pipeline, text: str, voice: str, output_path: Path) -> None:
    import torch

    samples = []
    for _gs, _ps, audio in pipeline(text, voice=voice):
        samples.append(audio)
    if not samples:
        raise RuntimeError(f"Kokoro TTS produced no audio for: {text!r}")
    full_audio = torch.cat(samples)

    # Write WAV using stdlib — no extra dependency
    audio_np = (full_audio.numpy() * 32767).astype(np.int16)
    with wave.open(str(output_path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(audio_np.tobytes())


async def get_or_generate_tts(
    question_id: int | str,
    text: str,
    cache_dir: str,
    voice: str,
) -> Path:
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    wav_file = cache_path / f"{question_id}.wav"

    if wav_file.exists():
        return wav_file

    await _ensure_pipeline()
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _synthesize, _pipeline, text, voice, wav_file)
    logger.info("Generated TTS for question %s → %s", question_id, wav_file)
    return wav_file
