"""Integration tests for questions API - forecast, bulk import, and list endpoints."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Attempt, Question


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

    async def test_tagged_topics_appear_grouped(self, api_client: AsyncClient, db_session: AsyncSession) -> None:
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

    async def test_sorted_by_last_seen_date_desc(self, api_client: AsyncClient, db_session: AsyncSession) -> None:
        db_session.add(
            Question(
                part="1",
                text="Old topic Q",
                topic_tag="education",
                last_seen_date=date(2024, 6, 1),
            )
        )
        db_session.add(
            Question(
                part="1",
                text="Recent topic Q",
                topic_tag="technology",
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
                part="1",
                text="Dated Q",
                topic_tag="environment",
                last_seen_date=date(2025, 1, 15),
            )
        )
        await db_session.commit()

        resp = await api_client.get("/api/v1/questions/forecast")
        data = resp.json()
        entry = next(e for e in data if e["topic_tag"] == "environment")
        assert entry["last_seen_date"] == "2025-01"

    async def test_null_last_seen_sorted_last(self, api_client: AsyncClient, db_session: AsyncSession) -> None:
        db_session.add(
            Question(
                part="1",
                text="Has date",
                topic_tag="education",
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


# ---------------------------------------------------------------------------
# List endpoint tests (part1 / part2 / part3) - bulk-query refactor coverage
# ---------------------------------------------------------------------------


class TestListPart1:
    async def test_returns_all_questions(self, api_client: AsyncClient, db_session: AsyncSession) -> None:
        for i in range(3):
            db_session.add(Question(part="1", text=f"Part1 Q{i}"))
        await db_session.commit()

        resp = await api_client.get("/api/v1/questions/part1")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    async def test_latest_score_none_when_no_attempts(self, api_client: AsyncClient, db_session: AsyncSession) -> None:
        db_session.add(Question(part="1", text="Unattempted question?"))
        await db_session.commit()

        resp = await api_client.get("/api/v1/questions/part1")
        assert resp.json()[0]["latest_score"] is None

    async def test_latest_score_populated_from_ready_attempt(
        self, api_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        q = Question(part="1", text="Scored question?")
        db_session.add(q)
        await db_session.flush()
        db_session.add(Attempt(question_id=q.id, status="ready", score=7.5))
        await db_session.commit()

        resp = await api_client.get("/api/v1/questions/part1")
        data = resp.json()
        assert data[0]["latest_score"] == 7.5

    async def test_latest_score_is_most_recent_ready_attempt(
        self, api_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Of multiple ready attempts, the most recent score wins."""
        now = datetime.now(UTC).replace(tzinfo=None)
        q = Question(part="1", text="Multi-attempt question?")
        db_session.add(q)
        await db_session.flush()
        db_session.add(Attempt(question_id=q.id, status="ready", score=5.0, created_at=now - timedelta(minutes=5)))
        db_session.add(Attempt(question_id=q.id, status="ready", score=8.0, created_at=now))
        db_session.add(
            Attempt(question_id=q.id, status="processing", score=None, created_at=now + timedelta(seconds=1))
        )
        await db_session.commit()

        resp = await api_client.get("/api/v1/questions/part1")
        # Most recent ready attempt (created_at=now) has score=8.0
        assert resp.json()[0]["latest_score"] == 8.0

    async def test_hide_answered_excludes_questions_with_ready_attempt(
        self, api_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        answered = Question(part="1", text="Answered question?")
        unanswered = Question(part="1", text="Unanswered question?")
        db_session.add(answered)
        db_session.add(unanswered)
        await db_session.flush()
        db_session.add(Attempt(question_id=answered.id, status="ready", score=6.0))
        await db_session.commit()

        resp = await api_client.get("/api/v1/questions/part1?hide_answered=true")
        texts = [q["text"] for q in resp.json()]
        assert "Answered question?" not in texts
        assert "Unanswered question?" in texts

    async def test_hide_answered_false_includes_all(self, api_client: AsyncClient, db_session: AsyncSession) -> None:
        q = Question(part="1", text="Answered with hide false?")
        db_session.add(q)
        await db_session.flush()
        db_session.add(Attempt(question_id=q.id, status="ready", score=7.0))
        await db_session.commit()

        resp = await api_client.get("/api/v1/questions/part1?hide_answered=false")
        assert len(resp.json()) == 1

    async def test_processing_attempt_does_not_count_as_answered(
        self, api_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        q = Question(part="1", text="Processing only question?")
        db_session.add(q)
        await db_session.flush()
        db_session.add(Attempt(question_id=q.id, status="processing", score=None))
        await db_session.commit()

        resp = await api_client.get("/api/v1/questions/part1?hide_answered=true")
        assert len(resp.json()) == 1


class TestListPart2:
    async def test_returns_part2_questions(self, api_client: AsyncClient, db_session: AsyncSession) -> None:
        db_session.add(Question(part="2", text="Describe a place.", category="places"))
        db_session.add(Question(part="1", text="Other part question?"))
        await db_session.commit()

        resp = await api_client.get("/api/v1/questions/part2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["text"] == "Describe a place."

    async def test_hide_answered_filters_ready_part2(self, api_client: AsyncClient, db_session: AsyncSession) -> None:
        answered = Question(part="2", text="Answered part2.")
        unanswered = Question(part="2", text="Unanswered part2.")
        db_session.add(answered)
        db_session.add(unanswered)
        await db_session.flush()
        db_session.add(Attempt(question_id=answered.id, status="ready", score=6.5))
        await db_session.commit()

        resp = await api_client.get("/api/v1/questions/part2?hide_answered=true")
        texts = [q["text"] for q in resp.json()]
        assert "Answered part2." not in texts
        assert "Unanswered part2." in texts


class TestListPart3:
    async def test_groups_children_under_parent(self, api_client: AsyncClient, db_session: AsyncSession) -> None:
        parent = Question(part="2", text="Describe a hobby.")
        db_session.add(parent)
        await db_session.flush()
        for i in range(3):
            db_session.add(Question(part="3", text=f"Follow-up {i}?", parent_question_id=parent.id))
        await db_session.commit()

        resp = await api_client.get("/api/v1/questions/part3")
        assert resp.status_code == 200
        groups = resp.json()
        assert len(groups) == 1
        assert groups[0]["parent"]["text"] == "Describe a hobby."
        assert len(groups[0]["questions"]) == 3

    async def test_parent_without_children_excluded(self, api_client: AsyncClient, db_session: AsyncSession) -> None:
        db_session.add(Question(part="2", text="Childless part2 card."))
        await db_session.commit()

        resp = await api_client.get("/api/v1/questions/part3")
        assert resp.json() == []

    async def test_hide_answered_filters_children_not_parents(
        self, api_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """hide_answered removes answered children but keeps the group if any child remains."""
        parent = Question(part="2", text="Describe a challenge.")
        db_session.add(parent)
        await db_session.flush()
        answered_child = Question(part="3", text="Answered follow-up?", parent_question_id=parent.id)
        open_child = Question(part="3", text="Open follow-up?", parent_question_id=parent.id)
        db_session.add(answered_child)
        db_session.add(open_child)
        await db_session.flush()
        db_session.add(Attempt(question_id=answered_child.id, status="ready", score=7.0))
        await db_session.commit()

        resp = await api_client.get("/api/v1/questions/part3?hide_answered=true")
        groups = resp.json()
        assert len(groups) == 1
        child_texts = [q["text"] for q in groups[0]["questions"]]
        assert "Answered follow-up?" not in child_texts
        assert "Open follow-up?" in child_texts

    async def test_all_children_answered_hides_entire_group(
        self, api_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        parent = Question(part="2", text="Describe a skill.")
        db_session.add(parent)
        await db_session.flush()
        child = Question(part="3", text="Only child follow-up?", parent_question_id=parent.id)
        db_session.add(child)
        await db_session.flush()
        db_session.add(Attempt(question_id=child.id, status="ready", score=8.0))
        await db_session.commit()

        resp = await api_client.get("/api/v1/questions/part3?hide_answered=true")
        assert resp.json() == []

    async def test_part3_latest_score_populated(self, api_client: AsyncClient, db_session: AsyncSession) -> None:
        parent = Question(part="2", text="Describe a meal.")
        db_session.add(parent)
        await db_session.flush()
        child = Question(part="3", text="Scored child?", parent_question_id=parent.id)
        db_session.add(child)
        await db_session.flush()
        db_session.add(Attempt(question_id=child.id, status="ready", score=6.5))
        await db_session.commit()

        resp = await api_client.get("/api/v1/questions/part3")
        groups = resp.json()
        assert groups[0]["questions"][0]["latest_score"] == 6.5
