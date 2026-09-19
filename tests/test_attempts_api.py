"""Integration tests for the attempts API: history stale-cleanup, pipeline persistence and the improve endpoint."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.api import attempts as attempts_module
from backend.api.attempts import router as attempts_router
from backend.database import get_db
from backend.models import Attempt, Base, Question
from backend.services.llm_client import LLMOutputError

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
        attempt = Attempt(question_id=q.id, status="processing", created_at=stale_time)
        attempts_db.add(attempt)
        await attempts_db.commit()

        resp = await attempts_client.get(f"/api/v1/attempts/history/{q.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "failed"

    async def test_stale_attempt_updated_in_db(self, attempts_client: AsyncClient, attempts_db: AsyncSession) -> None:
        """The DB row itself is updated to 'failed', not just the response."""
        q = await _make_question(attempts_db)
        stale_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=15)
        attempt = Attempt(question_id=q.id, status="processing", created_at=stale_time)
        attempts_db.add(attempt)
        await attempts_db.commit()

        await attempts_client.get(f"/api/v1/attempts/history/{q.id}")

        await attempts_db.refresh(attempt)
        assert attempt.status == "failed"

    async def test_fresh_processing_attempt_unchanged(
        self, attempts_client: AsyncClient, attempts_db: AsyncSession
    ) -> None:
        """An attempt in 'processing' created less than 10 minutes ago is left as-is."""
        q = await _make_question(attempts_db)
        fresh_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5)
        attempt = Attempt(question_id=q.id, status="processing", created_at=fresh_time)
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
        attempt = Attempt(question_id=q.id, status="processing", created_at=near_threshold)
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
        attempt = Attempt(question_id=q.id, status="ready", score=7.0, created_at=old_time)
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
        attempt = Attempt(question_id=q.id, status="transcribing", created_at=stale_time)
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
        attempt = Attempt(question_id=q.id, status="scoring", created_at=stale_time)
        attempts_db.add(attempt)
        await attempts_db.commit()

        resp = await attempts_client.get(f"/api/v1/attempts/history/{q.id}")
        assert resp.status_code == 200
        assert resp.json()[0]["status"] == "failed"

    async def test_returns_404_for_unknown_question(self, attempts_client: AsyncClient) -> None:
        resp = await attempts_client.get("/api/v1/attempts/history/99999")
        assert resp.status_code == 404


WORDS = [
    {"word": "I", "start": 0.0, "end": 0.4},
    {"word": "usually", "start": 0.5, "end": 1.1},
    {"word": "wake", "start": 1.2, "end": 1.6},
    {"word": "up", "start": 1.7, "end": 12.0},
]
TRANSCRIPT = "I usually wake up early."


@pytest.fixture
def pipeline_db(tmp_path, monkeypatch):
    """A file-backed session factory, so the pipeline task and the test can hold separate sessions."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path.as_posix()}/pipeline.db", echo=False)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(attempts_module, "AsyncSessionLocal", factory)
    monkeypatch.setattr(attempts_module, "get_lt_tool", lambda: None)
    return factory


async def _seeded_attempt(factory) -> int:
    async with factory() as session:
        await session.run_sync(lambda sync_session: Base.metadata.create_all(sync_session.get_bind()))
        question = Question(part="1", text="What time do you wake up?")
        session.add(question)
        await session.flush()
        attempt = Attempt(question_id=question.id, status="processing", audio_path="unused.webm")
        session.add(attempt)
        await session.commit()
        return attempt.id


class TestPipelineTranscriptPersistence:
    async def test_transcript_is_readable_while_scoring_runs(self, pipeline_db, monkeypatch) -> None:
        """The transcript, word timestamps and duration are committed before the LLM scoring step."""
        attempt_id = await _seeded_attempt(pipeline_db)
        seen: dict = {}

        async def fake_transcribe(_path: str) -> dict:
            return {"transcript": TRANSCRIPT, "words": WORDS}

        async def fake_score(**_kwargs) -> dict:
            async with pipeline_db() as session:
                row = (await session.execute(select(Attempt).where(Attempt.id == attempt_id))).scalar_one()
                seen.update(status=row.status, transcript=row.transcript, duration=row.duration_seconds)
            return {
                "fluency": 6.0,
                "vocabulary": 6.0,
                "grammar": 6.0,
                "pronunciation": 6.0,
                "score": 6.0,
                "feedback_text": "Good.",
                "usage_errors": [],
            }

        monkeypatch.setattr(attempts_module.transcription_service, "transcribe", fake_transcribe)
        monkeypatch.setattr(attempts_module.scoring_service, "score_attempt", fake_score)

        await attempts_module._run_pipeline(attempt_id, 1, "unused.webm")

        assert seen == {"status": "scoring", "transcript": TRANSCRIPT, "duration": 12}

        async with pipeline_db() as session:
            row = (await session.execute(select(Attempt).where(Attempt.id == attempt_id))).scalar_one()
            assert row.status == "ready"
            assert row.transcript == TRANSCRIPT
            assert row.duration_seconds == 12
            assert json.loads(row.word_timestamps) == WORDS

    async def test_scoring_failure_keeps_the_transcript_and_failed_status(self, pipeline_db, monkeypatch) -> None:
        attempt_id = await _seeded_attempt(pipeline_db)

        async def fake_transcribe(_path: str) -> dict:
            return {"transcript": TRANSCRIPT, "words": WORDS}

        async def failing_score(**_kwargs) -> dict:
            raise RuntimeError("LLM unavailable")

        monkeypatch.setattr(attempts_module.transcription_service, "transcribe", fake_transcribe)
        monkeypatch.setattr(attempts_module.scoring_service, "score_attempt", failing_score)

        await attempts_module._run_pipeline(attempt_id, 1, "unused.webm")

        async with pipeline_db() as session:
            row = (await session.execute(select(Attempt).where(Attempt.id == attempt_id))).scalar_one()
            assert row.status == "failed:scoring"
            assert row.transcript == TRANSCRIPT
            assert row.score is None


class TestImproveEndpoint:
    async def test_llm_output_error_becomes_502_with_a_readable_message(
        self, attempts_client: AsyncClient, attempts_db: AsyncSession, monkeypatch
    ) -> None:
        """A truncated rewrite is reported as an error, never rendered as the improved text."""
        q = await _make_question(attempts_db)
        attempt = Attempt(question_id=q.id, status="ready", transcript=TRANSCRIPT, score=6.0)
        attempts_db.add(attempt)
        await attempts_db.commit()

        async def failing_improvement(**_kwargs):
            raise LLMOutputError("gemini-3.6-flash output was cut off at max_tokens=8192")

        monkeypatch.setattr(attempts_module.improve_service, "generate_improvement", failing_improvement)

        resp = await attempts_client.post(f"/api/v1/attempts/{attempt.id}/improve")

        assert resp.status_code == 502
        assert "cut off" in resp.json()["detail"]
