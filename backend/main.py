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
from backend.services.transcription import _get_model as _get_whisper_model, warmup_probe as _warmup_probe
from backend.services.tts import evict_tts_cache

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

    logger.info("Pre-loading Whisper model…")
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _get_whisper_model)
    logger.info("Whisper model loaded — running CUDA warmup probe…")
    await _warmup_probe()
    logger.info("Whisper ready (device validated).")

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
