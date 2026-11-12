"""Interview packs: file import/export, question upserts, pack read models, AI drafting and sample seeding."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import get_settings
from backend.constants import PROJECT_ROOT
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
    ANSWER_SECONDS_MAX,
    ANSWER_SECONDS_MIN,
    DEFAULT_FOLLOW_UP_SECONDS,
    DEFAULT_QUESTION_SECONDS,
    KEY_POINT_TEXT_MAX,
    MAX_FOLLOW_UPS,
    MAX_KEY_POINTS,
    MAX_MISCONCEPTIONS,
    MISCONCEPTION_TEXT_MAX,
    PACK_FILE_FORMAT,
    PACK_FILE_FORMAT_VERSION,
    QUESTION_TEXT_MAX,
    SOURCE_QUOTE_MAX,
    InterviewDraftRequest,
    InterviewFollowUpIn,
    InterviewGlossaryTermOut,
    InterviewKeyPointIn,
    InterviewKeyPointOut,
    InterviewMisconceptionIn,
    InterviewMisconceptionOut,
    InterviewPackDetailOut,
    InterviewPackSummaryOut,
    InterviewQuestionOut,
    InterviewQuestionUpsert,
    InterviewSourceOut,
    InterviewTopicReadiness,
    PackFile,
    PackFileFollowUp,
    PackFileGlossaryTerm,
    PackFileKeyPoint,
    PackFileMeta,
    PackFileMisconception,
    PackFileQuestion,
    PackFileSource,
)
from backend.services import interview_prompts, llm_client
from backend.services.skills import find_skills
from backend.services.interview_glossary import GlossaryEntry
from backend.services.interview_scoring import QuoteIndex

logger = logging.getLogger(__name__)

MAX_PACK_FILE_BYTES = 5 * 1024 * 1024
SEED_PACKS_DIR = PROJECT_ROOT / "data" / "interview_packs"
DRAFT_SOURCES_CHAR_LIMIT = 24_000
DRAFT_EXISTING_QUESTIONS_CHAR_LIMIT = 8_000
INTRODUCTION_TOPIC = "About you"
INTRODUCTION_COUNT = 1
INTRODUCTION_MIN_KEY_POINTS = 2
INTRODUCTION_MIN_CV_CHARS = 200
CV_CHAR_LIMIT = 24_000
PERSONAL_PACK_TITLE = "About you"
# An introduction names a project, the decision behind it and a number. Two minutes
# cuts the recording off mid-sentence, because answer_seconds stops the microphone.
INTRODUCTION_MIN_SECONDS = 150
SOURCE_PREVIEW_CHARS = 200
MAX_VALIDATION_ERRORS_SHOWN = 5


class InterviewPackError(ValueError):
    """Invalid pack file or pack request; the message is shown to the user as-is."""


def new_uid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def pack_slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60].strip("-") or "interview-pack"


def aliases_of(term: InterviewGlossaryTerm) -> list[str]:
    try:
        aliases = json.loads(term.aliases or "[]")
    except json.JSONDecodeError:
        logger.warning("Glossary term %r has unreadable aliases; ignoring them", term.term)
        return []
    return [str(alias) for alias in aliases if str(alias).strip()] if isinstance(aliases, list) else []


def glossary_entries(terms: Iterable[InterviewGlossaryTerm]) -> list[GlossaryEntry]:
    return [GlossaryEntry(term.term, tuple(aliases_of(term))) for term in terms]


def clean_aliases(aliases: Iterable[str]) -> str:
    """Aliases as the JSON list stored on a glossary term, without blanks."""
    return json.dumps([alias.strip() for alias in aliases if alias.strip()])


def json_or(raw: Optional[str], default: Any) -> Any:
    """Decoded JSON column value, or default when it is empty or not valid JSON."""
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Unreadable JSON column (%d chars); falling back to %r", len(raw), default)
        return default


def _format_validation_error(exc: ValidationError) -> str:
    problems = []
    for error in exc.errors()[:MAX_VALIDATION_ERRORS_SHOWN]:
        location = ".".join(str(part) for part in error["loc"]) or "file"
        problems.append(f"{location}: {error['msg']}")
    more = len(exc.errors()) - MAX_VALIDATION_ERRORS_SHOWN
    suffix = f" (and {more} more problems)" if more > 0 else ""
    return "Invalid pack file: " + "; ".join(problems) + suffix


def _check_unique_ids(pack_file: PackFile) -> None:
    seen: dict[str, set[str]] = defaultdict(set)

    def claim(kind: str, item_id: Optional[str]) -> None:
        if item_id is None:
            return
        if item_id in seen[kind]:
            raise InterviewPackError(f"Invalid pack file: duplicate {kind} id {item_id!r}.")
        seen[kind].add(item_id)

    for source in pack_file.sources:
        claim("source", source.id)
    for question in pack_file.questions:
        claim("question", question.id)
        for item in (question, *question.follow_ups):
            for key_point in item.key_points:
                claim("key point", key_point.id)
            for misconception in item.misconceptions:
                claim("misconception", misconception.id)
        own_key_point_ids = {key_point.id for key_point in question.key_points if key_point.id}
        for follow_up in question.follow_ups:
            claim("question", follow_up.id)
            if follow_up.trigger_key_point_id and follow_up.trigger_key_point_id not in own_key_point_ids:
                raise InterviewPackError(
                    f"Invalid pack file: follow-up {follow_up.text[:60]!r} is triggered by key point "
                    f"{follow_up.trigger_key_point_id!r}, which is not a key point of its parent question."
                )


def parse_pack_bytes(data: bytes) -> PackFile:
    if len(data) > MAX_PACK_FILE_BYTES:
        raise InterviewPackError(f"Pack file is larger than {MAX_PACK_FILE_BYTES // (1024 * 1024)} MB.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InterviewPackError("Pack file must be UTF-8 encoded JSON.") from exc
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InterviewPackError(
            f"Pack file is not valid JSON (line {exc.lineno}, column {exc.colno}): {exc.msg}."
        ) from exc
    except (RecursionError, ValueError) as exc:
        raise InterviewPackError(
            "Pack file is not valid JSON: it is nested too deeply or has an oversized number."
        ) from exc
    if not isinstance(raw, dict) or raw.get("format") != PACK_FILE_FORMAT:
        raise InterviewPackError(f'This is not an Articulate interview pack (expected "format": "{PACK_FILE_FORMAT}").')
    if raw.get("format_version") != PACK_FILE_FORMAT_VERSION:
        raise InterviewPackError(
            f"Unsupported pack format_version {raw.get('format_version')!r}; "
            f"this app reads version {PACK_FILE_FORMAT_VERSION}."
        )
    try:
        pack_file = PackFile.model_validate(raw)
    except ValidationError as exc:
        raise InterviewPackError(_format_validation_error(exc)) from exc
    _check_unique_ids(pack_file)
    return pack_file


def _pack_query():
    questions = selectinload(InterviewPack.questions)
    return (
        select(InterviewPack)
        .options(
            questions.selectinload(InterviewQuestion.key_points),
            questions.selectinload(InterviewQuestion.misconceptions),
            selectinload(InterviewPack.glossary_terms),
            selectinload(InterviewPack.sources),
        )
        .execution_options(populate_existing=True)
    )


async def load_pack(session: AsyncSession, pack_id: int) -> Optional[InterviewPack]:
    return (await session.execute(_pack_query().where(InterviewPack.id == pack_id))).scalar_one_or_none()


async def load_pack_by_uid(session: AsyncSession, uid: str) -> Optional[InterviewPack]:
    return (await session.execute(_pack_query().where(InterviewPack.uid == uid))).scalar_one_or_none()


async def load_question_family(session: AsyncSession, question_id: int) -> list[InterviewQuestion]:
    """The question plus its direct follow-ups, with key points and misconceptions loaded."""
    result = await session.execute(
        select(InterviewQuestion)
        .where((InterviewQuestion.id == question_id) | (InterviewQuestion.parent_question_id == question_id))
        .options(selectinload(InterviewQuestion.key_points), selectinload(InterviewQuestion.misconceptions))
        .execution_options(populate_existing=True)
    )
    return list(result.scalars().all())


def _ordered(questions: Iterable[InterviewQuestion]) -> list[InterviewQuestion]:
    return sorted(questions, key=lambda q: (q.position, q.id or 0))


def top_level_questions(pack: InterviewPack) -> list[InterviewQuestion]:
    return _ordered(q for q in pack.questions if q.parent_question_id is None and not q.retired)


def follow_ups_of(questions: Iterable[InterviewQuestion], parent_id: int) -> list[InterviewQuestion]:
    return _ordered(q for q in questions if q.parent_question_id == parent_id and not q.retired)


class SourceQuoteChecker:
    def __init__(self, contents: Iterable[str]) -> None:
        self._indexes = [QuoteIndex(content) for content in contents if content]

    def verify(self, quote: Optional[str]) -> Optional[bool]:
        if not quote:
            return None
        return any(index.contains(quote) for index in self._indexes)


def _clean_quote(quote: Optional[str]) -> Optional[str]:
    return (quote or "").strip() or None


async def verify_source_quotes(sources: Iterable[InterviewSource], quotes: Iterable[Optional[str]]) -> dict[str, bool]:
    """Whether each quote is found in any source, computed off the event loop because large sources are slow."""
    wanted = {quote for quote in map(_clean_quote, quotes) if quote}
    if not wanted:
        return {}
    contents = [source.content for source in sources]

    def verify_all() -> dict[str, bool]:
        checker = SourceQuoteChecker(contents)
        return {quote: bool(checker.verify(quote)) for quote in wanted}

    return await asyncio.to_thread(verify_all)


def _payload_quotes(payloads: Iterable[InterviewQuestionUpsert]) -> list[Optional[str]]:
    return [
        key_point.source_quote
        for payload in payloads
        for item in (payload, *payload.follow_ups)
        for key_point in item.key_points
    ]


def question_skills(text: str, key_points: Sequence[InterviewKeyPointIn]) -> list[str]:
    """
    The technologies a question is about, read from its own words and its answer key.

    Derived rather than authored, so every question carries them without a coach having
    to fill a field, and so the same text always produces the same tags.
    """
    return find_skills(" ".join([text, *(key_point.text for key_point in key_points)]))

class _UidPool:
    def __init__(self, used: Iterable[str]) -> None:
        self._used = set(used)

    def claim(self, requested: Optional[str]) -> str:
        uid = requested if requested and requested not in self._used else new_uid()
        self._used.add(uid)
        return uid


@dataclass
class _PackWriter:
    session: AsyncSession
    pack: InterviewPack
    verified_quotes: dict[str, bool]
    question_uids: _UidPool
    key_point_uids: _UidPool
    misconception_uids: _UidPool

    @classmethod
    async def for_pack(
        cls, session: AsyncSession, pack: InterviewPack, payloads: Sequence[InterviewQuestionUpsert]
    ) -> "_PackWriter":
        """A writer for payloads whose source quotes are checked against the pack's current sources."""
        return cls(
            session=session,
            pack=pack,
            verified_quotes=await verify_source_quotes(pack.sources, _payload_quotes(payloads)),
            question_uids=_UidPool(q.uid for q in pack.questions),
            key_point_uids=_UidPool(kp.uid for q in pack.questions for kp in q.key_points),
            misconception_uids=_UidPool(m.uid for q in pack.questions for m in q.misconceptions),
        )

    def _sync_key_points(self, question: InterviewQuestion, items: Sequence[InterviewKeyPointIn]) -> dict[str, str]:
        """Upsert key points by uid, delete the rest; returns requested uid -> stored uid."""
        existing = {kp.uid: kp for kp in question.key_points}
        kept: set[str] = set()
        uid_map: dict[str, str] = {}
        for position, item in enumerate(items):
            key_point = existing.get(item.uid) if item.uid and item.uid not in kept else None
            if key_point is None:
                key_point = InterviewKeyPoint(uid=self.key_point_uids.claim(item.uid))
                question.key_points.append(key_point)
            key_point.text = item.text.strip()
            key_point.weight = item.weight
            key_point.source_quote = _clean_quote(item.source_quote)
            key_point.quote_verified = (
                None if key_point.source_quote is None else self.verified_quotes.get(key_point.source_quote, False)
            )
            key_point.approved = item.approved
            key_point.position = position
            kept.add(key_point.uid)
            if item.uid:
                uid_map[item.uid] = key_point.uid
        for key_point in list(question.key_points):
            if key_point.uid not in kept:
                question.key_points.remove(key_point)
        return uid_map

    def _sync_misconceptions(self, question: InterviewQuestion, items: Sequence[InterviewMisconceptionIn]) -> None:
        existing = {m.uid: m for m in question.misconceptions}
        kept: set[str] = set()
        for item in items:
            misconception = existing.get(item.uid) if item.uid and item.uid not in kept else None
            if misconception is None:
                misconception = InterviewMisconception(uid=self.misconception_uids.claim(item.uid))
                question.misconceptions.append(misconception)
            misconception.text = item.text.strip()
            misconception.correction = item.correction.strip()
            kept.add(misconception.uid)
        for misconception in list(question.misconceptions):
            if misconception.uid not in kept:
                question.misconceptions.remove(misconception)

    def _new_question(self, requested_uid: Optional[str]) -> InterviewQuestion:
        question = InterviewQuestion(
            uid=self.question_uids.claim(requested_uid),
            pack_id=self.pack.id,
            text="",
            key_points=[],
            misconceptions=[],
        )
        self.session.add(question)
        return question

    async def write_question(
        self,
        question: Optional[InterviewQuestion],
        requested_uid: Optional[str],
        payload: InterviewQuestionUpsert,
        position: int,
        follow_up_candidates: dict[str, InterviewQuestion],
    ) -> InterviewQuestion:
        """
        Create or update a top-level question with its key points, misconceptions and follow-ups.

        follow_up_candidates: existing questions (by uid) that a payload follow-up may update;
        existing follow-ups of this question that the payload leaves out are retired.
        """
        if question is None:
            question = self._new_question(requested_uid)
        question.parent_question_id = None
        question.trigger_key_point_uid = None
        question.retired = False
        question.topic = payload.topic.strip()
        question.kind = payload.kind
        question.text = payload.text.strip()
        question.tags = json.dumps(question_skills(payload.text, payload.key_points))
        question.answer_seconds = payload.answer_seconds
        question.position = position
        key_point_uid_map = self._sync_key_points(question, payload.key_points)
        self._sync_misconceptions(question, payload.misconceptions)
        await self.session.flush()

        own_key_point_uids = {kp.uid for kp in question.key_points}
        kept_follow_up_ids: set[int] = set()
        for follow_up_position, item in enumerate(payload.follow_ups):
            follow_up = follow_up_candidates.get(item.uid) if item.uid else None
            if follow_up is None or follow_up.id in kept_follow_up_ids or follow_up.id == question.id:
                follow_up = self._new_question(item.uid)
            trigger = key_point_uid_map.get(item.trigger_key_point_uid or "", item.trigger_key_point_uid)
            follow_up.parent_question_id = question.id
            follow_up.trigger_key_point_uid = trigger if trigger in own_key_point_uids else None
            follow_up.retired = False
            follow_up.topic = question.topic
            follow_up.kind = question.kind
            follow_up.text = item.text.strip()
            follow_up.tags = json.dumps(question_skills(item.text, item.key_points))
            follow_up.answer_seconds = item.answer_seconds
            follow_up.position = follow_up_position
            self._sync_key_points(follow_up, item.key_points)
            self._sync_misconceptions(follow_up, item.misconceptions)
            await self.session.flush()
            kept_follow_up_ids.add(follow_up.id)

        children = await self.session.execute(
            select(InterviewQuestion).where(
                InterviewQuestion.parent_question_id == question.id, InterviewQuestion.retired.is_(False)
            )
        )
        for child in children.scalars().all():
            if child.id not in kept_follow_up_ids:
                child.retired = True
        return question

    async def write_follow_up_only(self, question: InterviewQuestion, payload: InterviewQuestionUpsert) -> None:
        question.text = payload.text.strip()
        question.tags = json.dumps(question_skills(payload.text, payload.key_points))
        question.answer_seconds = payload.answer_seconds
        self._sync_key_points(question, payload.key_points)
        self._sync_misconceptions(question, payload.misconceptions)
        await self.session.flush()


def touch(pack: InterviewPack) -> None:
    pack.updated_at = utc_now()


async def refresh_quote_verification(pack: InterviewPack) -> None:
    """Re-check every key point's source quote after the pack's sources changed."""
    key_points = [key_point for question in pack.questions for key_point in question.key_points]
    verified = await verify_source_quotes(pack.sources, (key_point.source_quote for key_point in key_points))
    for key_point in key_points:
        quote = _clean_quote(key_point.source_quote)
        key_point.quote_verified = None if quote is None else verified.get(quote, False)


def _next_position(pack: InterviewPack) -> int:
    return max((q.position for q in pack.questions if q.parent_question_id is None), default=-1) + 1


async def create_questions(
    session: AsyncSession, pack: InterviewPack, payloads: Sequence[InterviewQuestionUpsert]
) -> list[int]:
    """Append new top-level questions to the pack; returns their ids in order."""
    writer = await _PackWriter.for_pack(session, pack, payloads)
    first_position = _next_position(pack)
    created = []
    for offset, payload in enumerate(payloads):
        question = await writer.write_question(None, None, payload, first_position + offset, {})
        created.append(question.id)
    touch(pack)
    return created


async def update_question(
    session: AsyncSession, pack: InterviewPack, question: InterviewQuestion, payload: InterviewQuestionUpsert
) -> None:
    writer = await _PackWriter.for_pack(session, pack, [payload])
    if question.parent_question_id is not None:
        if payload.follow_ups:
            raise InterviewPackError("Follow-up questions cannot have their own follow-ups.")
        await writer.write_follow_up_only(question, payload)
    else:
        children = {q.uid: q for q in pack.questions if q.parent_question_id == question.id}
        await writer.write_question(question, question.uid, payload, question.position, children)
    touch(pack)


def retire_question(pack: InterviewPack, question: InterviewQuestion) -> None:
    question.retired = True
    for child in pack.questions:
        if child.parent_question_id == question.id:
            child.retired = True
    touch(pack)


def _key_point_in(item: PackFileKeyPoint) -> InterviewKeyPointIn:
    return InterviewKeyPointIn(
        uid=item.id, text=item.text, weight=item.weight, source_quote=item.source_quote, approved=item.approved
    )


def _misconception_in(item: PackFileMisconception) -> InterviewMisconceptionIn:
    return InterviewMisconceptionIn(uid=item.id, text=item.text, correction=item.correction)


def _question_upsert(item: PackFileQuestion) -> InterviewQuestionUpsert:
    return InterviewQuestionUpsert(
        topic=item.topic,
        kind=item.kind,
        text=item.text,
        answer_seconds=item.answer_seconds,
        key_points=[_key_point_in(kp) for kp in item.key_points],
        misconceptions=[_misconception_in(m) for m in item.misconceptions],
        follow_ups=[
            InterviewFollowUpIn(
                uid=follow_up.id,
                text=follow_up.text,
                answer_seconds=follow_up.answer_seconds,
                trigger_key_point_uid=follow_up.trigger_key_point_id,
                key_points=[_key_point_in(kp) for kp in follow_up.key_points],
                misconceptions=[_misconception_in(m) for m in follow_up.misconceptions],
            )
            for follow_up in item.follow_ups
        ],
    )


async def import_pack(session: AsyncSession, pack_file: PackFile) -> int:
    """
    Create the pack, or update it in place when its uid already exists; returns the pack id.

    Items are matched by uid. Questions missing from the file are retired (their answers stay),
    key points and misconceptions missing from the file are deleted, the glossary is replaced
    and sources are upserted.
    """
    meta = pack_file.pack
    pack = await load_pack_by_uid(session, meta.id) if meta.id else None
    if pack is None:
        pack = InterviewPack(uid=meta.id or new_uid(), questions=[], glossary_terms=[], sources=[])
        session.add(pack)
    pack.title = meta.title.strip()
    pack.role = meta.role
    pack.level = meta.level
    pack.author = meta.author.strip()
    pack.job_description = meta.job_description
    pack.version = meta.version
    touch(pack)

    source_uids = _UidPool(source.uid for source in pack.sources)
    sources_by_uid = {source.uid: source for source in pack.sources}
    for item in pack_file.sources:
        source = sources_by_uid.get(item.id) if item.id else None
        if source is None:
            source = InterviewSource(uid=source_uids.claim(item.id))
            pack.sources.append(source)
        source.title = item.title.strip()
        source.url = item.url
        source.content = item.content

    pack.glossary_terms.clear()
    for term in pack_file.glossary:
        pack.glossary_terms.append(InterviewGlossaryTerm(term=term.term.strip(), aliases=clean_aliases(term.aliases)))
    await session.flush()

    existing_questions = list(pack.questions)
    by_uid = {q.uid: q for q in existing_questions}
    payloads = [_question_upsert(item) for item in pack_file.questions]
    writer = await _PackWriter.for_pack(session, pack, payloads)
    kept_ids: set[int] = set()
    for position, (item, payload) in enumerate(zip(pack_file.questions, payloads)):
        existing = by_uid.get(item.id) if item.id else None
        if existing is not None and existing.id in kept_ids:
            existing = None
        question = await writer.write_question(existing, item.id, payload, position, by_uid)
        kept_ids.add(question.id)
        kept_ids.update(fu.id for fu in by_uid.values() if fu.parent_question_id == question.id and not fu.retired)

    for question in existing_questions:
        if question.id not in kept_ids:
            question.retired = True
    await session.flush()
    return pack.id


def export_pack(pack: InterviewPack) -> PackFile:
    def key_points(question: InterviewQuestion) -> list[PackFileKeyPoint]:
        return [
            PackFileKeyPoint(
                id=kp.uid, text=kp.text, weight=kp.weight, source_quote=kp.source_quote, approved=kp.approved
            )
            for kp in sorted(question.key_points, key=lambda kp: kp.position)
        ]

    def misconceptions(question: InterviewQuestion) -> list[PackFileMisconception]:
        return [PackFileMisconception(id=m.uid, text=m.text, correction=m.correction) for m in question.misconceptions]

    return PackFile(
        format=PACK_FILE_FORMAT,
        format_version=PACK_FILE_FORMAT_VERSION,
        pack=PackFileMeta(
            id=pack.uid,
            title=pack.title,
            role=pack.role,
            level=pack.level,
            version=pack.version,
            author=pack.author,
            job_description=pack.job_description,
        ),
        glossary=[PackFileGlossaryTerm(term=t.term, aliases=aliases_of(t)) for t in pack.glossary_terms],
        sources=[PackFileSource(id=s.uid, title=s.title, url=s.url, content=s.content) for s in pack.sources],
        questions=[
            PackFileQuestion(
                id=question.uid,
                topic=question.topic,
                kind=question.kind,
                text=question.text,
                answer_seconds=question.answer_seconds,
                key_points=key_points(question),
                misconceptions=misconceptions(question),
                follow_ups=[
                    PackFileFollowUp(
                        id=follow_up.uid,
                        text=follow_up.text,
                        answer_seconds=follow_up.answer_seconds,
                        trigger_key_point_id=follow_up.trigger_key_point_uid,
                        key_points=key_points(follow_up),
                        misconceptions=misconceptions(follow_up),
                    )
                    for follow_up in follow_ups_of(pack.questions, question.id)
                ],
            )
            for question in top_level_questions(pack)
        ],
    )


async def build_report(session: AsyncSession, pack: InterviewPack) -> dict:
    """Graded answers per question, for the coach who prepared the pack."""
    question_ids = [q.id for q in pack.questions]
    answers_by_question: dict[int, list[InterviewAnswer]] = defaultdict(list)
    if question_ids:
        result = await session.execute(
            select(InterviewAnswer)
            .where(InterviewAnswer.question_id.in_(question_ids), InterviewAnswer.status == "graded")
            .order_by(InterviewAnswer.created_at, InterviewAnswer.id)
        )
        for answer in result.scalars().all():
            answers_by_question[answer.question_id].append(answer)

    uid_by_id = {q.id: q.uid for q in pack.questions}
    ordered: list[InterviewQuestion] = []
    for question in _ordered(q for q in pack.questions if q.parent_question_id is None):
        ordered.append(question)
        ordered.extend(_ordered(q for q in pack.questions if q.parent_question_id == question.id))

    return {
        "format": "articulate-interview-report",
        "generated_at": utc_now().isoformat() + "Z",
        "pack": {
            "id": pack.uid,
            "title": pack.title,
            "role": pack.role,
            "level": pack.level,
            "version": pack.version,
            "author": pack.author,
        },
        "questions": [
            {
                "id": question.uid,
                "parent_id": uid_by_id.get(question.parent_question_id),
                "topic": question.topic,
                "text": question.text,
                "retired": question.retired,
                "answers": [
                    {
                        "created_at": answer.created_at.isoformat() if answer.created_at else None,
                        "transcript": answer.transcript,
                        "transcript_edited": answer.transcript_edited,
                        "content_score": answer.content_score,
                        "content_band": answer.content_band,
                        "delivery_score": answer.delivery_score,
                        "key_point_results": _json_list(answer.key_point_results),
                        "misconceptions_found": _json_list(answer.misconceptions_found),
                    }
                    for answer in answers_by_question[question.id]
                ],
            }
            for question in ordered
            if not question.retired or answers_by_question[question.id]
        ],
    }


def _json_list(raw: Optional[str]) -> list:
    value = json_or(raw, [])
    return value if isinstance(value, list) else []


@dataclass
class _QuestionStats:
    graded_count: int = 0
    latest_content_score: Optional[int] = None
    latest_delivery_score: Optional[int] = None


async def _question_stats(session: AsyncSession, question_ids: Sequence[int]) -> dict[int, _QuestionStats]:
    stats: dict[int, _QuestionStats] = defaultdict(_QuestionStats)
    if not question_ids:
        return stats
    rows = await session.execute(
        select(InterviewAnswer.question_id, InterviewAnswer.content_score, InterviewAnswer.delivery_score)
        .where(InterviewAnswer.question_id.in_(question_ids), InterviewAnswer.status == "graded")
        .order_by(InterviewAnswer.created_at.desc(), InterviewAnswer.id.desc())
    )
    for question_id, content, delivery in rows.all():
        item = stats[question_id]
        item.graded_count += 1
        if item.latest_content_score is None:
            item.latest_content_score = content
        if item.latest_delivery_score is None:
            item.latest_delivery_score = delivery
    return stats


def _question_out(
    question: InterviewQuestion, follow_ups: Sequence[InterviewQuestion], stats: dict[int, _QuestionStats]
) -> InterviewQuestionOut:
    item = stats.get(question.id) or _QuestionStats()
    return InterviewQuestionOut(
        id=question.id,
        uid=question.uid,
        pack_id=question.pack_id,
        parent_question_id=question.parent_question_id,
        trigger_key_point_uid=question.trigger_key_point_uid,
        topic=question.topic,
        kind=question.kind,
        tags=json_or(question.tags, []),
        text=question.text,
        answer_seconds=question.answer_seconds,
        retired=question.retired,
        key_points=[
            InterviewKeyPointOut(
                id=kp.id,
                uid=kp.uid,
                text=kp.text,
                weight=kp.weight,
                source_quote=kp.source_quote,
                quote_verified=kp.quote_verified,
                approved=kp.approved,
            )
            for kp in sorted(question.key_points, key=lambda kp: kp.position)
        ],
        misconceptions=[
            InterviewMisconceptionOut(id=m.id, uid=m.uid, text=m.text, correction=m.correction)
            for m in question.misconceptions
        ],
        follow_ups=[_question_out(follow_up, [], stats) for follow_up in follow_ups],
        answer_count=item.graded_count,
        latest_content_score=item.latest_content_score,
        latest_delivery_score=item.latest_delivery_score,
    )


async def question_out(session: AsyncSession, question_id: int) -> Optional[InterviewQuestionOut]:
    family = await load_question_family(session, question_id)
    question = next((q for q in family if q.id == question_id), None)
    if question is None:
        return None
    stats = await _question_stats(session, [q.id for q in family])
    return _question_out(question, follow_ups_of(family, question.id), stats)


def _average(scores: Sequence[int]) -> Optional[float]:
    return round(sum(scores) / len(scores), 1) if scores else None


def _summary_fields(pack: InterviewPack, stats: dict[int, _QuestionStats]) -> dict:
    questions = top_level_questions(pack)
    scores = [s for q in questions if (s := stats[q.id].latest_content_score) is not None]
    return {
        "id": pack.id,
        "uid": pack.uid,
        "title": pack.title,
        "role": pack.role,
        "level": pack.level,
        "version": pack.version,
        "author": pack.author,
        "question_count": len(questions),
        "answered_question_count": len(scores),
        "average_content_score": _average(scores),
        "updated_at": pack.updated_at,
    }


async def pack_summaries(session: AsyncSession) -> list[InterviewPackSummaryOut]:
    result = await session.execute(
        select(InterviewPack)
        .where(InterviewPack.personal.is_(False))
        .options(selectinload(InterviewPack.questions))
        .order_by(InterviewPack.updated_at.desc(), InterviewPack.id.desc())
        .execution_options(populate_existing=True)
    )
    packs = list(result.scalars().all())
    stats = await _question_stats(session, [q.id for pack in packs for q in pack.questions])
    return [InterviewPackSummaryOut(**_summary_fields(pack, stats)) for pack in packs]


def source_out(source: InterviewSource) -> InterviewSourceOut:
    return InterviewSourceOut(
        id=source.id,
        uid=source.uid,
        title=source.title,
        url=source.url,
        content_length=len(source.content),
        preview=source.content[:SOURCE_PREVIEW_CHARS],
    )


def glossary_out(terms: Iterable[InterviewGlossaryTerm]) -> list[InterviewGlossaryTermOut]:
    return [InterviewGlossaryTermOut(id=t.id, term=t.term, aliases=aliases_of(t)) for t in terms]


async def pack_detail(session: AsyncSession, pack_id: int) -> Optional[InterviewPackDetailOut]:
    pack = await load_pack(session, pack_id)
    if pack is None:
        return None
    stats = await _question_stats(session, [q.id for q in pack.questions])
    questions = top_level_questions(pack)

    by_topic: dict[str, list[InterviewQuestion]] = defaultdict(list)
    for question in questions:
        by_topic[question.topic].append(question)
    topics = []
    for topic, topic_questions in by_topic.items():
        scores = [s for q in topic_questions if (s := stats[q.id].latest_content_score) is not None]
        topics.append(
            InterviewTopicReadiness(
                topic=topic,
                question_count=len(topic_questions),
                graded_count=len(scores),
                average_content_score=_average(scores),
            )
        )

    return InterviewPackDetailOut(
        **_summary_fields(pack, stats),
        job_description=pack.job_description,
        glossary=glossary_out(pack.glossary_terms),
        sources=[source_out(source) for source in sorted(pack.sources, key=lambda s: s.id)],
        questions=[_question_out(q, follow_ups_of(pack.questions, q.id), stats) for q in questions],
        topics=topics,
    )


def _draft_key_points(items: object) -> list[InterviewKeyPointIn]:
    key_points = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or not str(item.get("text") or "").strip():
            continue
        key_points.append(
            InterviewKeyPointIn(
                uid=new_uid(),
                text=str(item["text"]).strip()[:KEY_POINT_TEXT_MAX],
                weight=interview_prompts.WEIGHT_BY_IMPORTANCE.get(str(item.get("importance")), 2),
                source_quote=str(item.get("source_quote") or "").strip()[:SOURCE_QUOTE_MAX] or None,
                approved=False,
            )
        )
    return key_points[:MAX_KEY_POINTS]


def _draft_misconceptions(items: object) -> list[InterviewMisconceptionIn]:
    return [
        InterviewMisconceptionIn(
            text=str(item["text"]).strip()[:MISCONCEPTION_TEXT_MAX],
            correction=str(item.get("correction") or "").strip()[:MISCONCEPTION_TEXT_MAX],
        )
        for item in (items if isinstance(items, list) else [])
        if isinstance(item, dict) and str(item.get("text") or "").strip()
    ][:MAX_MISCONCEPTIONS]


def _answer_seconds(value: object, default: int) -> int:
    if not isinstance(value, int) or value <= 0:
        return default
    return min(max(value, ANSWER_SECONDS_MIN), ANSWER_SECONDS_MAX)


def _draft_question_upsert(topic: str, item: dict) -> InterviewQuestionUpsert:
    key_points = _draft_key_points(item.get("key_points"))
    follow_ups = []
    for follow_up in item.get("follow_ups") if isinstance(item.get("follow_ups"), list) else []:
        if not isinstance(follow_up, dict) or not str(follow_up.get("text") or "").strip():
            continue
        index = follow_up.get("trigger_key_point_index")
        trigger = key_points[index].uid if isinstance(index, int) and 0 <= index < len(key_points) else None
        follow_ups.append(
            InterviewFollowUpIn(
                text=str(follow_up["text"]).strip()[:QUESTION_TEXT_MAX],
                answer_seconds=_answer_seconds(follow_up.get("answer_seconds"), DEFAULT_FOLLOW_UP_SECONDS),
                trigger_key_point_uid=trigger,
                key_points=_draft_key_points(follow_up.get("key_points")),
                misconceptions=_draft_misconceptions(follow_up.get("misconceptions")),
            )
        )
    return InterviewQuestionUpsert(
        topic=topic,
        text=str(item.get("text") or "").strip()[:QUESTION_TEXT_MAX],
        answer_seconds=_answer_seconds(item.get("answer_seconds"), DEFAULT_QUESTION_SECONDS),
        key_points=key_points,
        misconceptions=_draft_misconceptions(item.get("misconceptions")),
        follow_ups=follow_ups[:MAX_FOLLOW_UPS],
    )


def _draft_sources_text(sources: Sequence[InterviewSource]) -> str:
    text = "\n\n".join(f"[Source: {source.title}]\n{source.content}" for source in sources)
    return text[:DRAFT_SOURCES_CHAR_LIMIT]


def _existing_question_texts(pack: InterviewPack) -> list[str]:
    texts, used = [], 0
    for question in _ordered(q for q in pack.questions if not q.retired):
        used += len(question.text)
        if used > DRAFT_EXISTING_QUESTIONS_CHAR_LIMIT:
            break
        texts.append(question.text)
    return texts


async def draft_questions(session: AsyncSession, pack: InterviewPack, request: InterviewDraftRequest) -> list[int]:
    """
    Ask the drafter LLM for new questions and save them with unapproved key points.

    Returns the new question ids. Raises InterviewPackError for unknown sources and the
    llm_client errors (LLMRateLimitError, LLMOutputError, RuntimeError) for LLM failures.
    """
    settings = get_settings()
    sources_by_id = {source.id: source for source in pack.sources}
    unknown = [source_id for source_id in request.source_ids if source_id not in sources_by_id]
    if unknown:
        raise InterviewPackError(f"Unknown source id(s) for this pack: {unknown}.")
    topic = request.topic.strip()
    prompt = interview_prompts.build_draft_prompt(
        role=pack.role,
        level=pack.level,
        job_description=pack.job_description,
        topic=topic,
        count=request.count,
        sources=_draft_sources_text([sources_by_id[source_id] for source_id in request.source_ids]),
        existing_questions=_existing_question_texts(pack),
    )
    output = await llm_client.generate_json(
        base_url=settings.llm_base_url,
        model=settings.interview_drafter_model,
        prompt=prompt,
        api_key=settings.llm_api_key,
        schema=interview_prompts.DRAFT_SCHEMA,
        schema_name="interview_question_draft",
        temperature=0.3,
        max_tokens=16384,
        timeout=150.0,
    )

    payloads: list[InterviewQuestionUpsert] = []
    for item in output.get("questions") if isinstance(output.get("questions"), list) else []:
        if not isinstance(item, dict):
            continue
        try:
            payloads.append(_draft_question_upsert(topic, item))
        except ValidationError as exc:
            logger.warning("Skipping drafted question that failed validation: %s", exc)
    if not payloads:
        raise llm_client.LLMOutputError("The drafter returned no usable questions.")

    return await create_questions(session, pack, payloads[: request.count])


def _introduction_upsert(item: dict) -> Optional[InterviewQuestionUpsert]:
    """
    One behavioural question with its key points approved as written.

    A technical answer key waits for a coach, who knows the subject better than the
    candidate. This one is about the candidate's own history, so they are the reviewer,
    and the question is practisable the moment it is written.
    """
    text = str(item.get("text") or "").strip()[:QUESTION_TEXT_MAX]
    key_points = []
    for point in item.get("key_points") if isinstance(item.get("key_points"), list) else []:
        if not isinstance(point, dict):
            continue
        point_text = str(point.get("text") or "").strip()[:KEY_POINT_TEXT_MAX]
        if not point_text:
            continue
        weight = interview_prompts.WEIGHT_BY_IMPORTANCE.get(str(point.get("importance")), 2)
        key_points.append(InterviewKeyPointIn(text=point_text, weight=weight, approved=True))
    if not text or len(key_points) < INTRODUCTION_MIN_KEY_POINTS:
        return None
    return InterviewQuestionUpsert(
        topic=INTRODUCTION_TOPIC,
        kind="behavioural",
        text=text,
        answer_seconds=max(
            INTRODUCTION_MIN_SECONDS, _answer_seconds(item.get("answer_seconds"), INTRODUCTION_MIN_SECONDS)
        ),
        key_points=key_points,
    )


async def load_personal_pack(session: AsyncSession) -> Optional[InterviewPack]:
    result = await session.execute(_pack_query().where(InterviewPack.personal.is_(True)))
    return result.scalars().first()


async def load_or_create_personal_pack(session: AsyncSession, profile: CandidateProfile) -> InterviewPack:
    """
    The candidate's own questionnaire, which holds the questions about them.

    It is kept out of the questionnaire list, because that list is client work and this
    one belongs to the person practising.
    """
    pack = await load_personal_pack(session)
    if pack is not None:
        return pack
    pack = InterviewPack(
        uid=new_uid(),
        title=PERSONAL_PACK_TITLE,
        role="other",
        level="mid",
        job_description="",
        author=profile.full_name.strip(),
        version=1,
        personal=True,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(pack)
    await session.flush()
    await session.refresh(pack, ["questions", "sources", "glossary_terms"])
    return pack


async def draft_introduction(
    session: AsyncSession,
    pack: InterviewPack,
    profile: CandidateProfile,
    job: Optional[InterviewPack] = None,
    count: int = INTRODUCTION_COUNT,
) -> list[int]:
    """
    Add the opening "introduce yourself" question, keyed to the CV.

    job is the client questionnaire the candidate is preparing for, when they picked one:
    only its role, level and job description are read, so the question can ask them to
    connect their own history to what that client wants.

    The CV is sent to the drafter and nothing else keeps it: it is never written into the
    questionnaire, so exporting the file does not carry the candidate's history with it.
    """
    aimed_at = job or pack
    cv = profile.cv_text.strip()
    if len(cv) < INTRODUCTION_MIN_CV_CHARS:
        raise InterviewPackError(
            f"Add your CV first. It has {len(cv)} characters and at least "
            f"{INTRODUCTION_MIN_CV_CHARS} are needed to write an answer key from."
        )
    settings = get_settings()
    prompt = interview_prompts.build_introduction_prompt(
        role=aimed_at.role,
        level=aimed_at.level,
        cv=cv[:CV_CHAR_LIMIT],
        job_description=aimed_at.job_description,
        count=count,
    )
    output = await llm_client.generate_json(
        base_url=settings.llm_base_url,
        model=settings.interview_drafter_model,
        prompt=prompt,
        api_key=settings.llm_api_key,
        schema=interview_prompts.introduction_schema(),
        schema_name="interview_introduction",
        temperature=0.3,
        max_tokens=8192,
        timeout=150.0,
    )

    payloads = []
    for item in output.get("questions") if isinstance(output.get("questions"), list) else []:
        if not isinstance(item, dict):
            continue
        try:
            upsert = _introduction_upsert(item)
        except ValidationError as exc:
            logger.warning("Skipping introduction question that failed validation: %s", exc)
            continue
        if upsert is not None:
            payloads.append(upsert)
    logger.info("INTERVIEW INTRODUCTION: cv=%d chars, asked for %d, kept %d", len(cv), count, len(payloads))
    if not payloads:
        raise llm_client.LLMOutputError("The drafter returned no usable question. Add more detail to your CV.")

    return await create_questions(session, pack, payloads[:count])

async def seed_sample_packs(session: AsyncSession, packs_dir: Path = SEED_PACKS_DIR) -> None:
    """Import bundled sample packs whose uid is not in the database yet (additive; never overwrites)."""
    if not packs_dir.is_dir():
        return
    for path in sorted(packs_dir.glob("*.json")):
        try:
            pack_file = parse_pack_bytes(path.read_bytes())
        except (OSError, InterviewPackError) as exc:
            logger.warning("Skipping sample interview pack %s: %s", path.name, exc)
            continue
        if not pack_file.pack.id:
            logger.warning("Skipping sample interview pack %s: pack.id is required for seeding.", path.name)
            continue
        existing = await session.execute(select(InterviewPack.id).where(InterviewPack.uid == pack_file.pack.id))
        if existing.scalar_one_or_none() is not None:
            continue
        try:
            await import_pack(session, pack_file)
            await session.commit()
            logger.info("Seeded sample interview pack %s (%s).", pack_file.pack.title, path.name)
        except Exception as exc:
            await session.rollback()
            logger.warning("Could not seed sample interview pack %s: %s", path.name, exc)
