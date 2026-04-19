from __future__ import annotations

import json
import logging
from datetime import date as date_type
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.future import select

from backend.config import get_settings
from backend.models import Base, Question, UserStats

logger = logging.getLogger(__name__)


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
    """Seed questions from seed_questions.json (additive - skips existing by text match)."""
    seed_path = Path(__file__).parent.parent / "data" / "seed_questions.json"
    if not seed_path.exists():
        return

    with open(seed_path, "r", encoding="utf-8") as f:
        questions_data = json.load(f)

    # Get existing question texts to avoid duplicates
    existing_texts = set((await session.execute(select(Question.text))).scalars().all())

    # Build lookup of all existing questions for parent_text resolution
    existing_by_text: dict[str, Question] = {}
    existing_result = await session.execute(select(Question))
    for q in existing_result.scalars().all():
        existing_by_text[q.text] = q

    # Separate by part
    part1_and_2 = [q for q in questions_data if q["part"] in ("1", "2")]
    part3 = [q for q in questions_data if q["part"] == "3"]

    inserted_by_text: dict[str, Question] = dict(existing_by_text)

    for q_data in part1_and_2:
        if q_data["text"] in existing_texts:
            continue

        bullet_points = q_data.get("bullet_points")
        if isinstance(bullet_points, list):
            bullet_points = json.dumps(bullet_points)

        last_seen = None
        last_seen_raw = q_data.get("last_seen_date")
        if last_seen_raw:
            try:
                if len(last_seen_raw) == 7:  # "YYYY-MM"
                    last_seen = date_type.fromisoformat(f"{last_seen_raw}-01")
                else:
                    last_seen = date_type.fromisoformat(last_seen_raw)
            except ValueError:
                pass

        question = Question(
            part=q_data["part"],
            topic=q_data.get("topic"),
            category=q_data.get("category"),
            parent_question_id=None,
            text=q_data["text"],
            bullet_points=bullet_points,
            topic_tag=q_data.get("topic_tag"),
            source=q_data.get("source"),
            last_seen_date=last_seen,
        )
        session.add(question)
        await session.flush()
        inserted_by_text[q_data["text"]] = question

    # Insert Part 3 questions, resolving parent_text -> parent_id
    for q_data in part3:
        if q_data["text"] in existing_texts:
            continue

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
            topic_tag=q_data.get("topic_tag"),
            source=q_data.get("source"),
            last_seen_date=None,
        )
        session.add(question)

    await session.commit()

    # Warn about orphaned Part 3 questions (parent_question_id IS NULL).
    # This catches seeding mismatches (typos, ordering issues) before they silently
    # disappear from the Part 3 grouped UI.
    orphan_result = await session.execute(
        select(Question.id, Question.text).where(Question.part == "3", Question.parent_question_id.is_(None))
    )
    for row in orphan_result.all():
        logger.warning(
            "Orphaned Part 3 question (no parent_question_id): id=%d text=%r",
            row.id,
            row.text,
        )


async def _ensure_indexes() -> None:
    """Create indexes and run column migrations for existing DBs."""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_attempts_question_id ON attempts(question_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_attempts_status ON attempts(status)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_attempts_created_at ON attempts(created_at)"))
        # New column migrations - idempotent via try/except (SQLite has no IF NOT EXISTS for ALTER)
        for col_sql in [
            "ALTER TABLE questions ADD COLUMN topic_tag TEXT",
            "ALTER TABLE questions ADD COLUMN source TEXT",
            "ALTER TABLE questions ADD COLUMN last_seen_date DATE",
        ]:
            try:
                await conn.execute(text(col_sql))
            except Exception as exc:
                logger.debug("ALTER TABLE skipped (column likely exists): %s", exc)


async def init_db() -> None:
    """Create all tables and seed questions (additive)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await _ensure_indexes()

    async with AsyncSessionLocal() as session:
        # Always run seeding (additive - skips existing by text match)
        await _seed_questions(session)

        # Ensure UserStats row with id=1 exists
        stats_result = await session.execute(select(UserStats).where(UserStats.id == 1))
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
