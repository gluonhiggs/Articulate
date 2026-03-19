from __future__ import annotations

import httpx
from fastapi import APIRouter

from backend.config import get_settings
from backend.schemas import SystemInfoOut

router = APIRouter(prefix="/api/v1/system", tags=["system"])


async def _check_ollama(base_url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(f"{base_url}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


@router.get("/info", response_model=SystemInfoOut)
async def system_info() -> SystemInfoOut:
    settings = get_settings()
    model = settings.ollama_model
    is_low_accuracy = any(tag in model for tag in ("1b", "3b"))
    ollama_reachable = await _check_ollama(settings.ollama_base_url)
    return SystemInfoOut(
        profile=settings.profile,
        whisper_model=settings.whisper_model,
        whisper_device=settings.whisper_device,
        ollama_model=model,
        is_low_accuracy=is_low_accuracy,
        ollama_reachable=ollama_reachable,
    )
