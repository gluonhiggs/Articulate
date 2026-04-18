from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api import attempts, dashboard, questions, system, tts
from backend.config import get_settings
from backend.database import init_db
from backend.services import llm_client
from backend.services.audio import cleanup_old_audio
from backend.services.transcription import is_faster_whisper_installed
from backend.services.tts import evict_tts_cache, _ensure_pipeline as _ensure_tts_pipeline
from backend.api.attempts import _get_lt_tool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _should_downgrade_to_groq(mode: str | None, fw_installed: bool) -> bool:
    """Capability gate: saved mode=local + missing fw → run as groq this session.

    Pure predicate so the invariant can be unit-tested without booting the app.
    """
    return mode == "local" and not fw_installed


def _prompt_mode_selection() -> None:
    """Interactive terminal prompt for transcription mode.

    Only runs when TRANSCRIPTION_MODE is unset in .env.
    For Mode 1 with no GPU, asks the user to confirm CPU slowness.
    Writes the chosen mode to data/mode and updates os.environ so
    get_settings() returns the new value after cache_clear().

    NOTE: Persistence (saved to data/mode) persists across server restarts.
    The chosen mode is restored during lifespan startup before the prompt runs.
    """
    settings = get_settings()
    if settings.transcription_mode in ("groq", "local"):
        return  # already configured - skip prompt

    # Non-interactive mode (Electron desktop app): skip terminal prompt.
    # Default to local when faster-whisper is bundled (the installer case) so
    # new users get full pronunciation scoring out-of-box; otherwise default
    # to groq so source installs without the local-transcription group still
    # boot cleanly. Users can flip modes from the UI switcher either way.
    if os.environ.get("ARTICULATE_NO_INTERACTIVE") == "1":
        from backend.config import write_mode_file
        default_mode = "local" if is_faster_whisper_installed() else "groq"
        write_mode_file(default_mode)
        os.environ["TRANSCRIPTION_MODE"] = default_mode
        get_settings.cache_clear()
        return

    from backend.services.transcription import detect_gpu
    has_gpu = detect_gpu()

    print("\n" + "=" * 60)
    print("Transcription mode - choose once (saved to data/mode):\n")
    print("  [1] Local  - faster-whisper, full pronunciation scoring")
    if has_gpu:
        print("       GPU detected: large-v3-turbo (fast + accurate)")
    else:
        print("       No GPU: small model on CPU (~40-60s per answer)")
    print()
    print("  [2] Cloud  - Groq API, ~2-3s per answer")
    print("       Note: pronunciation reflects fluency only")
    print("             (word-level analysis unavailable in cloud mode)")
    print("=" * 60)

    while True:
        try:
            choice = input("Choose [1/2]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nDefaulting to cloud mode.")
            choice = "2"
            break
        if choice in ("1", "2"):
            break
        print("Enter 1 or 2.")

    mode = "local" if choice == "1" else "groq"

    # Warn and confirm if local mode selected but no GPU available
    if mode == "local" and not has_gpu:
        print()
        print("! No GPU detected. Expect ~40-60s transcription per answer on CPU.")
        while True:
            try:
                confirm = input("Continue with local CPU mode? [y/N]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                confirm = "n"
                break
            if confirm in ("y", "yes", "n", "no", ""):
                break
            print("Enter y or n.")
        if confirm not in ("y", "yes"):
            print("Switching to cloud mode (Groq).")
            mode = "groq"

    # Persist to data/mode (never modifies .env)
    from backend.config import write_mode_file
    write_mode_file(mode)

    # Update the running process so lifespan reads the chosen mode
    os.environ["TRANSCRIPTION_MODE"] = mode
    get_settings.cache_clear()

    print(f"\nSaved. Starting in {'local' if mode == 'local' else 'cloud (Groq)'} mode.\n")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown hooks."""
    settings = get_settings()

    logger.info("Initialising database…")
    await init_db()
    logger.info("Database ready.")

    logger.info("Running audio cleanup…")
    await cleanup_old_audio(
        audio_dir=settings.audio_dir,
        retention_days=settings.audio_retention_days,
        max_size_mb=settings.max_audio_size_mb,
    )
    logger.info("Audio cleanup done.")

    logger.info("Evicting TTS cache…")
    evict_tts_cache(settings.tts_cache_dir, settings.tts_cache_max_mb)
    logger.info("TTS cache eviction done.")

    logger.info("Verifying vocab signal dependencies…")
    try:
        import simplemma  # noqa: F401
        logger.info("Vocab signal deps OK (simplemma).")
    except ImportError as exc:
        logger.warning("Vocab signal deps missing: %s - run `uv sync`", exc)

    from backend.data.oxford import WORD_TO_CEFR
    logger.info("Oxford 5000 loaded: %d words", len(WORD_TO_CEFR))

    # ── Restore last-used transcription mode from data/mode ──────────────────
    from backend.config import get_mode_file, write_mode_file
    _mode_file = get_mode_file()
    if _mode_file.exists():
        _saved_mode = _mode_file.read_text(encoding="utf-8").strip()
        if _saved_mode in ("groq", "local"):
            os.environ["TRANSCRIPTION_MODE"] = _saved_mode
            get_settings.cache_clear()
            logger.info("Transcription mode restored from data/mode: %s", _saved_mode)

    # Mode selection: prompt user if TRANSCRIPTION_MODE not set in .env
    _prompt_mode_selection()
    settings = get_settings()  # re-read after potential mode change

    # Capability gate: the shipped desktop bundle excludes faster-whisper (~3 GB
    # of CUDA weights). If the user's saved preference is "local" but the
    # runtime lacks faster-whisper, fall back to groq *in-memory only*. We do
    # not overwrite data/mode — the preference survives for environments where
    # local is supported (e.g. a source install with `uv sync --group local-transcription`).
    if _should_downgrade_to_groq(settings.transcription_mode, is_faster_whisper_installed()):
        logger.warning(
            "TRANSCRIPTION_MODE=local requested but faster-whisper is not available "
            "in this runtime (likely a packaged desktop build). Falling back to groq "
            "for this session. Saved preference is preserved."
        )
        os.environ["TRANSCRIPTION_MODE"] = "groq"
        get_settings.cache_clear()
        settings = get_settings()

    if settings.transcription_mode == "local":
        logger.info("Transcription: Mode 1 - local faster-whisper.")
        try:
            from backend.services.transcription import _get_model as _get_whisper_model, warmup_probe as _warmup_probe, _local_executor as _whisper_local_executor
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(_whisper_local_executor, _get_whisper_model)
            logger.info("faster-whisper model loaded - running CUDA warmup probe…")
            await _warmup_probe()
            logger.info("faster-whisper ready (device validated).")
        except ImportError:
            # Missing dep → hard fail. Signals a broken source install (dev forgot
            # `uv sync --group local-transcription`) or a build regression where
            # the packaged bundle is missing fw. The capability gate above is the
            # intended in-memory fallback for that second case, so reaching here
            # means the gate mis-routed — don't mask it.
            logger.critical(
                "faster-whisper is not installed but TRANSCRIPTION_MODE=local.\n"
                "  Install: uv sync --group local-transcription\n"
                "  Or set TRANSCRIPTION_MODE=groq in .env and restart."
            )
            raise SystemExit(1)
        except Exception as exc:
            # Runtime failure loading fw or downloading Whisper weights (HF
            # network error, captive proxy, CUDA driver mismatch not caught by
            # _force_cpu_fallback). Mirror the capability gate: degrade to groq
            # in-memory without overwriting the saved preference.
            logger.error(
                "faster-whisper init failed (%s). Falling back to groq for this session; "
                "saved preference is preserved.",
                exc,
            )
            os.environ["TRANSCRIPTION_MODE"] = "groq"
            get_settings.cache_clear()
            settings = get_settings()
            logger.info(
                "Transcription: Mode 2 - Groq API (model=%s) [runtime fallback].",
                settings.groq_whisper_model,
            )
    else:
        logger.info(
            "Transcription: Mode 2 - Groq API (model=%s). "
            "Pronunciation scoring reflects fluency only (no word-level analysis).",
            settings.groq_whisper_model,
        )

    logger.info("Pre-loading Kokoro TTS model…")
    await _ensure_tts_pipeline()
    logger.info("Kokoro TTS model ready.")

    logger.info("Initialising LanguageTool grammar checker…")
    loop = asyncio.get_running_loop()
    try:
        lt = await asyncio.wait_for(
            loop.run_in_executor(None, _get_lt_tool),
            timeout=30.0,
        )
        if lt is not None:
            logger.info("LanguageTool ready (%s).", type(lt).__name__)
        else:
            logger.warning("LanguageTool unavailable - grammar context will be skipped.")
    except asyncio.TimeoutError:
        logger.warning(
            "LanguageTool timed out after 30s (Java may be blocked by firewall). "
            "Grammar context will be skipped."
        )

    yield  # Application runs here

    await llm_client.close_if_initialized()
    logger.info("Shutting down Articulate backend.")


app = FastAPI(
    title="Articulate - IELTS Speaking Practice",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# API Routers  (must be registered BEFORE the static files catch-all)
# ---------------------------------------------------------------------------

app.include_router(questions.router)
app.include_router(attempts.router)
app.include_router(dashboard.router)
app.include_router(system.router)
app.include_router(tts.router)

# ---------------------------------------------------------------------------
# Frontend static files (catch-all - MUST be last)
# ---------------------------------------------------------------------------

import sys as _sys
_MEIPASS = getattr(_sys, "_MEIPASS", None)
_FRONTEND_DIST = Path(_MEIPASS) / "frontend" / "dist" if _MEIPASS else Path(__file__).parent.parent / "frontend" / "dist"

if _FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
    logger.info("Serving frontend from %s", _FRONTEND_DIST)
else:
    logger.warning(
        "Frontend dist not found at %s - run 'bun run build' inside the frontend/ directory.",
        _FRONTEND_DIST,
    )


@app.exception_handler(StarletteHTTPException)
async def spa_fallback(request, exc: StarletteHTTPException):
    """Serve index.html for SPA deep-link navigation."""
    if exc.status_code != 404 or request.url.path.startswith("/api/"):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    idx = _FRONTEND_DIST / "index.html"
    if idx.exists():
        return FileResponse(str(idx))
    return JSONResponse(status_code=404, content={"detail": exc.detail})
