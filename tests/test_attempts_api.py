"""Integration tests for attempts API — history endpoint stale-cleanup logic."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api.attempts import router as attempts_router
from backend.database import get_db
from backend.models import Attempt, Base, Question

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def attempts_db():
    """In-memory SQLite session scoped to this test module."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def attempts_client(attempts_db: AsyncSession):
    """HTTPX client wired to a test app that includes only the attempts router."""
    app = FastAPI()
    app.include_router(attempts_router)

    async def override_db():
        yield attempts_db

    app.dependency_overrides[get_db] = override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_question(session: AsyncSession) -> Question:
    q = Question(part="1", text="Test question?")
    session.add(q)
    await session.flush()
    return q


class TestAttemptHistory:
    async def test_stale_processing_attempt_returned_as_failed(
        self, attempts_client: AsyncClient, attempts_db: AsyncSession
    ) -> None:
        """An attempt stuck in 'processing' for >10 minutes is marked 'failed' on read."""
        q = await _make_question(attempts_db)
        stale_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=11)
        attempt = Attempt(
            question_id=q.id, status="processing", created_at=stale_time
        )
        attempts_db.add(attempt)
        await attempts_db.commit()

        resp = await attempts_client.get(f"/api/v1/attempts/history/{q.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "failed"

    async def test_stale_attempt_updated_in_db(
        self, attempts_client: AsyncClient, attempts_db: AsyncSession
    ) -> None:
        """The DB row itself is updated to 'failed', not just the response."""
        q = await _make_question(attempts_db)
        stale_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=15)
        attempt = Attempt(
            question_id=q.id, status="processing", created_at=stale_time
        )
        attempts_db.add(attempt)
        await attempts_db.commit()
        attempt_id = attempt.id

        await attempts_client.get(f"/api/v1/attempts/history/{q.id}")

        # Verify the DB row was updated
        await attempts_db.refresh(attempt)
        assert attempt.status == "failed"

    async def test_fresh_processing_attempt_unchanged(
        self, attempts_client: AsyncClient, attempts_db: AsyncSession
    ) -> None:
        """An attempt in 'processing' created less than 10 minutes ago is left as-is."""
        q = await _make_question(attempts_db)
        fresh_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5)
        attempt = Attempt(
            question_id=q.id, status="processing", created_at=fresh_time
        )
        attempts_db.add(attempt)
        await attempts_db.commit()

        resp = await attempts_client.get(f"/api/v1/attempts/history/{q.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "processing"

    async def test_attempt_just_under_threshold_not_marked_failed(
        self, attempts_client: AsyncClient, attempts_db: AsyncSession
    ) -> None:
        """Boundary: an attempt at 9m55s is NOT yet stale (must be strictly > 10 min)."""
        q = await _make_question(attempts_db)
        # 5 seconds of headroom to absorb test execution time without flapping
        near_threshold = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=10) + timedelta(seconds=5)
        attempt = Attempt(
            question_id=q.id, status="processing", created_at=near_threshold
        )
        attempts_db.add(attempt)
        await attempts_db.commit()

        resp = await attempts_client.get(f"/api/v1/attempts/history/{q.id}")
        data = resp.json()
        assert data[0]["status"] == "processing"

    async def test_ready_attempt_never_downgraded(
        self, attempts_client: AsyncClient, attempts_db: AsyncSession
    ) -> None:
        """A 'ready' attempt is never touched regardless of age."""
        q = await _make_question(attempts_db)
        old_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2)
        attempt = Attempt(
            question_id=q.id, status="ready", score=7.0, created_at=old_time
        )
        attempts_db.add(attempt)
        await attempts_db.commit()

        resp = await attempts_client.get(f"/api/v1/attempts/history/{q.id}")
        data = resp.json()
        assert data[0]["status"] == "ready"

    async def test_stale_transcribing_attempt_returned_as_failed(
        self, attempts_client: AsyncClient, attempts_db: AsyncSession
    ) -> None:
        """An attempt stuck in 'transcribing' for >10 minutes is marked 'failed' on read."""
        q = await _make_question(attempts_db)
        stale_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=11)
        attempt = Attempt(
            question_id=q.id, status="transcribing", created_at=stale_time
        )
        attempts_db.add(attempt)
        await attempts_db.commit()

        resp = await attempts_client.get(f"/api/v1/attempts/history/{q.id}")
        assert resp.status_code == 200
        assert resp.json()[0]["status"] == "failed"

    async def test_stale_scoring_attempt_returned_as_failed(
        self, attempts_client: AsyncClient, attempts_db: AsyncSession
    ) -> None:
        """An attempt stuck in 'scoring' for >10 minutes is marked 'failed' on read."""
        q = await _make_question(attempts_db)
        stale_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=11)
        attempt = Attempt(
            question_id=q.id, status="scoring", created_at=stale_time
        )
        attempts_db.add(attempt)
        await attempts_db.commit()

        resp = await attempts_client.get(f"/api/v1/attempts/history/{q.id}")
        assert resp.status_code == 200
        assert resp.json()[0]["status"] == "failed"

    async def test_returns_404_for_unknown_question(
        self, attempts_client: AsyncClient
    ) -> None:
        resp = await attempts_client.get("/api/v1/attempts/history/99999")
        assert resp.status_code == 404
