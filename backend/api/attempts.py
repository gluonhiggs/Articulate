from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.constants import BAND_ROLLING_WINDOW
from backend.data.cefr_wordlist import CEFR
from backend.database import AsyncSessionLocal, get_db
from backend.models import Attempt, DailyActivity, Question, UserStats
from backend.schemas import AttemptOut, AttemptStatusOut, ImproveOut, PronunciationOut, PronunciationWord
from backend.services import audio as audio_service
from pathlib import Path
from backend.services.audio import EXT_TO_MIME
from backend.services import improve as improve_service
from backend.services import scoring as scoring_service
from backend.services import transcription as transcription_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/attempts", tags=["attempts"])

# ── LanguageTool singleton (optional — requires Java) ────────────────────────

_lt_tool = None
_lt_tool_init_attempted = False


def _get_lt_tool():
    global _lt_tool, _lt_tool_init_attempted
    if _lt_tool_init_attempted:
        return _lt_tool
    _lt_tool_init_attempted = True
    try:
        import language_tool_python  # type: ignore[import]
        _lt_tool = language_tool_python.LanguageTool('en-US')
        logger.info("LanguageTool initialized successfully")
    except Exception as exc:
        logger.warning("LanguageTool unavailable (Java required): %s", exc)
        _lt_tool = None
    return _lt_tool


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

            # Emit 'transcribing' status
            t_result = await session.execute(select(Attempt).where(Attempt.id == attempt_id))
            attempt_pre = t_result.scalar_one_or_none()
            if attempt_pre is not None:
                attempt_pre.status = "transcribing"
                await session.commit()
                logger.info("Pipeline %d: transcribing", attempt_id)

            # ----------------------------------------------------------------
            # 1. Transcription
            # ----------------------------------------------------------------
            try:
                transcription_result = await asyncio.wait_for(
                    transcription_service.transcribe(audio_path),
                    timeout=120.0,
                )
            except asyncio.TimeoutError:
                logger.error("Pipeline %d: transcription timed out after 120s", attempt_id)
                t2 = await session.execute(select(Attempt).where(Attempt.id == attempt_id))
                a = t2.scalar_one_or_none()
                if a is not None:
                    a.status = "failed:transcription"
                    await session.commit()
                return
            except Exception as exc:
                logger.exception("Pipeline %d: transcription failed: %s", attempt_id, exc)
                t2 = await session.execute(select(Attempt).where(Attempt.id == attempt_id))
                a = t2.scalar_one_or_none()
                if a is not None:
                    a.status = "failed:transcription"
                    await session.commit()
                    logger.info("Pipeline %d: failed:transcription", attempt_id)
                return

            transcript = transcription_result.get("transcript", "")
            words = transcription_result.get("words", [])

            # Guard: empty or silent audio
            if not transcript or not transcript.strip():
                file_size = os.path.getsize(audio_path) if os.path.exists(audio_path) else -1
                logger.warning(
                    "Pipeline %d: empty transcript — audio=%s (%.1f KB)",
                    attempt_id, audio_path, file_size / 1024,
                )
                t2 = await session.execute(select(Attempt).where(Attempt.id == attempt_id))
                a = t2.scalar_one_or_none()
                if a is not None:
                    a.status = "failed:empty_audio"
                    await session.commit()
                    logger.info("Pipeline %d: failed:empty_audio", attempt_id)
                return
            word_timestamps_json = json.dumps(words)

            # Compute duration from last word end time if available
            duration_seconds: int | None = None
            if words:
                last_word = words[-1]
                end_time = last_word.get("end")
                if end_time is not None:
                    duration_seconds = int(end_time)

            # ----------------------------------------------------------------
            # 2. Scoring signals
            # ----------------------------------------------------------------

            # Signal 1: Fluency gap rate + disfluent word set (single pass)
            gap_count = 0
            disfluent: set[str] = set()
            for i in range(1, len(words)):
                cur_start = words[i].get("start")
                prev_end = words[i - 1].get("end")
                if (
                    cur_start is not None
                    and prev_end is not None
                    and cur_start - prev_end >= settings.gap_threshold
                ):
                    gap_count += 1
                    disfluent.add(words[i]["word"].lower())
            total_words = len(words)
            gaps_per_100 = round(gap_count / total_words * 100, 1) if total_words > 0 else 0.0
            fluency_context = (
                f"{gap_count} long pause(s) in {total_words} words ({gaps_per_100}/100 words)"
            )

            # Signal 2: CEFR vocabulary distribution
            vocab_signal = "insufficient vocabulary data"
            try:
                content_words = [
                    w["word"].lower().strip(".,!?;:'\"")
                    for w in words
                    if len(w.get("word", "")) > 2
                ]
                known = [w for w in content_words if w in CEFR]
                high_level = sum(1 for w in known if CEFR[w] in ("B2", "C1"))
                if known:
                    pct = round(high_level / len(known) * 100)
                    vocab_signal = f"{high_level}/{len(known)} known words are B2+ ({pct}%)"
            except Exception as exc:
                logger.warning("CEFR vocab signal failed: %s", exc)

            # Signal 3: Grammar checker (LanguageTool — requires Java)
            grammar_context = "grammar checker unavailable"
            if transcript and transcript.strip():
                try:
                    lt = _get_lt_tool()
                    if lt is not None:
                        loop = asyncio.get_event_loop()
                        matches = await loop.run_in_executor(None, lt.check, transcript)
                        grammar_errors = [
                            f"{m.ruleId}: '{transcript[m.offset:m.offset + m.errorLength]}'"
                            f" → {list(m.replacements[:2])}"
                            for m in matches[:8]
                        ]
                        grammar_context = (
                            "; ".join(grammar_errors)
                            if grammar_errors
                            else "no grammar errors detected"
                        )
                except Exception as exc:
                    logger.warning("Grammar check failed: %s", exc)

            # ----------------------------------------------------------------
            # 3. Flagged words for pronunciation
            # ----------------------------------------------------------------
            flagged_words = [
                w["word"]
                for w in words
                if (
                    isinstance(w.get("probability"), (int, float))
                    and w["probability"] < settings.low_confidence_threshold
                )
                or w["word"].lower() in disfluent
            ]

            # ----------------------------------------------------------------
            # 4. Score
            # ----------------------------------------------------------------
            # Emit 'scoring' status before calling Ollama
            s_result = await session.execute(select(Attempt).where(Attempt.id == attempt_id))
            attempt_scoring = s_result.scalar_one_or_none()
            if attempt_scoring is not None:
                attempt_scoring.status = "scoring"
                await session.commit()
                logger.info("Pipeline %d: scoring", attempt_id)

            try:
                scoring_result = await scoring_service.score_attempt(
                    question_text=question.text,
                    part=question.part,
                    transcript=transcript,
                    flagged_words=flagged_words,
                    fluency_context=fluency_context,
                    vocab_signal=vocab_signal,
                    grammar_context=grammar_context,
                )
            except Exception as exc:
                logger.exception("Pipeline %d: scoring failed: %s", attempt_id, exc)
                s2 = await session.execute(select(Attempt).where(Attempt.id == attempt_id))
                a = s2.scalar_one_or_none()
                if a is not None:
                    a.status = "failed:scoring"
                    await session.commit()
                    logger.info("Pipeline %d: failed:scoring", attempt_id)
                return

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
            # 5. Update Attempt
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
            logger.info("Pipeline %d: ready", attempt_id)

            # ----------------------------------------------------------------
            # 6. Update DailyActivity
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
            # 7. Update UserStats streak
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
                    logger.info("Pipeline %d: failed (unknown)", attempt_id)
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


_STALE_PROCESSING_THRESHOLD = timedelta(minutes=10)


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

    # Mark any attempt stuck in 'processing' for longer than the threshold as
    # 'failed' so they don't show as infinite spinners in the UI.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    stale_found = False
    for attempt in attempts:
        if (
            attempt.status in ("processing", "transcribing", "scoring")
            and attempt.created_at is not None
            and now - attempt.created_at > _STALE_PROCESSING_THRESHOLD
        ):
            attempt.status = "failed"
            stale_found = True
            logger.warning("Marked stale attempt %d as failed (created_at=%s)", attempt.id, attempt.created_at)
    if stale_found:
        await db.commit()

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
        media_type = EXT_TO_MIME.get(Path(attempt.audio_path).suffix, "audio/webm")
        return FileResponse(attempt.audio_path, media_type=media_type)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Audio file no longer available (may have been cleaned up)",
        )
