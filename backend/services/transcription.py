from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import time
from typing import Any, Dict, List

from backend.config import get_settings


logger = logging.getLogger(__name__)

# Thread pool for Groq API calls (network I/O — safe to allow concurrency).
_whisper_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=4, thread_name_prefix="whisper"
)


def _sync_transcribe(audio_path: str) -> Dict[str, Any]:
    """Call the Groq Whisper API synchronously — runs in a thread pool executor."""
    from groq import Groq

    settings = get_settings()
    if not settings.groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to your .env file to enable transcription."
        )

    client = Groq(api_key=settings.groq_api_key)
    file_size = os.path.getsize(audio_path) if os.path.exists(audio_path) else -1

    logger.info(
        "========== GROQ WHISPER START ==========\n"
        "  file  : %s (%.1f KB)\n"
        "  model : %s",
        audio_path,
        file_size / 1024,
        settings.groq_whisper_model,
    )

    t0 = time.perf_counter()
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            file=(os.path.basename(audio_path), f),
            model=settings.groq_whisper_model,
            response_format="verbose_json",
            timestamp_granularities=["word"],
            language="en",
            temperature=0,
        )
    elapsed = time.perf_counter() - t0

    transcript: str = response.text or ""

    word_list: List[Dict[str, Any]] = []
    raw_words = getattr(response, "words", None) or []
    for w in raw_words:
        # Groq SDK may return plain dicts or Word objects depending on version.
        if isinstance(w, dict):
            _word, _start, _end = w.get("word", ""), w.get("start", 0), w.get("end", 0)
        else:
            _word, _start, _end = getattr(w, "word", ""), getattr(w, "start", 0), getattr(w, "end", 0)
        word_list.append(
            {
                "word": str(_word or "").strip(),
                "start": round(float(_start), 3),
                "end": round(float(_end), 3),
                # Groq does not expose per-word confidence scores.
                # Set to 1.0 so downstream pronunciation scoring skips
                # confidence-based flagging (disfluency detection still works).
                "probability": 1.0,
            }
        )

    audio_duration = word_list[-1]["end"] if word_list else 0.0
    logger.info(
        "========== GROQ WHISPER DONE ==========\n"
        "  audio     : %.1fs\n"
        "  wall time : %.2fs\n"
        "  words     : %d",
        audio_duration,
        elapsed,
        len(word_list),
    )

    return {"transcript": transcript, "words": word_list}


async def transcribe(audio_path: str) -> Dict[str, Any]:
    """
    Transcribe an audio file asynchronously via the Groq Whisper API.

    Returns:
        {
            "transcript": str,
            "words": [{"word": str, "start": float, "end": float, "probability": float}]
        }
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_whisper_executor, _sync_transcribe, audio_path)
