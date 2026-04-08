from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import threading
import time
from typing import Any, Dict, List, Tuple

from backend.config import get_settings

logger = logging.getLogger(__name__)


# ── Windows CUDA DLL path fix ─────────────────────────────────────────────────
# ctranslate2 on Windows loads cublas64_12.dll / cudart64_12.dll via the OS
# DLL search path (PATH), not via Python's import machinery.  The nvidia-*
# packages install those DLLs into site-packages/nvidia/*/bin/ which is NOT
# on PATH by default.  Prepend those dirs here, before ctranslate2 is loaded.

def _patch_cuda_dll_path() -> None:
    import sys
    if sys.platform != "win32":
        return
    import site
    for site_dir in site.getsitepackages():
        nvidia_dir = os.path.join(site_dir, "nvidia")
        if not os.path.isdir(nvidia_dir):
            continue
        for pkg in os.listdir(nvidia_dir):
            bin_dir = os.path.join(nvidia_dir, pkg, "bin")
            if os.path.isdir(bin_dir) and bin_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = bin_dir + os.pathsep + os.environ["PATH"]


_patch_cuda_dll_path()

# ── Thread pools ─────────────────────────────────────────────────────────────
# Local whisper is CPU-bound → single thread to avoid contention.
# Groq is network I/O → multiple threads fine.
_local_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="whisper-local"
)
_groq_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=4, thread_name_prefix="whisper-groq"
)

# ── Local model singleton ─────────────────────────────────────────────────────
_whisper_model = None
_whisper_lock = threading.Lock()
# Set True when a CUDA inference error occurs so _get_model() reloads on CPU.
_force_cpu_fallback: bool = False


# ── GPU detection ─────────────────────────────────────────────────────────────

def detect_gpu() -> bool:
    """Return True if an NVIDIA CUDA device is usable via ctranslate2."""
    try:
        import ctranslate2  # type: ignore[import]
        supported = ctranslate2.get_supported_compute_types("cuda")
        return bool(supported)
    except Exception:
        return False


def _resolve_device_and_model() -> Tuple[str, str, str]:
    """Return (device, compute_type, model_size) for local mode.

    Priority:
      1. local_whisper_device == "cpu" → force CPU
      2. detect_gpu() → CUDA  (large-v3-turbo / float16)
      3. fallback        → CPU (small / int8)
    local_whisper_model and local_whisper_compute_type override auto-selection.
    """
    settings = get_settings()

    force_cpu = settings.local_whisper_device.lower() == "cpu"
    if force_cpu:
        device, compute_type = "cpu", "int8"
    elif detect_gpu():
        device, compute_type = "cuda", "float16"
    else:
        device, compute_type = "cpu", "int8"

    model_size = settings.local_whisper_model or (
        "large-v3-turbo" if device == "cuda" else "small"
    )
    if settings.local_whisper_compute_type:
        compute_type = settings.local_whisper_compute_type

    return device, compute_type, model_size


# ── Local model loading ───────────────────────────────────────────────────────

def _get_model():
    """Lazy-load and cache the WhisperModel instance (thread-safe).

    Falls back to CPU/int8 if:
    - WhisperModel() raises at load time (e.g. CUDA DLL not found), OR
    - _force_cpu_fallback is True (set after a runtime inference failure).
    Raises ImportError if faster-whisper is not installed.
    """
    global _whisper_model, _force_cpu_fallback
    with _whisper_lock:
        if _whisper_model is not None:
            return _whisper_model

        from faster_whisper import WhisperModel  # type: ignore[import]

        device, compute_type, model_size = _resolve_device_and_model()
        if _force_cpu_fallback and device != "cpu":
            device, compute_type = "cpu", "int8"

        logger.info(
            "Loading faster-whisper model='%s' device='%s' compute_type='%s'%s",
            model_size, device, compute_type,
            " (CPU fallback)" if _force_cpu_fallback else "",
        )
        try:
            _whisper_model = WhisperModel(
                model_size, device=device, compute_type=compute_type
            )
            logger.info("faster-whisper model loaded.")
        except Exception as exc:
            if device != "cpu":
                logger.warning(
                    "Failed to load faster-whisper on '%s' (%s). Falling back to CPU/int8.",
                    device, exc,
                )
                _force_cpu_fallback = True
                _whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")
                logger.info("faster-whisper loaded on CPU (fallback).")
            else:
                raise
        return _whisper_model


# ── Model lifecycle helpers ───────────────────────────────────────────────────

def is_faster_whisper_installed() -> bool:
    """Return True if the faster-whisper package is importable."""
    try:
        import faster_whisper  # type: ignore[import]  # noqa: F401
        return True
    except ImportError:
        return False


def unload_model() -> None:
    """Release the cached WhisperModel from memory (thread-safe).

    Frees RAM immediately; CUDA memory is released via torch if available.
    Safe to call even if no model is loaded.
    """
    global _whisper_model, _force_cpu_fallback
    import gc
    with _whisper_lock:
        if _whisper_model is None:
            return
        had_cuda = False
        try:
            had_cuda = "cuda" in str(_whisper_model.model.device)
        except Exception:
            pass
        del _whisper_model
        _whisper_model = None
        _force_cpu_fallback = False
    gc.collect()
    if had_cuda:
        try:
            import torch  # type: ignore[import]
            torch.cuda.empty_cache()
        except Exception:
            pass
    logger.info("faster-whisper model unloaded.")


# ── Local transcription helpers ───────────────────────────────────────────────

def _collect_segments(segments) -> Dict[str, Any]:
    """Iterate the segment generator and collect transcript + word timestamps."""
    full_transcript: List[str] = []
    words: List[Dict[str, Any]] = []
    for segment in segments:
        full_transcript.append(segment.text.strip())
        if segment.words:
            for word in segment.words:
                words.append({
                    "word": word.word.strip(),
                    "start": round(word.start, 3),
                    "end": round(word.end, 3),
                    "probability": round(word.probability, 4),
                })
    return {"transcript": " ".join(full_transcript), "words": words}


def _run_transcribe_local(model, audio_path: str) -> Dict[str, Any]:
    """Run model.transcribe() and collect results. Does NOT catch exceptions."""
    segments, info = model.transcribe(
        audio_path,
        language="en",
        beam_size=1,                       # greedy: 2-4× faster, ~1% WER trade-off
        word_timestamps=True,
        vad_filter=True,
        condition_on_previous_text=False,  # prevents hallucination loops on disfluent speech
        vad_parameters={
            "min_silence_duration_ms": 500,
            "speech_pad_ms": 400,
            "threshold": 0.5,
        },
    )
    if info.duration_after_vad == 0.0:
        logger.info("Local whisper: VAD found no speech in %s", audio_path)
        return {"transcript": "", "words": []}
    return _collect_segments(segments)


def _sync_transcribe_local(audio_path: str) -> Dict[str, Any]:
    """Synchronous local transcription with CUDA→CPU runtime fallback."""
    global _whisper_model, _force_cpu_fallback

    model = _get_model()
    device, _, model_size = _resolve_device_and_model()
    active_device = "cpu" if _force_cpu_fallback else device
    file_size = os.path.getsize(audio_path) if os.path.exists(audio_path) else -1

    logger.info(
        "========== LOCAL WHISPER START ==========\n"
        "  file   : %s (%.1f KB)\n"
        "  model  : %s  device=%s%s",
        audio_path, file_size / 1024, model_size, active_device,
        "  [CPU fallback]" if _force_cpu_fallback else "",
    )

    t0 = time.perf_counter()
    try:
        result = _run_transcribe_local(model, audio_path)
        elapsed = time.perf_counter() - t0
        audio_duration = result["words"][-1]["end"] if result.get("words") else 0
        rtf = elapsed / audio_duration if audio_duration > 0 else 0
        logger.info(
            "========== LOCAL WHISPER DONE ==========\n"
            "  device    : %s\n"
            "  audio     : %.1fs\n"
            "  wall time : %.2fs\n"
            "  RTF       : %.2f  (<1.0 = faster than real time)",
            active_device, audio_duration, elapsed, rtf,
        )
        return result

    except Exception as exc:
        elapsed = time.perf_counter() - t0
        if active_device != "cpu":
            logger.warning(
                "Local whisper inference failed on '%s' after %.2fs (%s). "
                "Switching to CPU/int8 for this and future calls.",
                active_device, elapsed, exc,
            )
            with _whisper_lock:
                _force_cpu_fallback = True
                _whisper_model = None
            cpu_model = _get_model()
            t1 = time.perf_counter()
            result = _run_transcribe_local(cpu_model, audio_path)
            elapsed_cpu = time.perf_counter() - t1
            audio_duration = result["words"][-1]["end"] if result.get("words") else 0
            rtf = elapsed_cpu / audio_duration if audio_duration > 0 else 0
            logger.info(
                "========== LOCAL WHISPER DONE (CPU fallback) ==========\n"
                "  device    : cpu\n"
                "  audio     : %.1fs\n"
                "  wall time : %.2fs\n"
                "  RTF       : %.2f",
                audio_duration, elapsed_cpu, rtf,
            )
            return result
        raise


# ── Warmup probe (local mode only) ───────────────────────────────────────────

def _warmup_probe() -> None:
    """Feed 0.5s of silence through the model at startup to validate CUDA.

    If CUDA fires an error during the dummy inference, _force_cpu_fallback is
    set here - before any real request arrives - so the first user recording
    goes straight to CPU instead of failing then retrying.
    Skipped when device resolves to CPU (nothing to probe).
    """
    import io
    import struct
    import tempfile
    import wave

    global _whisper_model, _force_cpu_fallback

    device, _, _ = _resolve_device_and_model()
    if device == "cpu":
        logger.info("Whisper warmup probe: device=cpu, skipping CUDA check.")
        return

    model = _get_model()

    n_samples = 8_000  # 0.5s @ 16kHz
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16_000)
        wf.writeframes(struct.pack(f"<{n_samples}h", *([0] * n_samples)))
    buf.seek(0)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        tf.write(buf.read())
        tmp_path = tf.name

    try:
        segs, info = model.transcribe(tmp_path, vad_filter=False, word_timestamps=False)
        list(segs)  # force generator evaluation - this is where CUDA fires
        logger.info("Whisper warmup probe: CUDA OK (duration=%.2fs)", info.duration)
    except Exception as exc:
        logger.warning(
            "Whisper warmup probe: CUDA failed (%s). Switching to CPU/int8.", exc
        )
        with _whisper_lock:
            _force_cpu_fallback = True
            _whisper_model = None
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


async def warmup_probe() -> None:
    """Async wrapper - runs _warmup_probe() in the local executor at startup."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_local_executor, _warmup_probe)


# ── Groq transcription ────────────────────────────────────────────────────────

def _sync_transcribe_groq(audio_path: str) -> Dict[str, Any]:
    """Call the Groq Whisper API synchronously - runs in a thread pool executor."""
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
        audio_path, file_size / 1024, settings.groq_whisper_model,
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
        if isinstance(w, dict):
            _word, _start, _end = w.get("word", ""), w.get("start", 0), w.get("end", 0)
        else:
            _word, _start, _end = (
                getattr(w, "word", ""), getattr(w, "start", 0), getattr(w, "end", 0)
            )
        word_list.append({
            "word": str(_word or "").strip(),
            "start": round(float(_start), 3),
            "end": round(float(_end), 3),
            # Groq does not expose per-word confidence scores.
            # probability=1.0 means the mispronounced_words guard skips confidence-based
            # flagging; timing-gap disfluency detection still works.
            "probability": 1.0,
        })

    audio_duration = word_list[-1]["end"] if word_list else 0.0
    logger.info(
        "========== GROQ WHISPER DONE ==========\n"
        "  audio     : %.1fs\n"
        "  wall time : %.2fs\n"
        "  words     : %d",
        audio_duration, elapsed, len(word_list),
    )
    return {"transcript": transcript, "words": word_list}


# ── Dispatcher ────────────────────────────────────────────────────────────────

async def transcribe(audio_path: str) -> Dict[str, Any]:
    """
    Transcribe an audio file asynchronously.

    Mode "local" → faster-whisper; real word.probability; full pronunciation scoring.
    Mode "groq"  → Groq Whisper API; probability=1.0; no pronunciation signal.

    Returns:
        {
            "transcript": str,
            "words": [{"word": str, "start": float, "end": float, "probability": float}]
        }
    """
    settings = get_settings()
    loop = asyncio.get_running_loop()
    if settings.transcription_mode == "local":
        return await loop.run_in_executor(_local_executor, _sync_transcribe_local, audio_path)
    if not settings.transcription_mode:
        logger.warning(
            "TRANSCRIPTION_MODE is not set - defaulting to Groq. "
            "Start the server via run.sh/run.ps1 to select a mode."
        )
    return await loop.run_in_executor(_groq_executor, _sync_transcribe_groq, audio_path)
