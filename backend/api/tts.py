from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database import get_db
from backend.models import Question
from backend.services.tts import get_or_generate_tts

router = APIRouter(prefix="/api/v1/tts", tags=["tts"])


@router.get("/pronounce")
async def pronounce_word(
    text: str = Query(..., max_length=100, description="Word or short phrase to pronounce"),
):
    """Generate TTS for a single word or short phrase, cached by text hash."""
    text = text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text must not be empty")

    settings = get_settings()
    text_hash = hashlib.sha256(text.lower().encode("utf-8")).hexdigest()[:16]
    # Use a stable fake question_id derived from text hash to reuse the TTS cache logic
    # We prefix with "pronounce_" to avoid collisions with real question IDs
    cache_key = f"pronounce_{text_hash}"

    wav_path = await get_or_generate_tts(
        question_id=cache_key,
        text=text,
        cache_dir=settings.tts_cache_dir,
        voice=settings.tts_voice,
    )

    return FileResponse(
        path=str(wav_path),
        media_type="audio/wav",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("/{question_id}")
async def tts_for_question(
    question_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Question).where(Question.id == question_id))
    question = result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    settings = get_settings()
    wav_path = await get_or_generate_tts(
        question_id=question.id,
        text=question.text,
        cache_dir=settings.tts_cache_dir,
        voice=settings.tts_voice,
    )

    return FileResponse(
        path=str(wav_path),
        media_type="audio/wav",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
