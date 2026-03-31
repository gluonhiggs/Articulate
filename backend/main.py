from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api import attempts, dashboard, questions, system, tts
from backend.config import get_settings
from backend.database import init_db
from backend.services import ollama_client
from backend.services.audio import cleanup_old_audio
from backend.services.tts import evict_tts_cache, _ensure_pipeline as _ensure_tts_pipeline
from backend.api.attempts import _get_lt_tool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


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
        import simplemma, lexicalrichness  # noqa: F401
        logger.info("Vocab signal deps OK (simplemma + lexicalrichness).")
    except ImportError as exc:
        logger.warning("Vocab signal deps missing: %s — run `uv sync`", exc)

    from backend.data.oxford import WORD_TO_CEFR
    logger.info("Oxford 5000 loaded: %d words", len(WORD_TO_CEFR))

    logger.info("Transcription: using Groq Whisper API (model=%s).", get_settings().groq_whisper_model)

    logger.info("Pre-loading Kokoro TTS model…")
    await _ensure_tts_pipeline()
    logger.info("Kokoro TTS model ready.")

    logger.info("Initialising LanguageTool grammar checker…")
    loop = asyncio.get_running_loop()
    lt = await loop.run_in_executor(None, _get_lt_tool)
    if lt is not None:
        logger.info("LanguageTool ready (%s).", type(lt).__name__)
    else:
        logger.warning("LanguageTool unavailable — grammar context will be skipped.")

    yield  # Application runs here

    await ollama_client.close_if_initialized()
    logger.info("Shutting down Articulate backend.")


app = FastAPI(
    title="Articulate — IELTS Speaking Practice",
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
# Frontend static files (catch-all — MUST be last)
# ---------------------------------------------------------------------------

_FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

if _FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
    logger.info("Serving frontend from %s", _FRONTEND_DIST)
else:
    logger.warning(
        "Frontend dist not found at %s — run 'bun run build' inside the frontend/ directory.",
        _FRONTEND_DIST,
    )


@app.exception_handler(StarletteHTTPException)
async def spa_fallback(request, exc: StarletteHTTPException):
    """Serve index.html for SPA deep-link navigation (e.g. phone refresh on /practice/part1/questions/5)."""
    if exc.status_code != 404 or request.url.path.startswith("/api/"):
        raise exc
    idx = _FRONTEND_DIST / "index.html"
    if idx.exists():
        return FileResponse(str(idx))
    raise exc
