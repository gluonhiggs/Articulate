"""Integration tests for questions API — forecast and bulk import endpoints."""
from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Question


class TestBulkImport:
    async def test_insert_new_questions(self, api_client: AsyncClient) -> None:
        body = [
            {"text": "Do you enjoy reading books?", "part": "1", "topic_tag": "reading"},
            {"text": "Describe a memorable book.", "part": "2", "topic_tag": "reading"},
        ]
        resp = await api_client.post("/api/v1/questions/bulk", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["inserted"] == 2
        assert data["skipped"] == 0

    async def test_skips_duplicate_text(self, api_client: AsyncClient) -> None:
        body = [{"text": "Unique question for dup test?", "part": "1"}]
        await api_client.post("/api/v1/questions/bulk", json=body)
        resp = await api_client.post("/api/v1/questions/bulk", json=body)
        data = resp.json()
        assert data["inserted"] == 0
        assert data["skipped"] == 1

    async def test_mixed_batch_counts_correctly(self, api_client: AsyncClient) -> None:
        existing = [{"text": "Already in database?", "part": "1"}]
        await api_client.post("/api/v1/questions/bulk", json=existing)

        mixed = [
            {"text": "Already in database?", "part": "1"},
            {"text": "Brand new question here?", "part": "1"},
        ]
        resp = await api_client.post("/api/v1/questions/bulk", json=mixed)
        data = resp.json()
        assert data["inserted"] == 1
        assert data["skipped"] == 1

    async def test_empty_body_returns_zero_counts(self, api_client: AsyncClient) -> None:
        resp = await api_client.post("/api/v1/questions/bulk", json=[])
        assert resp.status_code == 201
        data = resp.json()
        assert data["inserted"] == 0
        assert data["skipped"] == 0

    async def test_invalid_part_rejected(self, api_client: AsyncClient) -> None:
        body = [{"text": "Some question?", "part": "custom"}]
        resp = await api_client.post("/api/v1/questions/bulk", json=body)
        assert resp.status_code == 422  # Pydantic Literal validation error


class TestForecast:
    async def test_empty_db_returns_empty_list(self, api_client: AsyncClient) -> None:
        resp = await api_client.get("/api/v1/questions/forecast")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_questions_without_topic_tag_excluded(
        self, api_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        q = Question(part="1", text="No tag question")
        db_session.add(q)
        await db_session.commit()

        resp = await api_client.get("/api/v1/questions/forecast")
        assert resp.json() == []

    async def test_tagged_topics_appear_grouped(
        self, api_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        for i in range(3):
            db_session.add(Question(part="1", text=f"Env Q{i}", topic_tag="environment"))
        db_session.add(Question(part="1", text="Tech Q1", topic_tag="technology"))
        await db_session.commit()

        resp = await api_client.get("/api/v1/questions/forecast")
        data = resp.json()
        env = next(e for e in data if e["topic_tag"] == "environment")
        tech = next(e for e in data if e["topic_tag"] == "technology")
        assert env["count"] == 3
        assert tech["count"] == 1

    async def test_sorted_by_last_seen_date_desc(
        self, api_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        db_session.add(
            Question(
                part="1", text="Old topic Q", topic_tag="education",
                last_seen_date=date(2024, 6, 1),
            )
        )
        db_session.add(
            Question(
                part="1", text="Recent topic Q", topic_tag="technology",
                last_seen_date=date(2025, 3, 1),
            )
        )
        await db_session.commit()

        resp = await api_client.get("/api/v1/questions/forecast")
        data = resp.json()
        tags_in_order = [e["topic_tag"] for e in data]
        assert tags_in_order.index("technology") < tags_in_order.index("education")

    async def test_last_seen_date_formatted_as_year_month(
        self, api_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        db_session.add(
            Question(
                part="1", text="Dated Q", topic_tag="environment",
                last_seen_date=date(2025, 1, 15),
            )
        )
        await db_session.commit()

        resp = await api_client.get("/api/v1/questions/forecast")
        data = resp.json()
        entry = next(e for e in data if e["topic_tag"] == "environment")
        assert entry["last_seen_date"] == "2025-01"

    async def test_null_last_seen_sorted_last(
        self, api_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        db_session.add(
            Question(
                part="1", text="Has date", topic_tag="education",
                last_seen_date=date(2024, 1, 1),
            )
        )
        db_session.add(Question(part="1", text="No date", topic_tag="friendship"))
        await db_session.commit()

        resp = await api_client.get("/api/v1/questions/forecast")
        data = resp.json()
        edu = next(e for e in data if e["topic_tag"] == "education")
        friend = next(e for e in data if e["topic_tag"] == "friendship")
        assert data.index(edu) < data.index(friend)
        assert friend["last_seen_date"] is None
