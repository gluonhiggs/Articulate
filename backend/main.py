from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api import attempts, dashboard, questions, system
from backend.config import get_settings
from backend.database import init_db
from backend.services.audio import cleanup_old_audio

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

    yield  # Application runs here

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
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",
    ],
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

# ---------------------------------------------------------------------------
# Frontend static files (catch-all — MUST be last)
# ---------------------------------------------------------------------------

_FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

if _FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
    logger.info("Serving frontend from %s", _FRONTEND_DIST)
else:
    logger.warning(
        "Frontend dist not found at %s — run 'npm run build' inside the frontend/ directory.",
        _FRONTEND_DIST,
    )
