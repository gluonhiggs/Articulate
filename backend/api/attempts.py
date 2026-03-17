from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.constants import BAND_ROLLING_WINDOW
from backend.database import AsyncSessionLocal, get_db
from backend.models import Attempt, DailyActivity, Question, UserStats
from backend.schemas import AttemptOut, AttemptStatusOut, ImproveOut, PronunciationOut, PronunciationWord
from backend.services import audio as audio_service
from backend.services import improve as improve_service
from backend.services import scoring as scoring_service
from backend.services import transcription as transcription_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/attempts", tags=["attempts"])


async def _run_pipeline(attempt_id: int, question_id: int, audio_path: str) -> None:
    """Background task: transcribe → score → update attempt + stats."""
    settings = get_settings()

    async with AsyncSessionLocal() as session:
        try:
            # Fetch the question text and part
            q_result = await session.execute(
                select(Question).where(Question.id == question_id)
            )
            question = q_result.scalar_one_or_none()
            if question is None:
                raise ValueError(f"Question {question_id} not found")

            # ----------------------------------------------------------------
            # 1. Transcription
            # ----------------------------------------------------------------
            transcription_result = await transcription_service.transcribe(audio_path)
            transcript = transcription_result.get("transcript", "")
            words = transcription_result.get("words", [])
            word_timestamps_json = json.dumps(words)

            # Compute duration from last word end time if available
            duration_seconds: int | None = None
            if words:
                last_word = words[-1]
                end_time = last_word.get("end")
                if end_time is not None:
                    duration_seconds = int(end_time)

            # ----------------------------------------------------------------
            # 2. Scoring
            # ----------------------------------------------------------------
            # Build list of flagged words:
            # 1. Low Whisper confidence (possible mispronunciation)
            # 2. Long silence gap before word (disfluency / hesitation)
            disfluent: set[str] = set()
            for i in range(1, len(words)):
                cur_start = words[i].get("start")
                prev_end = words[i - 1].get("end")
                if (
                    cur_start is not None
                    and prev_end is not None
                    and cur_start - prev_end >= settings.gap_threshold
                ):
                    disfluent.add(words[i]["word"].lower())
            flagged_words = [
                w["word"]
                for w in words
                if (
                    isinstance(w.get("probability"), (int, float))
                    and w["probability"] < settings.low_confidence_threshold
                )
                or w["word"].lower() in disfluent
            ]

            scoring_result = await scoring_service.score_attempt(
                question_text=question.text,
                part=question.part,
                transcript=transcript,
                flagged_words=flagged_words,
            )

            fluency = scoring_result.get("fluency")
            vocabulary = scoring_result.get("vocabulary")
            grammar = scoring_result.get("grammar")
            pronunciation = scoring_result.get("pronunciation")
            feedback_text = scoring_result.get("feedback_text")
            error_highlights = json.dumps(
                scoring_result.get("error_highlights", [])
            )
            score = scoring_result.get("score")

            # ----------------------------------------------------------------
            # 3. Update Attempt
            # ----------------------------------------------------------------
            result = await session.execute(
                select(Attempt).where(Attempt.id == attempt_id)
            )
            attempt = result.scalar_one_or_none()
            if attempt is None:
                logger.error("Attempt %d not found during pipeline, aborting.", attempt_id)
                return
            attempt.transcript = transcript
            attempt.word_timestamps = word_timestamps_json
            attempt.duration_seconds = duration_seconds
            attempt.fluency = fluency
            attempt.vocabulary = vocabulary
            attempt.grammar = grammar
            attempt.pronunciation = pronunciation
            attempt.score = score
            attempt.feedback_text = feedback_text
            attempt.error_highlights = error_highlights
            attempt.status = "ready"

            # ----------------------------------------------------------------
            # 4. Update DailyActivity
            # ----------------------------------------------------------------
            today = date.today()
            da_result = await session.execute(
                select(DailyActivity).where(DailyActivity.date == today)
            )
            daily = da_result.scalar_one_or_none()
            if daily is None:
                daily = DailyActivity(date=today, attempts_count=1)
                session.add(daily)
                await session.flush()
            else:
                daily.attempts_count += 1

            # Compute intensity bucket (0-4)
            count = daily.attempts_count
            if count == 0:
                daily.intensity = 0
            elif count == 1:
                daily.intensity = 1
            elif count <= 3:
                daily.intensity = 2
            elif count <= 6:
                daily.intensity = 3
            else:
                daily.intensity = 4

            # ----------------------------------------------------------------
            # 5. Update UserStats streak
            # ----------------------------------------------------------------
            stats_result = await session.execute(
                select(UserStats).where(UserStats.id == 1)
            )
            stats = stats_result.scalar_one_or_none()
            if stats is None:
                stats = UserStats(
                    id=1, current_streak=0, longest_streak=0, total_attempts=0
                )
                session.add(stats)
                await session.flush()

            stats.total_attempts += 1

            # Recalculate streak: single bulk fetch, count consecutive days ending today
            recent = await session.execute(
                select(DailyActivity.date, DailyActivity.attempts_count)
                .order_by(DailyActivity.date.desc())
                .limit(1000)
            )
            rows = recent.all()
            streak = 0
            expected = today
            for row_date, count in rows:
                if row_date == expected and count > 0:
                    streak += 1
                    expected = date.fromordinal(expected.toordinal() - 1)
                else:
                    break

            stats.current_streak = streak
            if streak > stats.longest_streak:
                stats.longest_streak = streak

            # Update estimated_band as rolling average of recent scores
            if score is not None:
                recent_result = await session.execute(
                    select(Attempt.score)
                    .where(Attempt.status == "ready", Attempt.score.isnot(None))
                    .order_by(Attempt.created_at.desc())
                    .limit(BAND_ROLLING_WINDOW)
                )
                recent_scores = [r for r in recent_result.scalars().all()]
                if recent_scores:
                    stats.estimated_band = round(
                        sum(recent_scores) / len(recent_scores) * 2
                    ) / 2

            await session.commit()

        except Exception as exc:
            logger.exception("Pipeline failed for attempt %d: %s", attempt_id, exc)
            try:
                result = await session.execute(
                    select(Attempt).where(Attempt.id == attempt_id)
                )
                attempt = result.scalar_one_or_none()
                if attempt is not None:
                    attempt.status = "failed"
                    await session.commit()
            except Exception:
                logger.exception(
                    "Failed to mark attempt %d as failed", attempt_id
                )


@router.post("/submit", response_model=AttemptStatusOut, status_code=202)
async def submit_attempt(
    background_tasks: BackgroundTasks,
    audio: UploadFile,
    question_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
) -> AttemptStatusOut:
    settings = get_settings()

    # Validate question exists
    q_result = await db.execute(select(Question).where(Question.id == question_id))
    question = q_result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    # Create Attempt row (status=processing, no audio path yet)
    attempt = Attempt(question_id=question_id, status="processing")
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)

    # Save audio file
    try:
        audio_path = await audio_service.save_audio(
            upload_file=audio,
            attempt_id=attempt.id,
            audio_dir=settings.audio_dir,
        )
        attempt.audio_path = audio_path
        await db.commit()
        await db.refresh(attempt)
    except Exception as exc:
        attempt.status = "failed"
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to save audio: {exc}") from exc

    # Launch pipeline in background
    background_tasks.add_task(
        _run_pipeline,
        attempt_id=attempt.id,
        question_id=question_id,
        audio_path=audio_path,
    )

    return AttemptStatusOut(
        id=attempt.id,
        status=attempt.status,
        score=attempt.score,
        fluency=attempt.fluency,
        vocabulary=attempt.vocabulary,
        grammar=attempt.grammar,
        pronunciation=attempt.pronunciation,
        feedback_text=attempt.feedback_text,
        error_highlights=attempt.error_highlights,
        transcript=attempt.transcript,
    )


@router.get("/{attempt_id}/status", response_model=AttemptStatusOut)
async def get_attempt_status(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
) -> AttemptStatusOut:
    result = await db.execute(select(Attempt).where(Attempt.id == attempt_id))
    attempt = result.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return AttemptStatusOut(
        id=attempt.id,
        status=attempt.status,
        score=attempt.score,
        fluency=attempt.fluency,
        vocabulary=attempt.vocabulary,
        grammar=attempt.grammar,
        pronunciation=attempt.pronunciation,
        feedback_text=attempt.feedback_text,
        error_highlights=attempt.error_highlights,
        transcript=attempt.transcript,
    )


@router.get("/history/{question_id}", response_model=List[AttemptOut])
async def get_attempt_history(
    question_id: int,
    db: AsyncSession = Depends(get_db),
) -> List[AttemptOut]:
    # Verify question exists
    q_result = await db.execute(select(Question).where(Question.id == question_id))
    if q_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Question not found")

    result = await db.execute(
        select(Attempt)
        .where(Attempt.question_id == question_id)
        .order_by(Attempt.created_at.desc())
    )
    attempts = result.scalars().all()
    return [AttemptOut.model_validate(a) for a in attempts]


@router.post("/{attempt_id}/improve", response_model=ImproveOut)
async def improve_attempt(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
) -> ImproveOut:
    """Rewrite the attempt's response at one band higher using Ollama."""
    result = await db.execute(select(Attempt).where(Attempt.id == attempt_id))
    attempt = result.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found")

    if attempt.status != "ready" or attempt.transcript is None or attempt.score is None:
        raise HTTPException(
            status_code=400,
            detail="Attempt is not ready or has no transcript/score",
        )

    # Fetch question text
    q_result = await db.execute(
        select(Question).where(Question.id == attempt.question_id)
    )
    question = q_result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    # Compute target band: current score rounded to nearest 0.5 + 1.0, capped at 9.0
    current_band = round(attempt.score * 2) / 2
    target_band = min(current_band + 1.0, 9.0)

    try:
        improved = await improve_service.generate_improvement(
            question_text=question.text,
            transcript=attempt.transcript,
            current_band=current_band,
            target_band=target_band,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ImproveOut(
        improved_text=improved["improved_text"],
        target_band=target_band,
        explanation=improved["explanation"],
    )


@router.get("/{attempt_id}/pronunciation", response_model=PronunciationOut)
async def get_pronunciation(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
) -> PronunciationOut:
    """Return per-word pronunciation confidence from Whisper word timestamps."""
    result = await db.execute(select(Attempt).where(Attempt.id == attempt_id))
    attempt = result.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found")

    if attempt.status != "ready" or attempt.word_timestamps is None:
        raise HTTPException(
            status_code=400,
            detail="Attempt is not ready or has no word timestamps",
        )

    try:
        words_data = json.loads(attempt.word_timestamps)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=500, detail="Invalid word_timestamps data")

    words = []
    for w in words_data:
        confidence = w.get("probability", 0.0)
        if not isinstance(confidence, (int, float)):
            confidence = 0.0
        words.append(
            PronunciationWord(
                word=w.get("word", ""),
                confidence=round(confidence, 3),
                is_flagged=confidence < get_settings().low_confidence_threshold,
            )
        )

    return PronunciationOut(words=words)


@router.get("/{attempt_id}/audio")
async def get_attempt_audio(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Stream the recorded audio for a completed attempt."""
    result = await db.execute(select(Attempt).where(Attempt.id == attempt_id))
    attempt = result.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found")

    if not attempt.audio_path:
        raise HTTPException(status_code=404, detail="No audio recorded for this attempt")

    try:
        return FileResponse(attempt.audio_path, media_type="audio/webm")
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Audio file no longer available (may have been cleaned up)",
        )
