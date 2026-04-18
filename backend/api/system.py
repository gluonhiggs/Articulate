from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys

import httpx
from fastapi import APIRouter, HTTPException

from backend.config import get_active_model, get_mode_file, get_settings, set_runtime_model, write_mode_file
from backend.schemas import SetModelRequest, SetTranscriptionModeRequest, SystemInfoOut
from backend.services.transcription import is_faster_whisper_installed

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/system", tags=["system"])

# ── Background-operation state ────────────────────────────────────────────────
# op_status: "" | "installing" | "loading" | "failed"
# All mutations happen on the asyncio event loop thread - no lock needed.
_op_status: str = ""
_background_tasks: set = set()


def _set_op_status(status: str) -> None:
    global _op_status
    _op_status = status


def _get_op_status() -> str:
    return _op_status


# ── LLM reachability check ────────────────────────────────────────────────────

async def _check_llm_reachable(base_url: str, api_key: str) -> bool:
    try:
        if api_key:
            return True
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(base_url)
            return r.status_code < 500
    except Exception:
        return False


# ── System info ───────────────────────────────────────────────────────────────

@router.get("/info", response_model=SystemInfoOut)
async def system_info() -> SystemInfoOut:
    settings = get_settings()
    model = get_active_model()
    is_low_accuracy = any(tag in model for tag in ("1b", "3b", "1b-it", "3b-it"))
    llm_reachable = await _check_llm_reachable(settings.llm_base_url, settings.llm_api_key)

    # Whisper info depends on active mode
    if settings.transcription_mode == "local":
        try:
            from backend.services.transcription import _resolve_device_and_model
            device, _, model_size = _resolve_device_and_model()
            whisper_model = model_size
            whisper_device = device
        except Exception:
            whisper_model = "local"
            whisper_device = "unknown"
    else:
        whisper_model = settings.groq_whisper_model
        whisper_device = "groq-api"

    return SystemInfoOut(
        profile=settings.profile,
        whisper_model=whisper_model,
        whisper_device=whisper_device,
        llm_model=model,
        is_low_accuracy=is_low_accuracy,
        llm_reachable=llm_reachable,
        transcription_mode=settings.transcription_mode or "groq",
        faster_whisper_installed=is_faster_whisper_installed(),
        op_status=_get_op_status(),
        is_desktop=getattr(sys, "frozen", False),
    )


# ── LLM model switch ──────────────────────────────────────────────────────────

@router.patch("/model", response_model=SystemInfoOut)
async def update_model(body: SetModelRequest) -> SystemInfoOut:
    set_runtime_model(body.model.strip())
    return await system_info()


# ── Transcription mode switch ─────────────────────────────────────────────────

async def _install_faster_whisper() -> None:
    """Run `uv sync --group local-transcription` in a thread; update op_status."""
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _run_uv_sync)
        logger.info("faster-whisper installed successfully.")
        _set_op_status("")
    except Exception as exc:
        logger.error("faster-whisper install failed: %s", exc)
        _set_op_status("failed")


def _run_uv_sync() -> None:
    import sys
    if getattr(sys, "frozen", False):
        raise RuntimeError("Local transcription install is not available in the desktop app.")
    result = subprocess.run(
        ["uv", "sync", "--group", "local-transcription"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or "uv sync failed")


async def _load_model_and_switch() -> None:
    """Load the faster-whisper model + warmup, then switch mode to local."""
    try:
        from backend.services.transcription import (
            _get_model,
            _local_executor,
            warmup_probe,
        )
        loop = asyncio.get_running_loop()
        logger.info("Loading faster-whisper model in background...")
        await loop.run_in_executor(_local_executor, _get_model)
        logger.info("faster-whisper model loaded -- running warmup probe...")
        await warmup_probe()
        # Guard: if op_status was cleared by a concurrent groq switch, abort
        if _get_op_status() != "loading":
            logger.info("Mode switched away during load -- aborting local activation.")
            return
        logger.info("faster-whisper ready. Switching mode to local.")
        write_mode_file("local")
        os.environ["TRANSCRIPTION_MODE"] = "local"
        get_settings.cache_clear()
        _set_op_status("")
    except Exception as exc:
        logger.error("Failed to load faster-whisper model: %s", exc)
        _set_op_status("failed")


@router.patch("/transcription-mode", response_model=SystemInfoOut)
async def update_transcription_mode(body: SetTranscriptionModeRequest) -> SystemInfoOut:
    mode = body.mode.strip().lower()
    if mode not in ("groq", "local"):
        raise HTTPException(status_code=422, detail="mode must be 'groq' or 'local'")

    current_op = _get_op_status()

    if mode == "groq":
        # Synchronous -- fast. Unload model, switch immediately.
        from backend.services.transcription import unload_model
        unload_model()
        write_mode_file("groq")
        os.environ["TRANSCRIPTION_MODE"] = "groq"
        get_settings.cache_clear()
        _set_op_status("")
        return await system_info()

    # mode == "local"
    # Desktop installer bundles faster-whisper, so the normal path has it
    # available. If a frozen build somehow lacks it (build regression), fail
    # fast with a 400 — pip-installing into a PyInstaller bundle can't work
    # because imports resolve against frozen bytecode, not site-packages.
    if getattr(sys, "frozen", False) and not is_faster_whisper_installed():
        raise HTTPException(
            status_code=400,
            detail=(
                "Local transcription is not available in this build. "
                "Reinstall the latest Articulate release or run from source with "
                "`uv sync --group local-transcription`."
            ),
        )

    if current_op in ("installing", "loading"):
        # Already in progress -- return current state, do not double-launch
        return await system_info()

    if not is_faster_whisper_installed():
        _set_op_status("installing")
        _task = asyncio.create_task(_install_faster_whisper())
        _background_tasks.add(_task)
        _task.add_done_callback(_background_tasks.discard)
    else:
        _set_op_status("loading")
        _task = asyncio.create_task(_load_model_and_switch())
        _background_tasks.add(_task)
        _task.add_done_callback(_background_tasks.discard)

    return await system_info()
