from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import Attempt, Question
from backend.schemas import ForecastEntry, Part3GroupOut, QuestionCreateIn, QuestionOut
from backend.services import ai_assist as ai_assist_service

router = APIRouter(prefix="/api/v1/questions", tags=["questions"])


async def _latest_score(session: AsyncSession, question_id: int) -> Optional[float]:
    """Return the score of the most recent 'ready' attempt for a question."""
    result = await session.execute(
        select(Attempt.score)
        .where(Attempt.question_id == question_id, Attempt.status == "ready")
        .order_by(Attempt.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row


async def _question_to_out(session: AsyncSession, q: Question) -> QuestionOut:
    score = await _latest_score(session, q.id)
    return QuestionOut(
        id=q.id,
        part=q.part,
        topic=q.topic,
        category=q.category,
        parent_question_id=q.parent_question_id,
        text=q.text,
        bullet_points=q.bullet_points,
        latest_score=score,
        topic_tag=q.topic_tag,
        source=q.source,
        last_seen_date=q.last_seen_date,
    )


async def _has_ready_attempt(session: AsyncSession, question_id: int) -> bool:
    """Check whether a question has at least one attempt with status='ready'."""
    result = await session.execute(
        select(Attempt.id)
        .where(Attempt.question_id == question_id, Attempt.status == "ready")
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


@router.get("/part1", response_model=List[QuestionOut])
async def list_part1(
    topic: Optional[str] = Query(default=None),
    topic_tag: Optional[str] = Query(default=None),
    hide_answered: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> List[QuestionOut]:
    stmt = select(Question).where(Question.part == "1")
    if topic:
        stmt = stmt.where(Question.topic == topic)
    if topic_tag:
        stmt = stmt.where(Question.topic_tag == topic_tag)
    stmt = stmt.order_by(Question.id)

    result = await db.execute(stmt)
    questions = result.scalars().all()

    output: List[QuestionOut] = []
    for q in questions:
        if hide_answered and await _has_ready_attempt(db, q.id):
            continue
        output.append(await _question_to_out(db, q))
    return output


@router.get("/part2", response_model=List[QuestionOut])
async def list_part2(
    category: Optional[str] = Query(default=None),
    topic_tag: Optional[str] = Query(default=None),
    hide_answered: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> List[QuestionOut]:
    stmt = select(Question).where(Question.part == "2")
    if category:
        stmt = stmt.where(Question.category == category)
    if topic_tag:
        stmt = stmt.where(Question.topic_tag == topic_tag)
    stmt = stmt.order_by(Question.id)

    result = await db.execute(stmt)
    questions = result.scalars().all()

    output: List[QuestionOut] = []
    for q in questions:
        if hide_answered and await _has_ready_attempt(db, q.id):
            continue
        output.append(await _question_to_out(db, q))
    return output


@router.get("/part3", response_model=List[Part3GroupOut])
async def list_part3(
    category: Optional[str] = Query(default=None),
    topic_tag: Optional[str] = Query(default=None),
    hide_answered: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> List[Part3GroupOut]:
    # Fetch all Part 2 questions (potential parents), optionally filtered
    parent_stmt = select(Question).where(Question.part == "2")
    if category:
        parent_stmt = parent_stmt.where(Question.category == category)
    if topic_tag:
        parent_stmt = parent_stmt.where(Question.topic_tag == topic_tag)
    parent_stmt = parent_stmt.order_by(Question.id)

    parent_result = await db.execute(parent_stmt)
    parent_questions = parent_result.scalars().all()

    groups: List[Part3GroupOut] = []
    for parent_q in parent_questions:
        # Fetch Part 3 children
        children_stmt = (
            select(Question)
            .where(Question.part == "3", Question.parent_question_id == parent_q.id)
            .order_by(Question.id)
        )
        children_result = await db.execute(children_stmt)
        children = children_result.scalars().all()

        if not children:
            continue

        filtered_children: List[QuestionOut] = []
        for child in children:
            if hide_answered and await _has_ready_attempt(db, child.id):
                continue
            filtered_children.append(await _question_to_out(db, child))

        if not filtered_children:
            continue

        parent_out = await _question_to_out(db, parent_q)
        groups.append(Part3GroupOut(parent=parent_out, questions=filtered_children))

    return groups


@router.get("/forecast", response_model=List[ForecastEntry])
async def get_forecast(
    db: AsyncSession = Depends(get_db),
) -> List[ForecastEntry]:
    """Return topic groups sorted by last_seen_date desc, then by question count."""
    result = await db.execute(
        select(
            Question.topic_tag,
            func.count(Question.id).label("count"),
            func.max(Question.last_seen_date).label("last_seen_date"),
        )
        .where(Question.topic_tag.isnot(None))
        .group_by(Question.topic_tag)
        .order_by(
            func.max(Question.last_seen_date).desc().nullslast(),
            func.count(Question.id).desc(),
        )
    )
    rows = result.all()
    return [
        ForecastEntry(
            topic_tag=row.topic_tag,
            count=row.count,
            last_seen_date=str(row.last_seen_date)[:7] if row.last_seen_date else None,
        )
        for row in rows
    ]


@router.post("/{question_id}/sample-answer")
async def sample_answer(
    question_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Generate a sample IELTS response for a question."""
    result = await db.execute(select(Question).where(Question.id == question_id))
    question = result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    try:
        data = await ai_assist_service.generate_sample_answer(
            question_text=question.text,
            part=question.part,
            target_band=7.0,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return data


@router.post("/{question_id}/topic-vocab")
async def topic_vocab(
    question_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Generate advanced topic vocabulary for a question."""
    result = await db.execute(select(Question).where(Question.id == question_id))
    question = result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    try:
        data = await ai_assist_service.generate_topic_vocab(question_text=question.text)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return data


@router.get("/{question_id}", response_model=QuestionOut)
async def get_question(
    question_id: int,
    db: AsyncSession = Depends(get_db),
) -> QuestionOut:
    result = await db.execute(select(Question).where(Question.id == question_id))
    question = result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return await _question_to_out(db, question)


@router.post("/bulk", status_code=201)
async def bulk_import_questions(
    body: List[QuestionCreateIn],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Bulk import questions; skips duplicates by text match."""
    existing = set(
        (await db.execute(select(Question.text))).scalars().all()
    )
    inserted = 0
    skipped = 0
    for q in body:
        if q.text in existing:
            skipped += 1
            continue
        bp_str = json.dumps(q.bullet_points) if q.bullet_points else None
        question = Question(
            part=q.part,
            topic=q.topic,
            category=q.category,
            parent_question_id=q.parent_question_id,
            text=q.text,
            bullet_points=bp_str,
            topic_tag=q.topic_tag,
            source=q.source,
            last_seen_date=q.last_seen_date,
        )
        db.add(question)
        inserted += 1
    await db.commit()
    return {"inserted": inserted, "skipped": skipped}


@router.post("/", response_model=QuestionOut, status_code=201)
async def create_question(
    body: QuestionCreateIn,
    db: AsyncSession = Depends(get_db),
) -> QuestionOut:
    bullet_points_str: Optional[str] = None
    if body.bullet_points is not None:
        bullet_points_str = json.dumps(body.bullet_points)

    question = Question(
        part=body.part,
        topic=body.topic,
        category=body.category,
        parent_question_id=body.parent_question_id,
        text=body.text,
        bullet_points=bullet_points_str,
        topic_tag=body.topic_tag,
        source=body.source,
        last_seen_date=body.last_seen_date,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)
    return await _question_to_out(db, question)
