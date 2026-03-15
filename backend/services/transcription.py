from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from backend.config import get_settings

logger = logging.getLogger(__name__)

# Module-level cache for the loaded Whisper model
_whisper_model = None


def _get_model():
    """Lazy-load and cache the WhisperModel instance."""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        settings = get_settings()
        logger.info(
            "Loading Whisper model '%s' on device='%s' compute_type='%s'",
            settings.whisper_model,
            settings.whisper_device,
            settings.whisper_compute_type,
        )
        _whisper_model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
        logger.info("Whisper model loaded successfully.")
    return _whisper_model


def _sync_transcribe(audio_path: str) -> Dict[str, Any]:
    """Synchronous transcription — called in a thread pool executor."""
    model = _get_model()
    segments, _info = model.transcribe(
        audio_path,
        word_timestamps=True,
        vad_filter=True,
    )

    full_transcript = []
    words: List[Dict[str, Any]] = []

    for segment in segments:
        full_transcript.append(segment.text.strip())
        if segment.words:
            for word in segment.words:
                words.append(
                    {
                        "word": word.word.strip(),
                        "start": round(word.start, 3),
                        "end": round(word.end, 3),
                        "probability": round(word.probability, 4),
                    }
                )

    return {
        "transcript": " ".join(full_transcript),
        "words": words,
    }


async def transcribe(audio_path: str) -> Dict[str, Any]:
    """
    Transcribe an audio file asynchronously.

    Returns:
        {
            "transcript": str,
            "words": [{"word": str, "start": float, "end": float, "probability": float}]
        }
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _sync_transcribe, audio_path)
    return result
