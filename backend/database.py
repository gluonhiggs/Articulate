from __future__ import annotations

import json
import os
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.future import select

from backend.config import get_settings
from backend.models import Base, DailyActivity, Question, UserStats


def _make_engine():
    settings = get_settings()
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    database_url = f"sqlite+aiosqlite:///{db_path}"
    return create_async_engine(database_url, echo=False, future=True)


engine = _make_engine()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def _seed_questions(session: AsyncSession) -> None:
    """Seed the database with questions from seed_questions.json."""
    seed_path = Path(__file__).parent.parent / "data" / "seed_questions.json"
    if not seed_path.exists():
        return

    with open(seed_path, "r", encoding="utf-8") as f:
        questions_data = json.load(f)

    # Separate by part
    part1_and_2 = [q for q in questions_data if q["part"] in ("1", "2")]
    part3 = [q for q in questions_data if q["part"] == "3"]

    # Map from question text -> inserted Question object (for Part 3 parent lookup)
    inserted_by_text: dict[str, Question] = {}

    for q_data in part1_and_2:
        bullet_points = q_data.get("bullet_points")
        if isinstance(bullet_points, list):
            bullet_points = json.dumps(bullet_points)

        question = Question(
            part=q_data["part"],
            topic=q_data.get("topic"),
            category=q_data.get("category"),
            parent_question_id=None,
            text=q_data["text"],
            bullet_points=bullet_points,
        )
        session.add(question)
        await session.flush()  # Get the ID assigned
        inserted_by_text[q_data["text"]] = question

    # Insert Part 3 questions, resolving parent_text -> parent_id
    for q_data in part3:
        parent_text = q_data.get("parent_text")
        parent_id: int | None = None
        if parent_text and parent_text in inserted_by_text:
            parent_id = inserted_by_text[parent_text].id

        question = Question(
            part="3",
            topic=q_data.get("topic"),
            category=q_data.get("category"),
            parent_question_id=parent_id,
            text=q_data["text"],
            bullet_points=None,
        )
        session.add(question)

    await session.commit()


async def _ensure_indexes() -> None:
    """Create indexes for existing DBs that predate index=True column declarations."""
    async with engine.begin() as conn:
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_attempts_question_id ON attempts(question_id)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_attempts_status ON attempts(status)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_attempts_created_at ON attempts(created_at)"
        ))


async def init_db() -> None:
    """Create all tables and seed if the questions table is empty."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await _ensure_indexes()

    async with AsyncSessionLocal() as session:
        # Check if questions table is empty
        result = await session.execute(select(Question).limit(1))
        existing = result.scalars().first()

        if existing is None:
            await _seed_questions(session)

        # Ensure UserStats row with id=1 exists
        stats_result = await session.execute(
            select(UserStats).where(UserStats.id == 1)
        )
        stats = stats_result.scalars().first()
        if stats is None:
            session.add(
                UserStats(
                    id=1,
                    current_streak=0,
                    longest_streak=0,
                    total_attempts=0,
                    estimated_band=None,
                )
            )
            await session.commit()
