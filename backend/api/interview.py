from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database import get_db
from backend.models import (
    CandidateProfile,
    InterviewAnswer,
    InterviewGlossaryTerm,
    InterviewKeyPoint,
    InterviewMisconception,
    InterviewPack,
    InterviewQuestion,
    InterviewSource,
)
from backend.schemas import (
    CV_TEXT_MAX,
    CandidateProfileIn,
    CandidateProfileOut,
    CvFileOut,
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
    IntroductionRequest,
    SkillListOut,
    SkillQuestionOut,
    SkillRowOut,
    SkillSetOut,
)
from backend.services import audio as audio_service
from backend.services import cv_import, interview_grading, interview_packs, interview_sentences
from backend.services import interview_skills, skills
from backend.services.audio import EXT_TO_MIME
from backend.services.cv_import import CvReadError
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


PROFILE_ID = 1


async def _profile(db: AsyncSession) -> CandidateProfile:
    """The one profile row on this computer, created empty the first time it is asked for."""
    profile = await db.get(CandidateProfile, PROFILE_ID)
    if profile is None:
        profile = CandidateProfile(id=PROFILE_ID)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    return profile


def _profile_out(profile: CandidateProfile) -> CandidateProfileOut:
    return CandidateProfileOut(
        full_name=profile.full_name,
        target_role=profile.target_role,
        cv_text=profile.cv_text,
        cv_filename=profile.cv_filename,
        has_cv=bool(profile.cv_text.strip()),
    )


@router.get("/profile", response_model=CandidateProfileOut)
async def get_profile(db: AsyncSession = Depends(get_db)) -> CandidateProfileOut:
    return _profile_out(await _profile(db))


@router.put("/profile", response_model=CandidateProfileOut)
async def update_profile(body: CandidateProfileIn, db: AsyncSession = Depends(get_db)) -> CandidateProfileOut:
    profile = await _profile(db)
    profile.full_name = body.full_name.strip()
    profile.target_role = body.target_role.strip()
    profile.cv_text = cv_import.tidy(body.cv_text)
    profile.cv_filename = body.cv_filename.strip()
    profile.updated_at = utc_now()
    await db.commit()
    logger.info("Candidate profile saved: cv=%d chars from %r", len(profile.cv_text), profile.cv_filename)
    return _profile_out(profile)


@router.post("/profile/cv-file", response_model=CvFileOut)
async def read_cv_file(file: UploadFile) -> CvFileOut:
    """Turn an uploaded CV into text without storing it; the candidate saves it themselves."""
    data = await file.read()
    filename = file.filename or ""
    try:
        text, truncated = cv_import.read_cv(filename, data, CV_TEXT_MAX)
    except CvReadError as exc:
        logger.info("CV file %r rejected: %s", filename, exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("CV file %r read: %d bytes -> %d characters", filename, len(data), len(text))
    return CvFileOut(filename=filename, text=text, characters=len(text), truncated=truncated)


@router.get("/about-you", response_model=Optional[InterviewPackDetailOut])
async def get_about_you(db: AsyncSession = Depends(get_db)) -> Optional[InterviewPackDetailOut]:
    """The candidate's own questions, or null before the first one is written."""
    pack = await interview_packs.load_personal_pack(db)
    return None if pack is None else await _detail(db, pack.id)


@router.post("/about-you/introduction", response_model=InterviewPackDetailOut)
async def draft_introduction(
    body: IntroductionRequest, db: AsyncSession = Depends(get_db)
) -> InterviewPackDetailOut:
    """Write an introduction question from the CV, into the candidate's own questionnaire."""
    profile = await _profile(db)
    job = await _pack_or_404(db, body.job_pack_id) if body.job_pack_id is not None else None
    pack = await interview_packs.load_or_create_personal_pack(db, profile)
    logger.info(
        "About you: writing the introduction question from a %d character CV, aimed at %s, with %s",
        len(profile.cv_text),
        job.title if job else "no job",
        get_settings().interview_drafter_model,
    )
    try:
        question_ids = await interview_packs.draft_introduction(db, pack, profile, job)
    except InterviewPackError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMRateLimitError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=429,
            detail="The Gemini drafter's free-tier quota is reached for now. Please try again later.",
        ) from exc
    except RuntimeError as exc:
        logger.exception("About you: the introduction question failed")
        await db.rollback()
        raise HTTPException(status_code=502, detail=f"Writing the question failed: {exc}") from exc
    await db.commit()
    logger.info("About you: introduction question id(s) %s", question_ids)
    return await _detail(db, pack.id)


async def _all_questions(db: AsyncSession) -> list[tuple[InterviewQuestion, InterviewPack]]:
    result = await db.execute(
        select(InterviewQuestion, InterviewPack)
        .join(InterviewPack, InterviewQuestion.pack_id == InterviewPack.id)
        .where(InterviewQuestion.retired.is_(False), InterviewQuestion.parent_question_id.is_(None))
    )
    return list(result.all())


async def _tags_and_scores(db: AsyncSession) -> tuple[dict[int, list[str]], dict[int, list[int]]]:
    rows = await _all_questions(db)
    tags = {question.id: interview_packs.json_or(question.tags, []) for question, _ in rows}
    answers = await db.execute(select(InterviewAnswer).where(InterviewAnswer.content_score.is_not(None)))
    return tags, interview_skills.latest_scores(answers.scalars().all())


@router.get("/skills", response_model=SkillListOut)
async def list_skills(job_pack_id: Optional[int] = None, db: AsyncSession = Depends(get_db)) -> SkillListOut:
    """Every skill the questions, the job or the CV name, worst first."""
    job = await interview_packs.load_pack(db, job_pack_id) if job_pack_id is not None else None
    profile = await _profile(db)
    job_skills = interview_skills.job_skills_of(job)
    cv_skills = skills.find_skills(profile.cv_text, limit=20)
    tags, scores = await _tags_and_scores(db)
    rows = interview_skills.build_rows(tags, scores, job_skills, cv_skills)
    return SkillListOut(
        job_pack_id=job.id if job else None,
        job_title=job.title if job else None,
        job_skills=job_skills,
        cv_skills=cv_skills,
        rows=[SkillRowOut(**{**row.__dict__, "state": row.state}) for row in rows],
    )


@router.get("/skills/questions", response_model=SkillSetOut)
async def list_skill_questions(skills_query: str = Query("", alias="skills"), db: AsyncSession = Depends(get_db)):
    """The questions carrying any of these skills, across every questionnaire."""
    wanted = skills.known_skills(skills_query.split(","))
    rows = await _all_questions(db)
    tags, scores = await _tags_and_scores(db)
    packs = {question.id: pack for question, pack in rows}
    matched = interview_skills.matching_questions([question for question, _ in rows], tags, wanted)
    return SkillSetOut(
        skills=wanted,
        labels=[skills.label_of(skill) for skill in wanted],
        questions=[
            SkillQuestionOut(
                id=question.id,
                pack_id=question.pack_id,
                pack_title=packs[question.id].title,
                topic=question.topic,
                kind=question.kind,
                text=question.text,
                answer_seconds=question.answer_seconds,
                tags=tags.get(question.id, []),
                matched=[tag for tag in tags.get(question.id, []) if tag in wanted],
                latest_content_score=max(scores[question.id]) if scores.get(question.id) else None,
            )
            for question in matched
        ],
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
    logger.info("Interview pack %d created: %r (%s/%s) by %s", pack.id, pack.title, pack.role, pack.level, pack.author)
    return await _detail(db, pack.id)


@router.post("/packs/import", response_model=InterviewPackDetailOut)
async def import_pack(file: UploadFile, db: AsyncSession = Depends(get_db)) -> InterviewPackDetailOut:
    data = await file.read(interview_packs.MAX_PACK_FILE_BYTES + 1)
    try:
        pack_file = interview_packs.parse_pack_bytes(data)
    except InterviewPackError as exc:
        # The read stops one byte past the limit, so an oversize file's real size is unknown here.
        read = (
            f"over {interview_packs.MAX_PACK_FILE_BYTES}"
            if len(data) > interview_packs.MAX_PACK_FILE_BYTES
            else len(data)
        )
        logger.warning("Interview pack import rejected (%s, %s bytes): %s", file.filename, read, exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    pack_id = await interview_packs.import_pack(db, pack_file)
    await db.commit()
    logger.info(
        "Interview pack %d imported from %s: %r v%s, %d question(s), %d glossary term(s)",
        pack_id,
        file.filename,
        pack_file.pack.title,
        pack_file.pack.version,
        len(pack_file.questions),
        len(pack_file.glossary),
    )
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
    logger.info(
        "Interview pack %d deleted: %r, %d question(s), %d recording(s)",
        pack_id,
        pack.title,
        len(question_ids),
        len(audio_paths),
    )

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
    logger.info("Interview pack %d glossary replaced: %d term(s)", pack_id, len(pack.glossary_terms))
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
    logger.info(
        "Interview pack %d source %d added: %r (%d chars)", pack_id, source.id, source.title, len(source.content or "")
    )
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
    logger.info("Interview pack %d source %d deleted", pack_id, source_id)
    return DELETED


@router.post("/packs/{pack_id}/draft", response_model=List[InterviewQuestionOut])
async def draft_questions(
    pack_id: int, body: InterviewDraftRequest, db: AsyncSession = Depends(get_db)
) -> List[InterviewQuestionOut]:
    pack = await _pack_or_404(db, pack_id)
    logger.info(
        "Interview pack %d: drafting %d question(s) on %r from %d source(s) with %s",
        pack_id,
        body.count,
        body.topic,
        len(body.source_ids),
        get_settings().interview_drafter_model,
    )
    try:
        question_ids = await interview_packs.draft_questions(db, pack, body)
    except InterviewPackError as exc:
        logger.warning("Interview pack %d: drafting rejected: %s", pack_id, exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMRateLimitError as exc:
        logger.warning("Interview pack %d: the drafter is out of free-tier quota", pack_id)
        await db.rollback()
        raise HTTPException(
            status_code=429,
            detail="The Gemini drafter's free-tier quota is reached for now. Please try again later.",
        ) from exc
    except RuntimeError as exc:
        logger.exception("Interview pack %d: drafting failed", pack_id)
        await db.rollback()
        raise HTTPException(status_code=502, detail=f"Drafting failed: {exc}") from exc
    await db.commit()
    logger.info("Interview pack %d: drafted question id(s) %s", pack_id, question_ids)
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
    logger.info("Interview question %d retired (pack %d)", question_id, pack.id)
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
        logger.exception(
            "Interview answer %d: saving audio failed (question_id=%d, content_type=%s)",
            answer.id,
            question_id,
            audio.content_type,
        )
        answer.status = "failed:transcription"
        answer.error_message = f"Failed to save audio: {exc}"
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to save audio: {exc}") from exc
    await db.commit()

    logger.info(
        "\n\n========== INTERVIEW SUBMIT answer_id=%d question_id=%d ==========\n"
        "  pack_id      : %s\n  audio saved  : %s\n  content_type : %s",
        answer.id,
        question_id,
        question.pack_id,
        answer.audio_path,
        audio.content_type,
    )
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

    logger.info(
        "Interview answer %d: grading requested (%d words, edited=%s)",
        answer.id,
        len(transcript.split()),
        answer.transcript_edited,
    )
    background_tasks.add_task(interview_grading.grade_answer, answer.id, run_token)
    return interview_grading.answer_out(answer)


@router.post("/answers/{answer_id}/sentence-fixes", response_model=InterviewAnswerOut)
async def improve_sentences(answer_id: int, db: AsyncSession = Depends(get_db)) -> InterviewAnswerOut:
    """Fill in the better version of each sentence already flagged as reading badly."""
    answer = await _answer_or_404(db, answer_id)
    rows = interview_grading.sentence_fixes_for(answer)
    pending = [row for row in rows if isinstance(row, dict) and not row.get("improved")]
    if not pending:
        return interview_grading.answer_out(answer)

    question = await _question_or_404(db, answer.question_id)
    logger.info("Interview answer %d: rewriting %d sentence(s)", answer_id, len(pending))
    try:
        fixes = await interview_sentences.generate_sentence_fixes(
            question.text,
            [{"text": row["original"], "reasons": row.get("reasons", [])} for row in pending],
        )
    except LLMRateLimitError as exc:
        logger.warning("Interview answer %d: the assist model is out of free-tier quota", answer_id)
        raise HTTPException(
            status_code=429,
            detail="The free-tier quota for sentence rewrites is reached for now. Please try again later.",
        ) from exc
    except (RuntimeError, ValueError) as exc:
        logger.exception("Interview answer %d: rewriting sentences failed", answer_id)
        raise HTTPException(status_code=502, detail=f"Rewriting failed: {exc}") from exc

    improved = {fix["original"]: fix for fix in fixes}
    for row in rows:
        fix = improved.get(row.get("original")) if isinstance(row, dict) else None
        if fix is not None:
            row["improved"] = fix["improved"]
            row["note"] = fix["note"]
    answer.sentence_fixes = json.dumps(rows)
    await db.commit()
    logger.info("Interview answer %d: %d of %d sentence(s) rewritten", answer_id, len(fixes), len(pending))
    return interview_grading.answer_out(answer)


@router.get("/answers/{answer_id}/audio")
async def get_answer_audio(answer_id: int, db: AsyncSession = Depends(get_db)) -> FileResponse:
    answer = await _answer_or_404(db, answer_id)
    if not answer.audio_path or not Path(answer.audio_path).is_file():
        raise HTTPException(status_code=404, detail="Audio file is no longer available")
    media_type = EXT_TO_MIME.get(Path(answer.audio_path).suffix, "audio/webm")
    return FileResponse(answer.audio_path, media_type=media_type)
