"""Two attempts finishing at once must both count.

Before this was a select-then-insert on a unique date plus a read-modify-write counter:
the loser hit an IntegrityError that the pipeline's catch-all turned into failed, so a
fully scored attempt was thrown away, and concurrent increments were lost.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.attempts import _record_daily_activity, _update_user_stats
from backend.models import Base, DailyActivity, UserStats

TODAY = date(2026, 9, 21)


@pytest.fixture
async def engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def sessions(engine):
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def run(work, count: int) -> None:
        async def one(index: int) -> None:
            async with factory() as session:
                await work(session, index)
                await session.commit()

        await asyncio.gather(*(one(i) for i in range(count)))

    return run


async def _read(engine, statement):
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        return (await session.execute(statement)).all()


class TestDailyActivity:
    async def test_the_first_attempt_of_the_day_creates_the_row(self, engine, sessions) -> None:
        await sessions(lambda session, _: _record_daily_activity(session, TODAY), 1)

        rows = await _read(engine, select(DailyActivity.date, DailyActivity.attempts_count, DailyActivity.intensity))
        assert rows == [(TODAY, 1, 1)]

    async def test_concurrent_attempts_all_count_and_none_fail(self, engine, sessions) -> None:
        await sessions(lambda session, _: _record_daily_activity(session, TODAY), 8)

        rows = await _read(engine, select(DailyActivity.attempts_count, DailyActivity.intensity))
        assert rows == [(8, 4)]

    @pytest.mark.parametrize(
        "attempts,intensity",
        [(1, 1), (2, 2), (3, 2), (4, 3), (6, 3), (7, 4), (12, 4)],
    )
    async def test_intensity_matches_the_attempt_count(self, engine, sessions, attempts, intensity) -> None:
        await sessions(lambda session, _: _record_daily_activity(session, TODAY), attempts)

        rows = await _read(engine, select(DailyActivity.attempts_count, DailyActivity.intensity))
        assert rows == [(attempts, intensity)]


class TestUserStats:
    async def test_concurrent_attempts_do_not_lose_the_total(self, engine, sessions) -> None:
        await sessions(lambda session, _: _record_daily_activity(session, TODAY), 5)
        await sessions(lambda session, _: _update_user_stats(session, TODAY, None), 5)

        rows = await _read(engine, select(UserStats.total_attempts, UserStats.current_streak))
        assert rows == [(5, 1)]

    async def test_streak_counts_consecutive_days_and_keeps_the_longest(self, engine, sessions) -> None:
        for offset in (4, 3, 2, 1, 0):  # five days in a row, ending today
            day = TODAY - timedelta(days=offset)
            await sessions(lambda session, _, d=day: _record_daily_activity(session, d), 1)
            await sessions(lambda session, _, d=day: _update_user_stats(session, d, None), 1)

        rows = await _read(engine, select(UserStats.current_streak, UserStats.longest_streak))
        assert rows == [(5, 5)]

        # A gap resets the current streak without shrinking the longest.
        later = TODAY + timedelta(days=3)
        await sessions(lambda session, _: _record_daily_activity(session, later), 1)
        await sessions(lambda session, _: _update_user_stats(session, later, None), 1)

        rows = await _read(engine, select(UserStats.current_streak, UserStats.longest_streak))
        assert rows == [(1, 5)]
