from __future__ import annotations

from fastapi import APIRouter

from backend.config import get_settings
from backend.schemas import SystemInfoOut

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/info", response_model=SystemInfoOut)
async def system_info() -> SystemInfoOut:
    settings = get_settings()
    model = settings.ollama_model
    is_low_accuracy = any(tag in model for tag in ("1b", "3b"))
    return SystemInfoOut(
        profile=settings.profile,
        whisper_model=settings.whisper_model,
        whisper_device=settings.whisper_device,
        ollama_model=model,
        is_low_accuracy=is_low_accuracy,
    )
