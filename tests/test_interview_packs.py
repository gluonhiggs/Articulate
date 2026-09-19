"""Interview pack file parsing, import/export round trip, upsert semantics and sample seeding."""

from __future__ import annotations

import json
import re
import time

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import InterviewAnswer, InterviewKeyPoint, InterviewPack, InterviewQuestion, InterviewSource
from backend.services import interview_packs
from backend.services.interview_packs import InterviewPackError, parse_pack_bytes
from tests.interview_fixtures import PACK_UID, pack_bytes, sample_pack


async def _import(session: AsyncSession, pack: dict) -> int:
    pack_id = await interview_packs.import_pack(session, parse_pack_bytes(pack_bytes(pack)))
    await session.commit()
    return pack_id


async def _questions_by_uid(session: AsyncSession) -> dict[str, InterviewQuestion]:
    result = await session.execute(select(InterviewQuestion))
    return {q.uid: q for q in result.scalars().all()}


class TestParsePackBytes:
    def test_valid_file(self):
        pack_file = parse_pack_bytes(pack_bytes(sample_pack()))
        assert pack_file.pack.id == PACK_UID
        assert pack_file.questions[0].key_points[0].approved is True

    def test_utf8_bom_is_accepted(self):
        assert parse_pack_bytes(b"\xef\xbb\xbf" + pack_bytes(sample_pack())).pack.title

    @pytest.mark.parametrize(
        ("data", "message"),
        [
            (b"x" * (5 * 1024 * 1024 + 1), "larger than 5 MB"),
            (b"\xff\xfe\x00{", "UTF-8"),
            (b'{"format": "articulate-interview-pack", ', "not valid JSON (line 1"),
            (b"[]", "not an Articulate interview pack"),
            (b'{"format": "something-else"}', "not an Articulate interview pack"),
            (b'{"format": "articulate-interview-pack", "format_version": 7}', "format_version 7"),
            (b"[" * 100_000, "not valid JSON"),
            (b'{"pack": {"version": ' + b"9" * 5000 + b"}}", "not valid JSON"),
        ],
        ids=["too-large", "not-utf8", "bad-json", "not-object", "wrong-format", "wrong-version", "deep", "huge-int"],
    )
    def test_readable_errors(self, data, message):
        with pytest.raises(InterviewPackError, match=re.escape(message)):
            parse_pack_bytes(data)

    def test_schema_errors_name_the_field(self):
        pack = sample_pack()
        pack["pack"]["role"] = "manager"
        pack["questions"][0]["key_points"][0]["weight"] = 5
        with pytest.raises(InterviewPackError) as excinfo:
            parse_pack_bytes(pack_bytes(pack))
        message = str(excinfo.value)
        assert "pack.role" in message
        assert "questions.0.key_points.0.weight" in message

    def test_out_of_range_version_is_a_schema_error(self):
        pack = sample_pack()
        pack["pack"]["version"] = 2**70
        with pytest.raises(InterviewPackError, match=re.escape("pack.version")):
            parse_pack_bytes(pack_bytes(pack))

    @pytest.mark.parametrize(
        "url", ["file:///C:/Windows/System32/calc.exe", "javascript:alert(1)", r"\\server\share\tool.exe"]
    )
    def test_source_url_must_be_a_web_link(self, url):
        pack = sample_pack()
        pack["sources"][0]["url"] = url
        with pytest.raises(InterviewPackError, match=re.escape("sources.0.url")):
            parse_pack_bytes(pack_bytes(pack))

    def test_blank_source_url_becomes_none(self):
        pack = sample_pack()
        pack["sources"][0]["url"] = "  "
        assert parse_pack_bytes(pack_bytes(pack)).sources[0].url is None

    def test_duplicate_ids_are_rejected(self):
        pack = sample_pack()
        pack["questions"][1]["id"] = "q-lazy"
        with pytest.raises(InterviewPackError, match="duplicate question id 'q-lazy'"):
            parse_pack_bytes(pack_bytes(pack))

    def test_follow_up_trigger_must_be_a_parent_key_point(self):
        pack = sample_pack()
        pack["questions"][0]["follow_ups"][0]["trigger_key_point_id"] = "kp-shuffle"
        with pytest.raises(InterviewPackError, match="not a key point of its parent question"):
            parse_pack_bytes(pack_bytes(pack))


class TestImportExport:
    async def test_import_creates_pack_with_verified_quotes(self, db_session: AsyncSession):
        pack_id = await _import(db_session, sample_pack())
        detail = await interview_packs.pack_detail(db_session, pack_id)

        assert detail.uid == PACK_UID
        assert detail.version == 2
        assert [q.text for q in detail.questions] == [
            "What is lazy evaluation in Spark?",
            "What is a shuffle and why is it expensive?",
        ]
        lazy = detail.questions[0]
        assert [kp.quote_verified for kp in lazy.key_points] == [True, None, False]
        assert all(kp.approved for kp in lazy.key_points)
        assert [f.text for f in lazy.follow_ups] == [
            "How does the plan help Spark optimize a job?",
            "When would you cache a DataFrame?",
        ]
        assert lazy.follow_ups[0].trigger_key_point_uid == "kp-lazy-dag"
        assert lazy.follow_ups[0].topic == "Spark"
        assert {t.term: t.aliases for t in detail.glossary} == {"PySpark": [], "PostgreSQL": ["post gres"]}
        assert [(t.topic, t.question_count, t.graded_count) for t in detail.topics] == [
            ("Spark", 1, 0),
            ("Performance", 1, 0),
        ]
        assert detail.sources[0].content_length == len(sample_pack()["sources"][0]["content"])

    async def test_export_round_trip_preserves_ids_and_content(self, db_session: AsyncSession):
        original = sample_pack()
        pack_id = await _import(db_session, original)
        exported = interview_packs.export_pack(await interview_packs.load_pack(db_session, pack_id)).model_dump(
            mode="json"
        )

        assert exported["pack"]["id"] == PACK_UID
        assert exported["glossary"] == original["glossary"]
        assert exported["sources"] == original["sources"]
        first = exported["questions"][0]
        assert [kp["id"] for kp in first["key_points"]] == ["kp-lazy-core", "kp-lazy-dag", "kp-lazy-example"]
        assert first["misconceptions"] == original["questions"][0]["misconceptions"]
        assert [(f["id"], f["trigger_key_point_id"]) for f in first["follow_ups"]] == [
            ("fu-dag", "kp-lazy-dag"),
            ("fu-cache", None),
        ]

        reimported_id = await _import(db_session, json.loads(json.dumps(exported)))
        assert reimported_id == pack_id
        again = interview_packs.export_pack(await interview_packs.load_pack(db_session, pack_id)).model_dump(
            mode="json"
        )
        assert again == exported
        assert await db_session.scalar(select(func.count()).select_from(InterviewPack)) == 1

    async def test_reimport_upserts_in_place_and_retires_missing_questions(self, db_session: AsyncSession):
        pack_id = await _import(db_session, sample_pack())
        before = await _questions_by_uid(db_session)
        db_session.add(InterviewAnswer(question_id=before["q-shuffle"].id, status="graded", content_score=50))
        await db_session.commit()

        updated = sample_pack()
        updated["pack"]["version"] = 3
        updated["pack"]["title"] = "Spark basics v3"
        lazy = updated["questions"][0]
        lazy["key_points"][0]["text"] = "Transformations stay lazy until an action runs"
        del lazy["key_points"][2]
        lazy["follow_ups"] = lazy["follow_ups"][:1]
        updated["questions"] = [lazy]
        updated["glossary"] = [{"term": "Databricks", "aliases": ["data bricks"]}]
        await _import(db_session, updated)

        after = await _questions_by_uid(db_session)
        assert after["q-lazy"].id == before["q-lazy"].id
        assert after["q-shuffle"].retired is True
        assert after["fu-cache"].retired is True
        assert after["fu-dag"].retired is False
        key_points = (await db_session.execute(select(InterviewKeyPoint.uid, InterviewKeyPoint.text))).all()
        texts = dict(key_points)
        assert "kp-lazy-example" not in texts
        assert texts["kp-lazy-core"] == "Transformations stay lazy until an action runs"
        answers = await db_session.scalar(select(func.count()).select_from(InterviewAnswer))
        assert answers == 1

        detail = await interview_packs.pack_detail(db_session, pack_id)
        assert detail.title == "Spark basics v3"
        assert detail.version == 3
        assert [q.uid for q in detail.questions] == ["q-lazy"]
        assert [f.uid for f in detail.questions[0].follow_ups] == ["fu-dag"]
        assert [t.term for t in detail.glossary] == ["Databricks"]

        exported = interview_packs.export_pack(await interview_packs.load_pack(db_session, pack_id))
        assert [q.id for q in exported.questions] == ["q-lazy"]

        restored = await _import(db_session, sample_pack())
        detail = await interview_packs.pack_detail(db_session, restored)
        assert [q.uid for q in detail.questions] == ["q-lazy", "q-shuffle"]
        assert detail.questions[1].answer_count == 1

    async def test_import_without_ids_generates_uids(self, db_session: AsyncSession):
        pack = sample_pack()
        del pack["pack"]["id"]
        for question in pack["questions"]:
            del question["id"]
            for key_point in question["key_points"]:
                del key_point["id"]
            question.pop("follow_ups", None)
        first = await _import(db_session, pack)
        second = await _import(db_session, pack)
        assert first != second
        uids = [q.uid for q in (await _questions_by_uid(db_session)).values()]
        assert len(set(uids)) == 4


class TestSourceQuoteVerification:
    async def test_repetitive_source_is_checked_quickly(self):
        sources = [InterviewSource(title="Repetitive", content="a " * 100_000)]
        quotes = ["a b " * 150, "a b " * 30, "a a a b"]
        started = time.perf_counter()
        assert await interview_packs.verify_source_quotes(sources, quotes) == {q.strip(): False for q in quotes}
        assert time.perf_counter() - started < 3.0

    async def test_quotes_are_stripped_and_blank_quotes_skipped(self):
        sources = [InterviewSource(title="Notes", content="Spark evaluates transformations lazily.")]
        verified = await interview_packs.verify_source_quotes(
            sources, ["  Spark evaluates transformations lazily. ", "", None]
        )
        assert verified == {"Spark evaluates transformations lazily.": True}


class TestSeedSamplePacks:
    async def test_seeds_new_packs_once_and_skips_invalid_files(self, db_session: AsyncSession, tmp_path):
        (tmp_path / "a-valid.json").write_bytes(pack_bytes(sample_pack()))
        (tmp_path / "b-broken.json").write_text("{not json", encoding="utf-8")
        no_id = sample_pack()
        del no_id["pack"]["id"]
        (tmp_path / "c-no-id.json").write_bytes(pack_bytes(no_id))

        await interview_packs.seed_sample_packs(db_session, tmp_path)
        await interview_packs.seed_sample_packs(db_session, tmp_path)

        assert await db_session.scalar(select(func.count()).select_from(InterviewPack)) == 1

    async def test_existing_pack_is_not_overwritten(self, db_session: AsyncSession, tmp_path):
        pack_id = await _import(db_session, sample_pack())
        pack = await interview_packs.load_pack(db_session, pack_id)
        pack.title = "Edited locally"
        await db_session.commit()

        (tmp_path / "pack.json").write_bytes(pack_bytes(sample_pack()))
        await interview_packs.seed_sample_packs(db_session, tmp_path)

        assert (await interview_packs.load_pack(db_session, pack_id)).title == "Edited locally"

    async def test_missing_directory_is_ignored(self, db_session: AsyncSession, tmp_path):
        await interview_packs.seed_sample_packs(db_session, tmp_path / "missing")

    def test_bundled_sample_packs_are_valid(self):
        files = sorted(interview_packs.SEED_PACKS_DIR.glob("*.json"))
        if not files:
            pytest.skip("no bundled sample packs")
        for path in files:
            pack_file = parse_pack_bytes(path.read_bytes())
            assert pack_file.pack.id, f"{path.name} needs pack.id for seeding"
            quotes = interview_packs.SourceQuoteChecker(source.content for source in pack_file.sources)
            unverified = [
                key_point.source_quote
                for question in pack_file.questions
                for item in (question, *question.follow_ups)
                for key_point in item.key_points
                if key_point.source_quote and not quotes.verify(key_point.source_quote)
            ]
            assert unverified == [], f"{path.name} has source quotes not found in its sources"
