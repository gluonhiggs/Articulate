from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database import get_db
from backend.models import (
    InterviewAnswer,
    InterviewGlossaryTerm,
    InterviewKeyPoint,
    InterviewMisconception,
    InterviewPack,
    InterviewQuestion,
    InterviewSource,
)
from backend.schemas import (
    InterviewAnswerOut,
    InterviewDraftRequest,
    InterviewGlossaryTermIn,
    InterviewGlossaryTermOut,
    InterviewGradeRequest,
    InterviewPackCreate,
    InterviewPackDetailOut,
    InterviewPackSummaryOut,
    InterviewPackUpdate,
    InterviewQuestionOut,
    InterviewQuestionUpsert,
    InterviewSourceIn,
    InterviewSourceOut,
)
from backend.services import audio as audio_service
from backend.services import interview_grading, interview_packs
from backend.services.audio import EXT_TO_MIME
from backend.services.interview_packs import InterviewPackError, utc_now
from backend.services.llm_client import LLMRateLimitError
from backend.services.tts import get_or_generate_tts

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/interview", tags=["interview"])

DELETED = {"deleted": True}


async def _pack_or_404(db: AsyncSession, pack_id: int) -> InterviewPack:
    pack = await interview_packs.load_pack(db, pack_id)
    if pack is None:
        raise HTTPException(status_code=404, detail="Interview pack not found")
    return pack


async def _detail(db: AsyncSession, pack_id: int) -> InterviewPackDetailOut:
    detail = await interview_packs.pack_detail(db, pack_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Interview pack not found")
    return detail


async def _question_out(db: AsyncSession, question_id: int) -> InterviewQuestionOut:
    out = await interview_packs.question_out(db, question_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return out


async def _question_or_404(db: AsyncSession, question_id: int) -> InterviewQuestion:
    question = await db.get(InterviewQuestion, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return question


async def _answer_or_404(db: AsyncSession, answer_id: int) -> InterviewAnswer:
    answer = await db.get(InterviewAnswer, answer_id)
    if answer is None:
        raise HTTPException(status_code=404, detail="Answer not found")
    return answer


def _json_download(payload: object, filename: str) -> Response:
    return Response(
        content=json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/packs", response_model=List[InterviewPackSummaryOut])
async def list_packs(db: AsyncSession = Depends(get_db)) -> List[InterviewPackSummaryOut]:
    return await interview_packs.pack_summaries(db)


@router.post("/packs", response_model=InterviewPackDetailOut, status_code=201)
async def create_pack(body: InterviewPackCreate, db: AsyncSession = Depends(get_db)) -> InterviewPackDetailOut:
    pack = InterviewPack(
        uid=interview_packs.new_uid(),
        title=body.title.strip(),
        role=body.role,
        level=body.level,
        author=body.author.strip(),
        job_description=body.job_description,
    )
    db.add(pack)
    await db.commit()
    return await _detail(db, pack.id)


@router.post("/packs/import", response_model=InterviewPackDetailOut)
async def import_pack(file: UploadFile, db: AsyncSession = Depends(get_db)) -> InterviewPackDetailOut:
    data = await file.read(interview_packs.MAX_PACK_FILE_BYTES + 1)
    try:
        pack_file = interview_packs.parse_pack_bytes(data)
    except InterviewPackError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    pack_id = await interview_packs.import_pack(db, pack_file)
    await db.commit()
    return await _detail(db, pack_id)


@router.get("/packs/{pack_id}", response_model=InterviewPackDetailOut)
async def get_pack(pack_id: int, db: AsyncSession = Depends(get_db)) -> InterviewPackDetailOut:
    return await _detail(db, pack_id)


@router.put("/packs/{pack_id}", response_model=InterviewPackDetailOut)
async def update_pack(
    pack_id: int, body: InterviewPackUpdate, db: AsyncSession = Depends(get_db)
) -> InterviewPackDetailOut:
    pack = await _pack_or_404(db, pack_id)
    pack.title = body.title.strip()
    pack.role = body.role
    pack.level = body.level
    pack.author = body.author.strip()
    pack.job_description = body.job_description
    pack.version += 1
    interview_packs.touch(pack)
    await db.commit()
    return await _detail(db, pack_id)


@router.delete("/packs/{pack_id}")
async def delete_pack(pack_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    pack = await _pack_or_404(db, pack_id)
    question_ids = [q.id for q in pack.questions]
    audio_paths: list[str] = []
    if question_ids:
        paths = await db.execute(
            select(InterviewAnswer.audio_path).where(
                InterviewAnswer.question_id.in_(question_ids), InterviewAnswer.audio_path.is_not(None)
            )
        )
        audio_paths = list(paths.scalars().all())
        await db.execute(delete(InterviewAnswer).where(InterviewAnswer.question_id.in_(question_ids)))
        await db.execute(delete(InterviewKeyPoint).where(InterviewKeyPoint.question_id.in_(question_ids)))
        await db.execute(delete(InterviewMisconception).where(InterviewMisconception.question_id.in_(question_ids)))
        await db.execute(delete(InterviewQuestion).where(InterviewQuestion.id.in_(question_ids)))
    await db.execute(delete(InterviewGlossaryTerm).where(InterviewGlossaryTerm.pack_id == pack_id))
    await db.execute(delete(InterviewSource).where(InterviewSource.pack_id == pack_id))
    await db.execute(delete(InterviewPack).where(InterviewPack.id == pack_id))
    await db.commit()

    for audio_path in audio_paths:
        try:
            Path(audio_path).unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Could not delete interview audio %s: %s", audio_path, exc)
    return DELETED


@router.get("/packs/{pack_id}/export")
async def export_pack(pack_id: int, db: AsyncSession = Depends(get_db)) -> Response:
    pack = await _pack_or_404(db, pack_id)
    pack_file = interview_packs.export_pack(pack)
    filename = f"{interview_packs.pack_slug(pack.title)}-v{pack.version}.json"
    return _json_download(pack_file.model_dump(mode="json"), filename)


@router.get("/packs/{pack_id}/report")
async def export_report(pack_id: int, db: AsyncSession = Depends(get_db)) -> Response:
    pack = await _pack_or_404(db, pack_id)
    report = await interview_packs.build_report(db, pack)
    filename = f"{interview_packs.pack_slug(pack.title)}-report-{utc_now():%Y%m%d}.json"
    return _json_download(report, filename)


@router.put("/packs/{pack_id}/glossary", response_model=List[InterviewGlossaryTermOut])
async def replace_glossary(
    pack_id: int, body: List[InterviewGlossaryTermIn], db: AsyncSession = Depends(get_db)
) -> List[InterviewGlossaryTermOut]:
    pack = await _pack_or_404(db, pack_id)
    pack.glossary_terms.clear()
    for item in body:
        pack.glossary_terms.append(
            InterviewGlossaryTerm(term=item.term.strip(), aliases=interview_packs.clean_aliases(item.aliases))
        )
    interview_packs.touch(pack)
    await db.commit()
    return interview_packs.glossary_out(pack.glossary_terms)


@router.post("/packs/{pack_id}/sources", response_model=InterviewSourceOut, status_code=201)
async def add_source(pack_id: int, body: InterviewSourceIn, db: AsyncSession = Depends(get_db)) -> InterviewSourceOut:
    pack = await _pack_or_404(db, pack_id)
    source = InterviewSource(
        uid=interview_packs.new_uid(), title=body.title.strip(), url=body.url, content=body.content
    )
    pack.sources.append(source)
    await interview_packs.refresh_quote_verification(pack)
    interview_packs.touch(pack)
    await db.commit()
    return interview_packs.source_out(source)


@router.delete("/packs/{pack_id}/sources/{source_id}")
async def delete_source(pack_id: int, source_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    pack = await _pack_or_404(db, pack_id)
    source = next((s for s in pack.sources if s.id == source_id), None)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    pack.sources.remove(source)
    await interview_packs.refresh_quote_verification(pack)
    interview_packs.touch(pack)
    await db.commit()
    return DELETED


@router.post("/packs/{pack_id}/draft", response_model=List[InterviewQuestionOut])
async def draft_questions(
    pack_id: int, body: InterviewDraftRequest, db: AsyncSession = Depends(get_db)
) -> List[InterviewQuestionOut]:
    pack = await _pack_or_404(db, pack_id)
    try:
        question_ids = await interview_packs.draft_questions(db, pack, body)
    except InterviewPackError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMRateLimitError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=429,
            detail="The Gemini drafter's free-tier quota is reached for now. Please try again later.",
        ) from exc
    except RuntimeError as exc:
        await db.rollback()
        raise HTTPException(status_code=502, detail=f"Drafting failed: {exc}") from exc
    await db.commit()
    return [await _question_out(db, question_id) for question_id in question_ids]


@router.post("/packs/{pack_id}/questions", response_model=InterviewQuestionOut, status_code=201)
async def create_question(
    pack_id: int, body: InterviewQuestionUpsert, db: AsyncSession = Depends(get_db)
) -> InterviewQuestionOut:
    pack = await _pack_or_404(db, pack_id)
    [question_id] = await interview_packs.create_questions(db, pack, [body])
    await db.commit()
    return await _question_out(db, question_id)


@router.get("/questions/{question_id}", response_model=InterviewQuestionOut)
async def get_question(question_id: int, db: AsyncSession = Depends(get_db)) -> InterviewQuestionOut:
    return await _question_out(db, question_id)


@router.put("/questions/{question_id}", response_model=InterviewQuestionOut)
async def update_question(
    question_id: int, body: InterviewQuestionUpsert, db: AsyncSession = Depends(get_db)
) -> InterviewQuestionOut:
    question = await _question_or_404(db, question_id)
    pack = await _pack_or_404(db, question.pack_id)
    try:
        await interview_packs.update_question(db, pack, question, body)
    except InterviewPackError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return await _question_out(db, question_id)


@router.delete("/questions/{question_id}")
async def retire_question(question_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    question = await _question_or_404(db, question_id)
    pack = await _pack_or_404(db, question.pack_id)
    interview_packs.retire_question(pack, question)
    await db.commit()
    return DELETED


@router.get("/questions/{question_id}/tts")
async def question_tts(question_id: int, db: AsyncSession = Depends(get_db)) -> FileResponse:
    question = await _question_or_404(db, question_id)
    settings = get_settings()
    cache_key = "interview_" + interview_grading.sha256_text(question.text)[:16]
    try:
        wav_path = await get_or_generate_tts(
            question_id=cache_key,
            text=question.text,
            cache_dir=settings.tts_cache_dir,
            voice=settings.tts_voice,
        )
    except Exception as exc:
        logger.warning("Interview TTS failed for question %d: %s", question_id, exc)
        raise HTTPException(status_code=503, detail="Text-to-speech is unavailable") from exc
    # The URL stays the same when a coach edits the question text, so the browser must revalidate.
    return FileResponse(path=str(wav_path), media_type="audio/wav", headers={"Cache-Control": "no-cache"})


@router.get("/questions/{question_id}/answers", response_model=List[InterviewAnswerOut])
async def list_answers(question_id: int, db: AsyncSession = Depends(get_db)) -> List[InterviewAnswerOut]:
    await _question_or_404(db, question_id)
    result = await db.execute(
        select(InterviewAnswer)
        .where(InterviewAnswer.question_id == question_id)
        .order_by(InterviewAnswer.created_at.desc(), InterviewAnswer.id.desc())
    )
    answers = list(result.scalars().all())
    if interview_grading.mark_stale(answers, utc_now()):
        await db.commit()
    return [interview_grading.answer_out(answer) for answer in answers]


@router.post("/questions/{question_id}/answers", response_model=InterviewAnswerOut, status_code=202)
async def submit_answer(
    question_id: int,
    audio: UploadFile,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> InterviewAnswerOut:
    question = await _question_or_404(db, question_id)
    if question.retired:
        raise HTTPException(status_code=409, detail="This question has been retired")

    answer = InterviewAnswer(question_id=question_id, status="processing")
    db.add(answer)
    await db.commit()
    await db.refresh(answer)

    try:
        answer.audio_path = await audio_service.save_audio(
            upload_file=audio,
            attempt_id=answer.id,
            audio_dir=get_settings().audio_dir,
            filename_stem=f"interview_{answer.id}",
        )
    except Exception as exc:
        answer.status = "failed:transcription"
        answer.error_message = f"Failed to save audio: {exc}"
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to save audio: {exc}") from exc
    await db.commit()

    background_tasks.add_task(interview_grading.process_recording, answer.id)
    return interview_grading.answer_out(answer)


@router.get("/answers/{answer_id}", response_model=InterviewAnswerOut)
async def get_answer(answer_id: int, db: AsyncSession = Depends(get_db)) -> InterviewAnswerOut:
    answer = await _answer_or_404(db, answer_id)
    if interview_grading.mark_stale([answer], utc_now()):
        await db.commit()
    return interview_grading.answer_out(answer)


@router.post("/answers/{answer_id}/grade", response_model=InterviewAnswerOut, status_code=202)
async def grade_answer(
    answer_id: int,
    body: InterviewGradeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> InterviewAnswerOut:
    answer = await _answer_or_404(db, answer_id)
    if answer.status not in interview_grading.GRADEABLE_STATUSES:
        raise HTTPException(status_code=409, detail=f"Answer cannot be graded while its status is {answer.status}")
    transcript = body.transcript.strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="Transcript must not be empty")

    run_token = utc_now()
    if not await interview_grading.claim_for_grading(db, answer, transcript, run_token):
        raise HTTPException(status_code=409, detail=f"Answer cannot be graded while its status is {answer.status}")

    background_tasks.add_task(interview_grading.grade_answer, answer.id, run_token)
    return interview_grading.answer_out(answer)


@router.get("/answers/{answer_id}/audio")
async def get_answer_audio(answer_id: int, db: AsyncSession = Depends(get_db)) -> FileResponse:
    answer = await _answer_or_404(db, answer_id)
    if not answer.audio_path or not Path(answer.audio_path).is_file():
        raise HTTPException(status_code=404, detail="Audio file is no longer available")
    media_type = EXT_TO_MIME.get(Path(answer.audio_path).suffix, "audio/webm")
    return FileResponse(answer.audio_path, media_type=media_type)
