"""Interview answer pipeline: transcription and delivery on upload, then evidence-checked content grading."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import time
from collections import Counter
from datetime import datetime, timedelta
from typing import Callable, Iterable, Optional, Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import Settings, get_settings
from backend.database import AsyncSessionLocal
from backend.models import (
    InterviewAnswer,
    InterviewGlossaryTerm,
    InterviewKeyPoint,
    InterviewMisconception,
    InterviewPack,
    InterviewQuestion,
)
from backend.schemas import (
    InterviewAnswerOut,
    InterviewDeliveryOut,
    InterviewFeedbackOut,
    InterviewGlossaryCorrectionOut,
    InterviewKeyPointResultOut,
    InterviewMisconceptionResultOut,
    InterviewSentenceFixOut,
)
from backend.services import grammar as grammar_service
from backend.services import interview_prompts, llm_client
from backend.services import transcription as transcription_service
from backend.services.interview_delivery import compute_delivery
from backend.services.interview_glossary import apply_corrections, correct_transcript
from backend.services.interview_packs import glossary_entries, json_or, load_question_family, utc_now
from backend.services.interview_scoring import (
    VERDICT_CREDIT,
    FollowUpOption,
    QuoteIndex,
    apply_quote_rules,
    choose_follow_up,
    content_score,
    merge_verdict,
)
from backend.services.llm_client import LLMOutputError, LLMRateLimitError
from backend.services.sentences import find_span, weak_sentences

logger = logging.getLogger(__name__)

TRANSCRIPTION_TIMEOUT_SECONDS = 120.0
GRAMMAR_TIMEOUT_SECONDS = 30.0
STALE_AFTER = timedelta(minutes=10)
# Below STALE_AFTER, so a run that an answer list already reported as failed can no longer be running.
GRADING_TIMEOUT = timedelta(minutes=8)
MIN_WORDS_TO_GRADE = 15
MAX_CONTENT_TIPS = 3
# Groq's free tier counts prompt + max_tokens against one per-minute budget and rejects
# the request outright when the pair exceeds it, so a long transcript buys a shorter reply.
GROQ_FREE_TIER_TOKENS_PER_MINUTE = 8000
MIN_VERIFIER_MAX_TOKENS = 512
# Four characters per token is an average rather than a worst case, and Groq also counts the
# JSON schema and the message envelope, neither of which is part of the prompt string.
VERIFIER_CHARS_PER_TOKEN = 3.5
VERIFIER_REQUEST_OVERHEAD_TOKENS = 400
GRADEABLE_STATUSES = frozenset({"needs_review", "graded", "pending_quota", "failed:grading"})
RETRY_STATUSES = frozenset({"pending_quota", "failed:grading"})

NO_APPROVED_KEY_POINTS_MESSAGE = (
    "This question has no approved key points yet, so the content cannot be graded. "
    "Ask your coach to approve its answer key in Pack Studio."
)
TOO_SHORT_MESSAGE = f"Answer too short to grade (fewer than {MIN_WORDS_TO_GRADE} words)."
GRADER_QUOTA_MESSAGE = "The Gemini grader is out of free-tier quota for now. Your answer is saved; retry grading later."
VERIFIER_QUOTA_MESSAGE = (
    "The Groq verifier is out of free-tier quota for now. Your answer is saved; retry grading later."
)
VERIFIER_DOWNGRADE_REASONS = {
    "partial": "An independent check found that this only partly states the point.",
    "missing": "An independent check found that this does not actually state the point.",
    "incorrect": "An independent check found that this contradicts the point.",
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _anchor_grammar_issues(delivery: dict, transcript: Optional[str]) -> None:
    """Re-point each grammar issue at the transcript the UI will display.

    Grammar runs on the raw transcript, which glossary corrections and the candidate's
    own edits then change, so a stored offset can land mid-word or past the end. Each
    issue is relocated to the occurrence of its own phrase nearest the stored offset;
    one that no longer appears gets a null offset and simply is not highlighted.
    """
    issues = delivery.get("grammar_issues")
    if not transcript or not isinstance(issues, list):
        return
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        span = find_span(transcript, str(issue.get("text") or ""), issue.get("offset"), whole_word=True)
        issue["offset"] = span[0] if span else None


def _grammar_offsets(delivery: object, transcript: str) -> list[int]:
    issues = delivery.get("grammar_issues") if isinstance(delivery, dict) else None
    offsets = []
    for issue in issues or []:
        if not isinstance(issue, dict):
            continue
        span = find_span(transcript, str(issue.get("text") or ""), issue.get("offset"), whole_word=True)
        if span is not None:
            offsets.append(span[0])
    return offsets


def sentence_fix_rows(answer: InterviewAnswer, transcript: str) -> list[dict]:
    """The sentences worth rewriting, with an empty rewrite until one is asked for.

    Picking them is free and deterministic, so it happens on every grade; only filling
    in `improved` costs a model call, which the candidate triggers themselves.
    """
    offsets = _grammar_offsets(json_or(answer.delivery_details, None), transcript)
    return [
        {"original": sentence["text"], "improved": "", "note": "", "reasons": sentence["reasons"]}
        for sentence in weak_sentences(transcript, offsets)
    ]


def sentence_fixes_for(answer: InterviewAnswer) -> list[dict]:
    """Stored rows, or freshly picked ones for an answer graded before this existed.

    A null column means the sentences were never picked, which is not the same as an
    answer with nothing to tighten, so it is recomputed rather than read as empty.
    """
    if answer.sentence_fixes is not None:
        return json_or(answer.sentence_fixes, [])
    transcript = (answer.transcript or "").strip()
    if not transcript:
        return []
    return sentence_fix_rows(answer, transcript)


def answer_out(answer: InterviewAnswer) -> InterviewAnswerOut:
    delivery = json_or(answer.delivery_details, None)
    feedback = json_or(answer.feedback, None)
    if isinstance(delivery, dict):
        _anchor_grammar_issues(delivery, answer.transcript)
    return InterviewAnswerOut(
        id=answer.id,
        question_id=answer.question_id,
        status=answer.status,
        created_at=answer.created_at,
        graded_at=answer.graded_at,
        duration_seconds=answer.duration_seconds,
        raw_transcript=answer.raw_transcript,
        transcript=answer.transcript,
        transcript_edited=answer.transcript_edited,
        glossary_corrections=[
            InterviewGlossaryCorrectionOut(**item) for item in json_or(answer.glossary_corrections, [])
        ],
        delivery=InterviewDeliveryOut(**delivery) if isinstance(delivery, dict) else None,
        content_score=answer.content_score,
        content_band=answer.content_band,
        key_point_results=[InterviewKeyPointResultOut(**item) for item in json_or(answer.key_point_results, [])],
        misconceptions_found=[
            InterviewMisconceptionResultOut(**item) for item in json_or(answer.misconceptions_found, [])
        ],
        feedback=InterviewFeedbackOut(**feedback) if isinstance(feedback, dict) else None,
        sentence_fixes=[InterviewSentenceFixOut(**item) for item in sentence_fixes_for(answer)],
        next_follow_up_question_id=answer.next_follow_up_question_id,
        error_message=answer.error_message,
    )


def mark_stale(answers: Iterable[InterviewAnswer], now: datetime) -> bool:
    """Fail answers whose background work evidently died; returns whether any changed."""
    changed = False
    for answer in answers:
        if answer.status in ("processing", "transcribing"):
            started, failed_status = answer.created_at, "failed:transcription"
        elif answer.status == "grading":
            started, failed_status = answer.grading_started_at or answer.created_at, "failed:grading"
        else:
            continue
        if started is not None and now - started > STALE_AFTER:
            logger.warning(
                "Interview answer %d: no progress since %s (over %s), marking %s",
                answer.id,
                started,
                STALE_AFTER,
                failed_status,
            )
            answer.status = failed_status
            answer.error_message = "Processing did not finish (the app may have been closed). Please try again."
            changed = True
    return changed


def suggested_transcript(answer: InterviewAnswer) -> str:
    """The glossary-corrected transcript offered for review, before any user edits."""
    if answer.raw_transcript is None:
        return answer.transcript or ""
    return apply_corrections(answer.raw_transcript, json_or(answer.glossary_corrections, []))


async def _mark_failed(session: AsyncSession, answer_id: int, status: str, message: str) -> None:
    try:
        await session.rollback()
        answer = await session.get(InterviewAnswer, answer_id)
        if answer is not None:
            answer.status = status
            answer.error_message = message
            await session.commit()
    except Exception:
        logger.exception("Could not mark interview answer %d as %s", answer_id, status)


async def _check_grammar(text: str, ignore_terms: Sequence[str]) -> Optional[list[dict]]:
    loop = asyncio.get_running_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, grammar_service.check_grammar, text, ignore_terms),
            timeout=GRAMMAR_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.warning("Grammar check unavailable for interview answer: %r", exc)
        return None


async def process_recording(answer_id: int) -> None:
    """Background task: transcribe, suggest glossary corrections and score delivery, ending in needs_review."""
    async with AsyncSessionLocal() as session:
        answer = await session.get(InterviewAnswer, answer_id)
        if answer is None:
            logger.error("Interview answer %d not found for processing", answer_id)
            return
        t_start = time.perf_counter()
        logger.info(
            "\n\n========== INTERVIEW PIPELINE START answer_id=%d ==========\n  question_id=%d\n  audio=%s",
            answer_id,
            answer.question_id,
            answer.audio_path,
        )
        try:
            answer.status = "transcribing"
            await session.commit()
            logger.info("Interview %d: transcribing", answer_id)
            try:
                result = await asyncio.wait_for(
                    transcription_service.transcribe(answer.audio_path), timeout=TRANSCRIPTION_TIMEOUT_SECONDS
                )
            except Exception as exc:
                logger.exception("Interview answer %d: transcription failed", answer_id)
                detail = "timed out" if isinstance(exc, asyncio.TimeoutError) else str(exc)
                await _mark_failed(session, answer_id, "failed:transcription", f"Transcription failed: {detail}")
                return

            raw_transcript = (result.get("transcript") or "").strip()
            words = result.get("words") or []
            if not raw_transcript:
                logger.warning(
                    "Interview %d: empty transcript from %s (%d timed words) - failed:empty_audio",
                    answer_id,
                    answer.audio_path,
                    len(words),
                )
                await _mark_failed(session, answer_id, "failed:empty_audio", "No speech was detected in the recording.")
                return

            question = await session.get(InterviewQuestion, answer.question_id)
            terms = await session.execute(
                select(InterviewGlossaryTerm).where(InterviewGlossaryTerm.pack_id == question.pack_id)
            )
            entries = glossary_entries(terms.scalars().all())
            transcript, corrections = correct_transcript(raw_transcript, entries)
            ignore_terms = [entry.term for entry in entries] + [alias for entry in entries for alias in entry.aliases]
            delivery = compute_delivery(
                words, await _check_grammar(raw_transcript, ignore_terms), get_settings().gap_threshold
            )

            logger.info(
                "\n\n========== INTERVIEW SIGNALS answer_id=%d ==========\n"
                "  transcript : %d words, %d chars\n"
                "  glossary   : %d term(s) loaded, %d correction(s) %s\n"
                "  delivery   : score=%s wpm=%s long_pauses=%s grammar=%s lexical=%s\n"
                "  components : %s",
                answer_id,
                len(words),
                len(transcript),
                len(entries),
                len(corrections),
                [(c.get("original"), c.get("replacement")) for c in corrections[:10]],
                delivery.get("score"),
                delivery.get("words_per_minute"),
                delivery.get("long_pauses"),
                "available" if delivery.get("grammar_available") else "unavailable",
                delivery.get("lexical_diversity"),
                delivery.get("components"),
            )

            answer.raw_transcript = raw_transcript
            answer.transcript = transcript
            answer.transcript_edited = False
            answer.word_timestamps = json.dumps(words)
            answer.glossary_corrections = json.dumps(corrections)
            last_end = words[-1].get("end") if words else None
            answer.duration_seconds = float(last_end) if isinstance(last_end, (int, float)) else None
            answer.delivery_score = delivery["score"]
            answer.delivery_details = json.dumps(delivery)
            answer.status = "needs_review"
            answer.error_message = None
            await session.commit()
            logger.info(
                "Interview %d: needs_review after %.1fs (%d words, %d glossary corrections, delivery=%s)",
                answer_id,
                time.perf_counter() - t_start,
                len(words),
                len(corrections),
                delivery["score"],
            )
        except Exception as exc:
            logger.exception("Interview answer %d: processing failed", answer_id)
            await _mark_failed(session, answer_id, "failed:transcription", f"Processing the recording failed: {exc}")


def _answer_key_digest(key_points: Sequence[InterviewKeyPoint], question: InterviewQuestion) -> str:
    parts = [f"{kp.uid}|{kp.weight}|{kp.text}" for kp in key_points]
    parts += [f"{m.uid}|{m.text}" for m in question.misconceptions]
    return sha256_text("\n".join(parts))


def _judged_ids(proposal: dict, field: str, is_judged: Callable[[dict], bool]) -> Optional[Counter[str]]:
    items = proposal.get(field)
    if not isinstance(items, list) or not all(isinstance(item, dict) and is_judged(item) for item in items):
        return None
    return Counter(str(item.get("id")) for item in items)


def proposal_is_complete(proposal: dict, key_point_uids: Sequence[str], misconception_uids: Sequence[str]) -> bool:
    """Whether the grader judged every key point and every misconception exactly once."""
    key_points = _judged_ids(proposal, "key_points", lambda item: item.get("verdict") in VERDICT_CREDIT)
    misconceptions = _judged_ids(proposal, "misconceptions", lambda item: isinstance(item.get("stated"), bool))
    return key_points == Counter(key_point_uids) and misconceptions == Counter(misconception_uids)


def _reusable_proposer_output(
    answer: InterviewAnswer,
    transcript_sha: str,
    answer_key_sha: str,
    key_point_uids: Sequence[str],
    misconception_uids: Sequence[str],
) -> Optional[dict]:
    stored = json_or(answer.proposer_output, None)
    if (
        isinstance(stored, dict)
        and stored.get("transcript_sha256") == transcript_sha
        and stored.get("answer_key_sha256") == answer_key_sha
        and isinstance(stored.get("output"), dict)
        and proposal_is_complete(stored["output"], key_point_uids, misconception_uids)
    ):
        return stored["output"]
    return None


async def _propose(
    settings: Settings,
    pack: InterviewPack,
    question: InterviewQuestion,
    key_points: Sequence[InterviewKeyPoint],
    transcript: str,
) -> dict:
    shuffled = list(key_points)
    # Shuffled so the model cannot lean on the coach's ordering; seeded so a retry sends the same prompt.
    random.Random(sha256_text(transcript)).shuffle(shuffled)
    prompt = interview_prompts.build_grade_prompt(
        role=pack.role,
        level=pack.level,
        question=question.text,
        key_points=[(kp.uid, kp.weight, kp.text) for kp in shuffled],
        misconceptions=[(m.uid, m.text) for m in question.misconceptions],
        transcript=transcript,
    )
    return await llm_client.generate_json(
        base_url=settings.llm_base_url,
        model=settings.interview_grader_model,
        prompt=prompt,
        api_key=settings.llm_api_key,
        schema=interview_prompts.grade_schema([kp.uid for kp in shuffled], [m.uid for m in question.misconceptions]),
        schema_name="interview_answer_grade",
    )


def estimated_request_tokens(prompt: str) -> int:
    """Pessimistic token count for the whole verifier request, not just the prompt string."""
    return int(len(prompt) / VERIFIER_CHARS_PER_TOKEN) + VERIFIER_REQUEST_OVERHEAD_TOKENS


def verifier_max_tokens(prompt: str, configured_max: int) -> int:
    """Reply budget that keeps the estimated request plus the reply inside the free tier's per-minute limit."""
    remaining = GROQ_FREE_TIER_TOKENS_PER_MINUTE - estimated_request_tokens(prompt)
    return max(MIN_VERIFIER_MAX_TOKENS, min(configured_max, remaining))


async def _verify(
    settings: Settings,
    question: InterviewQuestion,
    transcript: str,
    key_point_claims: Sequence[tuple[str, str, str]],
    misconception_claims: Sequence[tuple[str, str, str]],
) -> dict:
    prompt = interview_prompts.build_verify_prompt(
        question=question.text,
        transcript=transcript,
        key_point_claims=key_point_claims,
        misconception_claims=misconception_claims,
    )
    max_tokens = verifier_max_tokens(prompt, settings.interview_verifier_max_tokens)
    logger.info("Interview verifier: prompt_chars=%d max_tokens=%d", len(prompt), max_tokens)
    return await llm_client.generate_json(
        base_url=settings.interview_verifier_base_url,
        model=settings.interview_verifier_model,
        prompt=prompt,
        api_key=settings.groq_api_key,
        schema=interview_prompts.verify_schema(
            [uid for uid, _, _ in key_point_claims], [uid for uid, _, _ in misconception_claims]
        ),
        schema_name="interview_claim_check",
        strict=True,
        max_tokens=max_tokens,
    )


def _items_by_id(output: dict, field: str) -> dict[str, dict]:
    items = output.get(field)
    return {
        str(item["id"]): item
        for item in (items if isinstance(items, list) else [])
        if isinstance(item, dict) and "id" in item
    }


def _ungraded(message: str) -> dict:
    return {
        "content_score": None,
        "content_band": "ungraded",
        "key_point_results": json.dumps([]),
        "misconceptions_found": json.dumps([]),
        "feedback": None,
        "next_follow_up_question_id": None,
        "error_message": message,
        "status": "graded",
        "graded_at": utc_now(),
    }


def _proposed_claims(approved: Sequence[InterviewKeyPoint], proposal: dict, index: QuoteIndex) -> list[dict]:
    proposed = _items_by_id(proposal, "key_points")
    claims = []
    for kp in approved:
        item = proposed.get(kp.uid, {})
        verdict = item.get("verdict")
        claims.append(
            {
                "verdict": verdict if verdict in VERDICT_CREDIT else "missing",
                "quote": str(item.get("quote") or ""),
                "reason": str(item.get("reason") or "").strip() or None,
            }
        )
    return apply_quote_rules(claims, index)


def _stated_misconceptions(
    question: InterviewQuestion, proposal: dict, index: QuoteIndex
) -> list[tuple[InterviewMisconception, str]]:
    """Misconceptions the grader says were stated, with the transcript words its quote matched."""
    proposed = _items_by_id(proposal, "misconceptions")
    stated = []
    for misconception in question.misconceptions:
        item = proposed.get(misconception.uid, {})
        match = index.find(item.get("quote")) if item.get("stated") is True else None
        if match is not None:
            stated.append((misconception, match.text))
    return stated


def _key_point_results(
    approved: Sequence[InterviewKeyPoint], claims: Sequence[dict], verifier_verdicts: Optional[dict[str, str]]
) -> list[dict]:
    """Final per key point results; verifier_verdicts is None when the verifier did not need to run."""
    results = []
    for kp, claim in zip(approved, claims):
        verdict, quote, reason, verifier_verdict = claim["verdict"], claim["quote"], claim["reason"], None
        if verdict != "missing" and verifier_verdicts is not None:
            # A claim the verifier skipped is treated as unsupported rather than trusted.
            verifier_verdict = verifier_verdicts.get(kp.uid, "not_supported")
            final = merge_verdict(verdict, verifier_verdict)
            if final != verdict:
                verdict, reason = final, VERIFIER_DOWNGRADE_REASONS[final]
                quote = None if final == "missing" else quote
        results.append(
            {
                "uid": kp.uid,
                "text": kp.text,
                "weight": kp.weight,
                "verdict": verdict,
                "quote": quote,
                "reason": reason,
                "verifier_verdict": verifier_verdict,
            }
        )
    return results


def _next_follow_up(
    question: InterviewQuestion, family: Sequence[InterviewQuestion], results: Sequence[dict], band: str
) -> Optional[int]:
    if question.parent_question_id is not None:
        return None
    options = [
        FollowUpOption(follow_up.id, follow_up.position, follow_up.trigger_key_point_uid)
        for follow_up in family
        if follow_up.parent_question_id == question.id
        and not follow_up.retired
        and any(kp.approved for kp in follow_up.key_points)
    ]
    return choose_follow_up(
        options, {r["uid"]: r["verdict"] for r in results}, {r["uid"]: r["weight"] for r in results}, band
    )


def _feedback(proposal: dict) -> dict:
    tips = proposal.get("content_tips")
    content_tips = [str(tip).strip() for tip in (tips if isinstance(tips, list) else []) if str(tip).strip()]
    return {
        "content_tips": content_tips[:MAX_CONTENT_TIPS],
        "english_tip": str(proposal.get("english_tip") or "").strip() or None,
    }


def _missing_api_keys(settings: Settings) -> list[str]:
    keys = (("LLM_API_KEY", settings.llm_api_key), ("GROQ_API_KEY", settings.groq_api_key))
    return [name for name, value in keys if not value]


async def claim_for_grading(
    session: AsyncSession, answer: InterviewAnswer, transcript: str, run_token: datetime
) -> bool:
    """
    Atomically move the answer from the status it was loaded with to grading, owned by run_token.

    Returns False when the status is not gradeable or changed since loading (for example a second
    grade request won). Stored grader output is kept only for a retry after a quota or grading
    failure; any other re-grade asks the grader again.
    """
    if answer.status not in GRADEABLE_STATUSES:
        return False
    values = {
        "transcript": transcript,
        "transcript_edited": transcript != suggested_transcript(answer).strip(),
        "status": "grading",
        "grading_started_at": run_token,
        "error_message": None,
        "content_score": None,
        "content_band": None,
        "key_point_results": None,
        "misconceptions_found": None,
        "feedback": None,
        "next_follow_up_question_id": None,
        "graded_at": None,
    }
    if answer.status not in RETRY_STATUSES:
        values["proposer_output"] = None
    result = await session.execute(
        update(InterviewAnswer)
        .where(InterviewAnswer.id == answer.id, InterviewAnswer.status == answer.status)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    await session.commit()
    await session.refresh(answer)
    return result.rowcount == 1


async def _write_run(session: AsyncSession, answer_id: int, run_token: datetime, values: dict) -> bool:
    """Write this grading run's results unless the answer has been re-claimed or failed as stale since."""
    result = await session.execute(
        update(InterviewAnswer)
        .where(
            InterviewAnswer.id == answer_id,
            InterviewAnswer.status == "grading",
            InterviewAnswer.grading_started_at == run_token,
        )
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    await session.commit()
    if result.rowcount == 0:
        logger.info("Interview answer %d: grading run is no longer current; its result was dropped", answer_id)
        return False
    return True


async def _grade(session: AsyncSession, answer_id: int, run_token: datetime, settings: Settings) -> None:
    answer = await session.get(InterviewAnswer, answer_id)
    if answer is None:
        logger.error("Interview answer %d not found for grading", answer_id)
        return
    if answer.status != "grading" or answer.grading_started_at != run_token:
        logger.info("Interview answer %d: grading run is no longer current; skipped", answer_id)
        return
    family = await load_question_family(session, answer.question_id)
    question = next(q for q in family if q.id == answer.question_id)
    transcript = (answer.transcript or "").strip()
    approved = [kp for kp in sorted(question.key_points, key=lambda kp: kp.position) if kp.approved]
    t_start = time.perf_counter()
    logger.info(
        "\n\n========== INTERVIEW GRADE START answer_id=%d ==========\n"
        "  question_id : %d (%d approved key point(s), %d misconception(s))\n"
        "  transcript  : %d words, edited=%s\n"
        "  grader      : %s\n  verifier    : %s",
        answer_id,
        answer.question_id,
        len(approved),
        len(question.misconceptions),
        len(transcript.split()),
        answer.transcript_edited,
        settings.interview_grader_model,
        settings.interview_verifier_model,
    )

    if not approved or len(transcript.split()) < MIN_WORDS_TO_GRADE:
        logger.info(
            "Interview %d: ungraded (%s)",
            answer_id,
            "no approved key points" if not approved else f"transcript under {MIN_WORDS_TO_GRADE} words",
        )
        await _write_run(
            session,
            answer_id,
            run_token,
            _ungraded(NO_APPROVED_KEY_POINTS_MESSAGE if not approved else TOO_SHORT_MESSAGE),
        )
        return
    missing_keys = _missing_api_keys(settings)
    if missing_keys:
        message = f"Grading needs {' and '.join(missing_keys)} to be set. Add the key and retry grading."
        logger.error("Interview %d: %s is not set - failed:grading", answer_id, " and ".join(missing_keys))
        await _write_run(session, answer_id, run_token, {"status": "failed:grading", "error_message": message})
        return

    key_point_uids = [kp.uid for kp in approved]
    misconception_uids = [m.uid for m in question.misconceptions]
    transcript_sha = sha256_text(transcript)
    answer_key_sha = _answer_key_digest(approved, question)
    proposal = _reusable_proposer_output(answer, transcript_sha, answer_key_sha, key_point_uids, misconception_uids)
    if proposal is not None:
        logger.info("Interview %d: reusing the stored grader output (retry without a new grader call)", answer_id)
    if proposal is None:
        pack = await session.get(InterviewPack, question.pack_id)
        t_grader = time.perf_counter()
        try:
            proposal = await _propose(settings, pack, question, approved, transcript)
        except LLMRateLimitError:
            logger.warning(
                "Interview %d: grader %s is out of free-tier quota - pending_quota",
                answer_id,
                settings.interview_grader_model,
            )
            quota = {"status": "pending_quota", "error_message": GRADER_QUOTA_MESSAGE}
            await _write_run(session, answer_id, run_token, quota)
            return
        logger.info("Interview %d: grader answered in %.1fs", answer_id, time.perf_counter() - t_grader)
        if not proposal_is_complete(proposal, key_point_uids, misconception_uids):
            raise LLMOutputError("the grader did not judge every key point and misconception exactly once")
        stored = {"transcript_sha256": transcript_sha, "answer_key_sha256": answer_key_sha, "output": proposal}
        saved = {"proposer_output": json.dumps(stored), "grader_model": settings.interview_grader_model}
        if not await _write_run(session, answer_id, run_token, saved):
            return

    transcript_index = QuoteIndex(transcript)
    claims = _proposed_claims(approved, proposal, transcript_index)
    stated = _stated_misconceptions(question, proposal, transcript_index)

    key_point_claims = [
        (kp.uid, kp.text, claim["quote"]) for kp, claim in zip(approved, claims) if claim["verdict"] != "missing"
    ]
    values: dict = {}
    verifier_verdicts = None
    verifier_confirmed: dict[str, bool] = {}
    if key_point_claims or stated:
        logger.info(
            "Interview %d: verifying %d key point claim(s) and %d stated misconception(s)",
            answer_id,
            len(key_point_claims),
            len(stated),
        )
        t_verifier = time.perf_counter()
        try:
            verification = await _verify(
                settings, question, transcript, key_point_claims, [(m.uid, m.text, quote) for m, quote in stated]
            )
        except LLMRateLimitError:
            logger.warning(
                "Interview %d: verifier %s is out of free-tier quota - pending_quota (grader output kept for retry)",
                answer_id,
                settings.interview_verifier_model,
            )
            quota = {"status": "pending_quota", "error_message": VERIFIER_QUOTA_MESSAGE}
            await _write_run(session, answer_id, run_token, quota)
            return
        logger.info("Interview %d: verifier answered in %.1fs", answer_id, time.perf_counter() - t_verifier)
        values["verifier_model"] = settings.interview_verifier_model
        verifier_verdicts = {
            uid: str(item.get("verdict")) for uid, item in _items_by_id(verification, "key_points").items()
        }
        verifier_confirmed = {
            uid: item["confirmed"]
            for uid, item in _items_by_id(verification, "misconceptions").items()
            if isinstance(item.get("confirmed"), bool)
        }

    results = _key_point_results(approved, claims, verifier_verdicts)
    # A quote-verified misconception always counts; the verifier's opinion is only recorded for the coach.
    score, band = content_score(((r["weight"], r["verdict"]) for r in results), len(stated))
    next_follow_up = _next_follow_up(question, family, results, band)
    misconceptions_found = [
        {
            "uid": m.uid,
            "text": m.text,
            "correction": m.correction,
            "quote": quote,
            "verifier_confirmed": verifier_confirmed.get(m.uid),
        }
        for m, quote in stated
    ]
    values.update(
        content_score=score,
        content_band=band,
        key_point_results=json.dumps(results),
        misconceptions_found=json.dumps(misconceptions_found),
        feedback=json.dumps(_feedback(proposal)),
        sentence_fixes=json.dumps(sentence_fix_rows(answer, transcript)),
        next_follow_up_question_id=next_follow_up,
        error_message=None,
        status="graded",
        graded_at=utc_now(),
    )
    if await _write_run(session, answer_id, run_token, values):
        logger.info(
            "\n\n========== INTERVIEW GRADE DONE answer_id=%d ==========\n"
            "  content     : %s (%s) in %.1fs\n"
            "  key points  : %s\n"
            "  misconceptions found : %d\n"
            "  follow_up   : %s",
            answer_id,
            score,
            band,
            time.perf_counter() - t_start,
            dict(Counter(r["verdict"] for r in results)),
            len(misconceptions_found),
            next_follow_up,
        )


async def _fail_run(answer_id: int, run_token: datetime, message: str) -> None:
    try:
        async with AsyncSessionLocal() as session:
            await _write_run(session, answer_id, run_token, {"status": "failed:grading", "error_message": message})
    except Exception:
        logger.exception("Could not mark interview answer %d as failed:grading", answer_id)


async def grade_answer(answer_id: int, run_token: datetime) -> None:
    """
    Background task: grade the confirmed transcript against the approved answer key.

    run_token is the grading_started_at written by claim_for_grading; results are only stored while it is current.
    """
    try:
        async with AsyncSessionLocal() as session:
            await asyncio.wait_for(
                _grade(session, answer_id, run_token, get_settings()), timeout=GRADING_TIMEOUT.total_seconds()
            )
    except Exception as exc:
        logger.exception("Interview answer %d: grading failed", answer_id)
        timed_out = isinstance(exc, asyncio.TimeoutError)
        await _fail_run(
            answer_id, run_token, "Grading timed out. Retry grading." if timed_out else f"Grading failed: {exc}"
        )
