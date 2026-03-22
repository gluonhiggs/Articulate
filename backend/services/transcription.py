from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import threading
import time
from typing import Any, Dict, List

from backend.config import get_settings


logger = logging.getLogger(__name__)

# Module-level cache for the loaded Whisper model
_whisper_model = None
_whisper_lock = threading.Lock()

# Set to True when a CUDA inference error occurs at runtime so that
# _get_model() loads the CPU fallback on the next call instead of
# re-attempting CUDA (which would fail the same way).
_force_cpu_fallback: bool = False

# Dedicated single-thread executor for Whisper.
# Using None (default executor) risks pool exhaustion when a transcription hangs:
# asyncio.wait_for cancels the coroutine but the thread keeps running, and the
# default pool has os.cpu_count()*5 threads — fill them all with hung calls and
# new transcriptions queue forever. A max_workers=1 executor bounds the damage to
# one hung call; subsequent calls wait in the asyncio queue (and time out) rather
# than spawning unbounded threads.
_whisper_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="whisper"
)


def _get_model():
    """Lazy-load and cache the WhisperModel instance (thread-safe).

    Falls back to CPU/int8 if:
    - WhisperModel() raises at load time (e.g. CUDA DLL not found during init), OR
    - a previous inference call set _force_cpu_fallback=True (e.g. cublas64_12.dll
      present enough for construction but missing for actual matrix operations).
    """
    global _whisper_model, _force_cpu_fallback
    with _whisper_lock:
        if _whisper_model is None:
            from faster_whisper import WhisperModel

            settings = get_settings()
            use_cpu = _force_cpu_fallback or settings.whisper_device.lower() == "cpu"

            device = "cpu" if use_cpu else settings.whisper_device
            compute_type = "int8" if use_cpu else settings.whisper_compute_type

            logger.info(
                "Loading Whisper model '%s' on device='%s' compute_type='%s'%s",
                settings.whisper_model,
                device,
                compute_type,
                " (CPU fallback)" if use_cpu and settings.whisper_device.lower() != "cpu" else "",
            )
            try:
                _whisper_model = WhisperModel(
                    settings.whisper_model,
                    device=device,
                    compute_type=compute_type,
                )
                logger.info("Whisper model loaded successfully.")
            except Exception as exc:
                if device != "cpu":
                    # Load-time CUDA failure → fall back to CPU immediately
                    logger.warning(
                        "Failed to load Whisper on device='%s' (%s). "
                        "Falling back to CPU/int8.",
                        device,
                        exc,
                    )
                    _force_cpu_fallback = True
                    _whisper_model = WhisperModel(
                        settings.whisper_model,
                        device="cpu",
                        compute_type="int8",
                    )
                    logger.info("Whisper model loaded on CPU (fallback).")
                else:
                    raise
    return _whisper_model


def _collect_segments(segments, audio_path: str) -> Dict[str, Any]:
    """Iterate the segment generator and collect transcript + word timestamps."""
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


def _run_transcribe(model, audio_path: str) -> Dict[str, Any]:
    """Run model.transcribe() and collect results.  Does NOT catch exceptions."""
    segments, info = model.transcribe(
        audio_path,
        language="en",                    # skip 30s language-detection pass; app is English-only
        beam_size=1,                      # greedy decoding: 2-4× faster, ~1% WER trade-off
        word_timestamps=True,
        vad_filter=True,
        condition_on_previous_text=False, # prevents hallucination loops on disfluent speech
        vad_parameters={
            "min_silence_duration_ms": 500,  # default 2000ms — cuts end-of-recording wait
            "speech_pad_ms": 400,
            "threshold": 0.5,
        },
    )
    # VAD found no speech — return empty immediately without iterating the
    # generator. Iterating an empty chunk through the Whisper model can hang.
    if info.duration_after_vad == 0.0:
        logger.info("Transcribing %s: VAD found no speech (duration_after_vad=0)", audio_path)
        return {"transcript": "", "words": []}
    return _collect_segments(segments, audio_path)


def _sync_transcribe(audio_path: str) -> Dict[str, Any]:
    """Synchronous transcription — called in a thread pool executor.

    First attempt uses the configured device (CUDA when running from run.ps1).
    If inference raises (e.g. cublas64_12.dll missing at runtime), the model
    cache is cleared, _force_cpu_fallback is set, the model is reloaded on CPU,
    and transcription is retried once.
    """
    global _whisper_model, _force_cpu_fallback

    model = _get_model()
    file_size = os.path.getsize(audio_path) if os.path.exists(audio_path) else -1
    settings = get_settings()
    configured_device = settings.whisper_device.lower()
    active_device = "cpu" if _force_cpu_fallback else configured_device

    logger.info(
        "========== WHISPER START ==========\n"
        "  file      : %s (%.1f KB)\n"
        "  model     : %s\n"
        "  device    : %s  compute_type=%s%s",
        audio_path, file_size / 1024,
        settings.whisper_model,
        active_device,
        "int8" if active_device == "cpu" else settings.whisper_compute_type,
        "  [CPU fallback]" if _force_cpu_fallback else "",
    )

    t0 = time.perf_counter()
    try:
        result = _run_transcribe(model, audio_path)
        elapsed = time.perf_counter() - t0
        audio_duration = result["words"][-1]["end"] if result.get("words") else 0
        rtf = elapsed / audio_duration if audio_duration > 0 else 0
        logger.info(
            "========== WHISPER DONE ==========\n"
            "  device    : %s\n"
            "  audio     : %.1fs\n"
            "  wall time : %.2fs\n"
            "  RTF       : %.2f  (real-time factor — lower is faster; <1.0 = faster than real time)",
            active_device, audio_duration, elapsed, rtf,
        )
        return result

    except Exception as exc:
        elapsed = time.perf_counter() - t0
        # If the model was on a non-CPU device, a CUDA runtime error can surface
        # here at inference time (e.g. cublas64_12.dll present enough for
        # WhisperModel() but missing for actual matrix ops).  Flag for CPU and
        # retry once — subsequent calls will skip CUDA entirely.
        if configured_device != "cpu":
            logger.warning(
                "Transcription inference failed on device='%s' after %.2fs (%s). "
                "Switching to CPU/int8 for this and future calls.",
                configured_device, elapsed, exc,
            )
            with _whisper_lock:
                _force_cpu_fallback = True
                _whisper_model = None  # force _get_model() to reload on CPU

            cpu_model = _get_model()
            t1 = time.perf_counter()
            result = _run_transcribe(cpu_model, audio_path)
            elapsed_cpu = time.perf_counter() - t1
            audio_duration = result["words"][-1]["end"] if result.get("words") else 0
            rtf = elapsed_cpu / audio_duration if audio_duration > 0 else 0
            logger.info(
                "========== WHISPER DONE (CPU fallback) ==========\n"
                "  device    : cpu\n"
                "  audio     : %.1fs\n"
                "  wall time : %.2fs\n"
                "  RTF       : %.2f",
                audio_duration, elapsed_cpu, rtf,
            )
            return result

        raise  # already on CPU — propagate so the pipeline marks it as failed


def _warmup_probe() -> None:
    """Run a tiny dummy transcription to validate the device at startup.

    Synthesises 0.5 s of silence (8 000 samples @ 16 kHz) and feeds it to
    the model via a temporary WAV file.  If CUDA inference raises (e.g.
    cublas64_12.dll missing), _force_cpu_fallback is set here — before any
    real request arrives — so the first user recording goes straight to CPU
    instead of failing then retrying.
    """
    import io
    import struct
    import wave

    global _whisper_model, _force_cpu_fallback

    settings = get_settings()
    if settings.whisper_device.lower() == "cpu":
        logger.info("Whisper warmup probe: device=cpu, skipping CUDA check.")
        return

    model = _get_model()

    # Build a minimal 16-bit PCM WAV in memory (0.5 s silence)
    n_samples = 8_000  # 0.5 s @ 16 kHz
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)   # 16-bit
        wf.setframerate(16_000)
        wf.writeframes(struct.pack(f"<{n_samples}h", *([0] * n_samples)))
    buf.seek(0)

    # Write to a temp file (faster-whisper needs a file path)
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        tf.write(buf.read())
        tmp_path = tf.name

    try:
        # vad_filter=False so empty audio isn't short-circuited before the GPU call
        segs, info = model.transcribe(tmp_path, vad_filter=False, word_timestamps=False)
        list(segs)  # force generator evaluation — this is where CUDA fires
        logger.info(
            "Whisper warmup probe: device='%s' OK (duration=%.2fs)",
            settings.whisper_device,
            info.duration,
        )
    except Exception as exc:
        logger.warning(
            "Whisper warmup probe: device='%s' failed (%s). "
            "Switching to CPU/int8 for all transcriptions.",
            settings.whisper_device,
            exc,
        )
        with _whisper_lock:
            _force_cpu_fallback = True
            _whisper_model = None  # will reload on CPU on next _get_model() call
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


async def warmup_probe() -> None:
    """Async wrapper — runs _warmup_probe() in the Whisper executor at startup."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_whisper_executor, _warmup_probe)


async def transcribe(audio_path: str) -> Dict[str, Any]:
    """
    Transcribe an audio file asynchronously.

    Returns:
        {
            "transcript": str,
            "words": [{"word": str, "start": float, "end": float, "probability": float}]
        }
    """
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(_whisper_executor, _sync_transcribe, audio_path)
    return result
