from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.constants import BAND_ROLLING_WINDOW
from backend.database import AsyncSessionLocal, get_db
from backend.models import Attempt, DailyActivity, Question, UserStats
from backend.schemas import AttemptOut, AttemptStatusOut, ImproveOut, PronunciationOut, PronunciationWord
from backend.services import audio as audio_service
from pathlib import Path
from backend.services.audio import EXT_TO_MIME
from backend.services import improve as improve_service
from backend.services import scoring as scoring_service
from backend.services import transcription as transcription_service
from backend.services.vocab import compute_grammar_signals, compute_vocab_signal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/attempts", tags=["attempts"])

# ── LanguageTool singleton (optional - requires Java) ────────────────────────

_lt_tool = None
_lt_tool_init_attempted = False


def _get_lt_tool():
    global _lt_tool, _lt_tool_init_attempted
    if _lt_tool_init_attempted:
        return _lt_tool
    _lt_tool_init_attempted = True
    try:
        import language_tool_python  # type: ignore[import]
        _lt_tool = language_tool_python.LanguageTool('en-US')
        _lt_tool.picky = True  # enable stricter rule set (sent as request param to /check)
        logger.info("LanguageTool initialized (local, picky=True)")
    except Exception as exc:
        logger.warning("LanguageTool local unavailable (Java required): %s", exc)
        try:
            import language_tool_python  # type: ignore[import]
            # Fallback: sends transcript to languagetool.org - no Java needed.
            _lt_tool = language_tool_python.LanguageToolPublicAPI('en-US')
            logger.info("LanguageTool initialized (public API fallback)")
        except Exception as exc2:
            logger.warning("LanguageTool public API also unavailable: %s", exc2)
            _lt_tool = None
    return _lt_tool


# ── LanguageTool artifact filter ─────────────────────────────────────────────
# Whisper (Groq API) may capitalise the first word of segments separated by
# pauses. LanguageTool flags these as UPPERCASE_SENTENCE_START and related
# casing/punctuation rules - transcription artefacts, not speaker errors.
# Filtering them out before building grammar_context prevents the LLM from
# penalising phantom mistakes.
#
# Kept: GRAMMAR, CONFUSED_WORDS, MISC, TYPOS - all genuine error categories.

_LT_FILTERED_RULE_IDS: frozenset[str] = frozenset({
    # VAD segment-boundary capitalisation - primary transcription artefact
    "UPPERCASE_SENTENCE_START",
    # Whitespace / formatting - concepts absent from speech
    "WHITESPACE_RULE",
    "EN_QUOTES",
    # Punctuation absence - spoken language has no terminal punctuation
    "COMMA_PARENTHESIS_WHITESPACE",
    "PUNCTUATION_PARAGRAPH_END",
    "UNLIKELY_OPENING_PUNCTUATION",
    # Style rules outside the IELTS speaking rubric
    "TOO_LONG_SENTENCE",
    "ENGLISH_WORD_REPEAT_BEGINNING_RULE",
})

_LT_FILTERED_CATEGORIES: frozenset[str] = frozenset({
    "CASING",       # all casing rules - meaningless in speech
    "TYPOGRAPHY",   # formatting rules - meaningless in speech
    "PUNCTUATION",  # missing / wrong punctuation - transcription artefact
    "STYLE",        # subjective style - not an IELTS speaking criterion
    "REDUNDANCY",   # wordy phrasing - not penalised in IELTS speaking
})

# Rules that belong to filtered categories but catch genuine errors worth surfacing.
_LT_WHITELISTED_RULE_IDS: frozenset[str] = frozenset({
    "BORED_OF",  # STYLE: 'bored of' → 'bored with/by' - real preposition error
})


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    """Return (start, end) character offsets for each sentence in *text*.

    Splits on terminal punctuation (. ! ?) followed by whitespace or end of
    string. Whisper transcripts include punctuation, making this reliable.
    Falls back to the whole text as a single span when no boundary is found
    (e.g. very short responses without punctuation).
    """
    spans: list[tuple[int, int]] = []
    start = 0
    for m in re.finditer(r"[.!?]+", text):
        end = m.end()
        spans.append((start, end))
        nxt = end
        while nxt < len(text) and text[nxt].isspace():
            nxt += 1
        start = nxt
    if start < len(text):          # trailing text with no terminal punctuation
        spans.append((start, len(text)))
    return spans or [(0, len(text))]


async def _run_pipeline(attempt_id: int, question_id: int, audio_path: str) -> None:
    """Background task: transcribe → score → update attempt + stats."""
    logger.info(
        "\n\n========== PIPELINE START attempt_id=%d ==========\n"
        "  question_id=%d\n"
        "  audio=%s",
        attempt_id, question_id, audio_path,
    )
    _t_start = time.perf_counter()
    _t_transcription: float = 0.0
    _t_signals: float = 0.0
    _t_scoring: float = 0.0
    settings = get_settings()

    async with AsyncSessionLocal() as session:
        try:
            # Fetch the question text and part
            q_result = await session.execute(
                select(Question).where(Question.id == question_id)
            )
            question = q_result.scalar_one_or_none()
            if question is None:
                raise ValueError(f"Question {question_id} not found")

            # Emit 'transcribing' status
            t_result = await session.execute(select(Attempt).where(Attempt.id == attempt_id))
            attempt_pre = t_result.scalar_one_or_none()
            if attempt_pre is not None:
                attempt_pre.status = "transcribing"
                await session.commit()
                logger.info("Pipeline %d: transcribing", attempt_id)

            # ----------------------------------------------------------------
            # 1. Transcription
            # ----------------------------------------------------------------
            _t0 = time.perf_counter()
            try:
                transcription_result = await asyncio.wait_for(
                    transcription_service.transcribe(audio_path),
                    timeout=120.0,
                )
            except asyncio.TimeoutError:
                logger.error("Pipeline %d: transcription timed out after 120s", attempt_id)
                t2 = await session.execute(select(Attempt).where(Attempt.id == attempt_id))
                a = t2.scalar_one_or_none()
                if a is not None:
                    a.status = "failed:transcription"
                    await session.commit()
                return
            except Exception as exc:
                logger.exception("Pipeline %d: transcription failed: %s", attempt_id, exc)
                t2 = await session.execute(select(Attempt).where(Attempt.id == attempt_id))
                a = t2.scalar_one_or_none()
                if a is not None:
                    a.status = "failed:transcription"
                    await session.commit()
                    logger.info("Pipeline %d: failed:transcription", attempt_id)
                return

            _t_transcription = time.perf_counter() - _t0
            transcript = transcription_result.get("transcript", "")
            words = transcription_result.get("words", [])
            logger.info(
                "\n\n========== TRANSCRIPTION RESULT attempt_id=%d ==========\n"
                "  raw keys: %s\n"
                "  word_count=%d  duration=%.1fs\n"
                "  transcript: %r\n"
                "  first 3 words: %s",
                attempt_id,
                list(transcription_result.keys()),
                len(words),
                words[-1].get("end", 0) if words else 0,
                transcript[:300],
                words[:3],
            )

            # Guard: empty or silent audio
            if not transcript or not transcript.strip():
                file_size = os.path.getsize(audio_path) if os.path.exists(audio_path) else -1
                logger.warning(
                    "Pipeline %d: empty transcript - audio=%s (%.1f KB)",
                    attempt_id, audio_path, file_size / 1024,
                )
                t2 = await session.execute(select(Attempt).where(Attempt.id == attempt_id))
                a = t2.scalar_one_or_none()
                if a is not None:
                    a.status = "failed:empty_audio"
                    await session.commit()
                    logger.info("Pipeline %d: failed:empty_audio", attempt_id)
                return
            word_timestamps_json = json.dumps(words)

            # Compute duration from last word end time if available
            duration_seconds: int | None = None
            if words:
                last_word = words[-1]
                end_time = last_word.get("end")
                if end_time is not None:
                    duration_seconds = int(end_time)

            # ----------------------------------------------------------------
            # 2. Scoring signals
            # ----------------------------------------------------------------

            # Signal 1: Fluency gap rate + disfluent word set (single pass)
            gap_count = 0
            disfluent: set[str] = set()
            for i in range(1, len(words)):
                cur_start = words[i].get("start")
                prev_end = words[i - 1].get("end")
                if (
                    cur_start is not None
                    and prev_end is not None
                    and cur_start - prev_end >= settings.gap_threshold
                ):
                    gap_count += 1
                    disfluent.add(words[i]["word"].lower())
            total_words = len(words)
            gaps_per_100 = round(gap_count / total_words * 100, 1) if total_words > 0 else 0.0
            fluency_context = (
                f"{gap_count} long pause(s) in {total_words} words ({gaps_per_100}/100 words)"
            )
            _t0 = time.perf_counter()

            # Signal 2: CEFR vocabulary distribution + lexical diversity (MTLD)
            vocab_signal = compute_vocab_signal(words, transcript)

            # Signal 3: Grammar checker (LanguageTool - requires Java)
            grammar_context = "grammar checker unavailable"
            filtered_matches: list = []  # initialised here so spaCy signals run even if LT fails
            if transcript and transcript.strip():
                try:
                    lt = _get_lt_tool()
                    if lt is not None:
                        loop = asyncio.get_event_loop()
                        matches = await loop.run_in_executor(None, lt.check, transcript)
                        filtered_matches = [
                            m for m in matches
                            if m.rule_id not in _LT_FILTERED_RULE_IDS
                            and (
                                m.rule_id in _LT_WHITELISTED_RULE_IDS
                                or m.category not in _LT_FILTERED_CATEGORIES
                            )
                        ]
                        logger.info(
                            "\n\n========== LT_RAW_MATCHES attempt_id=%d ==========\n"
                            "  source : %s\n"
                            "  count  : %d (raw) → %d (after artifact filter)\n"
                            "  matches: %s",
                            attempt_id,
                            "local" if type(lt).__name__ == "LanguageTool" else "public API",
                            len(matches),
                            len(filtered_matches),
                            [
                                {
                                    "rule": m.rule_id,
                                    "category": m.category,
                                    "word": transcript[m.offset:m.offset + m.error_length],
                                    "offset": m.offset,
                                    "suggestions": list(m.replacements[:3]),
                                    "message": m.message,
                                }
                                for m in filtered_matches[:10]
                            ],
                        )
                        # ── Sentence segmentation & error attribution ─────────
                        sent_spans = _sentence_spans(transcript)
                        n_sentences = len(sent_spans)

                        def _sent_idx(offset: int) -> int | None:
                            for i, (s, e) in enumerate(sent_spans):
                                if s <= offset < e:
                                    return i
                            return None  # unmatched offset - caller must skip

                        # Stats computed over ALL filtered matches (not just cap)
                        error_sentence_set = {
                            idx
                            for m in filtered_matches
                            if (idx := _sent_idx(m.offset)) is not None
                        }
                        n_error_sents = len(error_sentence_set)
                        clean_pct = round(
                            100 * (n_sentences - n_error_sents) / n_sentences
                        ) if n_sentences else 100

                        if not filtered_matches:
                            grammar_context = (
                                f"no grammar errors detected "
                                f"({n_sentences} sentences, 100% error-free)"
                            )
                        else:
                            displayed = filtered_matches
                            total = len(filtered_matches)
                            header = (
                                f"{total} error(s) in {n_sentences} sentences "
                                f"({clean_pct}% error-free)"
                            )

                            # Group by rule_id - systematicity signal
                            rule_groups: dict[str, list] = defaultdict(list)
                            for m in displayed:
                                rule_groups[m.rule_id].append(m)

                            by_rule_lines = []
                            for rule_id, grp in rule_groups.items():
                                cat = grp[0].category
                                examples = " | ".join(
                                    f"'{transcript[m.offset:m.offset + m.error_length]}'"
                                    f" → {list(m.replacements[:2])}"
                                    for m in grp
                                )
                                by_rule_lines.append(
                                    f"  [{cat}] {rule_id} ×{len(grp)}: {examples}"
                                )

                            # Per-sentence attribution
                            by_sent_lines = []
                            for m in displayed:
                                _sidx = _sent_idx(m.offset)
                                s_num = (_sidx + 1) if _sidx is not None else "?"
                                span = transcript[m.offset:m.offset + m.error_length]
                                by_sent_lines.append(
                                    f"  S{s_num}: '{span}'"
                                    f" → {list(m.replacements[:2])}"
                                    f" ({m.message})"
                                )

                            grammar_context = "\n".join([
                                header,
                                "",
                                "By rule:",
                                *by_rule_lines,
                                "",
                                "By sentence:",
                                *by_sent_lines,
                            ])
                except Exception as exc:
                    logger.warning("Grammar check failed: %s", exc)

            # Signals 3 + 5: spaCy sentence complexity and structural range
            # Runs outside the LT block so it executes even when LT is unavailable.
            # filtered_matches is [] in that case - Signal 3 error-density reports 0
            # but Signal 5 (tense inventory, passive, conditionals, tree depth) still runs.
            try:
                grammar_result = compute_grammar_signals(
                    transcript, _sentence_spans(transcript), filtered_matches,
                )
                grammar_context += "\n\n" + grammar_result["detail"]
                grammar_context += "\n" + grammar_result["structural_detail"]
                # Signal 7 (partial): turn length - anchors band 4 "overall turns are short"
                n_sents = grammar_result["n_sentences"]
                avg_words = round(total_words / n_sents, 1) if n_sents > 0 else 0.0
                grammar_context += f"\nturn_length: {total_words} words, {n_sents} sentences, avg {avg_words} words/sentence"
            except Exception as exc:
                logger.warning("Grammar signals (spaCy) failed: %s", exc)

            # ----------------------------------------------------------------
            # 3. Mispronounced words for pronunciation
            # ----------------------------------------------------------------
            mispronounced_words = [
                w["word"]
                for w in words
                if (
                    isinstance(w.get("probability"), (int, float))
                    and w["probability"] < settings.low_confidence_threshold
                )
            ]
            disfluent_words = [w for w in words if w["word"].lower() in disfluent]

            logger.info(
                "\n\n========== SCORING SIGNALS attempt_id=%d ==========\n"
                "  fluency : %d gaps / %d words = %.1f per 100\n"
                "  vocab   : %s\n"
                "  grammar : %s\n"
                "  mispronounced : %s",
                attempt_id,
                gap_count, total_words, gaps_per_100,
                vocab_signal,
                grammar_context,
                mispronounced_words,
            )

            # ----------------------------------------------------------------
            # 4. Score
            # ----------------------------------------------------------------
            # Emit 'scoring' status before calling LLM
            s_result = await session.execute(select(Attempt).where(Attempt.id == attempt_id))
            attempt_scoring = s_result.scalar_one_or_none()
            if attempt_scoring is not None:
                attempt_scoring.status = "scoring"
                await session.commit()
                logger.info("Pipeline %d: scoring", attempt_id)

            _t_signals = time.perf_counter() - _t0
            _t0 = time.perf_counter()
            try:
                scoring_result = await scoring_service.score_attempt(
                    question_text=question.text,
                    part=question.part,
                    transcript=transcript,
                    mispronounced_words=mispronounced_words,
                    fluency_context=fluency_context,
                    vocab_signal=vocab_signal,
                    grammar_context=grammar_context,
                )
            except Exception as exc:
                logger.exception("Pipeline %d: scoring failed: %s", attempt_id, exc)
                s2 = await session.execute(select(Attempt).where(Attempt.id == attempt_id))
                a = s2.scalar_one_or_none()
                if a is not None:
                    a.status = "failed:scoring"
                    await session.commit()
                    logger.info("Pipeline %d: failed:scoring", attempt_id)
                return

            _t_scoring = time.perf_counter() - _t0
            fluency = scoring_result.get("fluency")
            vocabulary = scoring_result.get("vocabulary")
            grammar = scoring_result.get("grammar")
            pronunciation = scoring_result.get("pronunciation")
            feedback_text = scoring_result.get("feedback_text")
            _highlights_list = scoring_result.get("usage_errors", [])
            logger.info(
                "\n\n========== LLM_ERROR_HIGHLIGHTS attempt_id=%d ==========\n"
                "  count : %d\n"
                "  items : %s",
                attempt_id,
                len(_highlights_list),
                _highlights_list,
            )
            usage_errors = json.dumps(_highlights_list)
            score = scoring_result.get("score")
            logger.info(
                "\n\n========== SCORING RESULT attempt_id=%d ==========\n"
                "  raw keys : %s\n"
                "  fluency  : %s\n"
                "  vocab    : %s\n"
                "  grammar  : %s\n"
                "  pronun   : %s\n"
                "  overall  : %s\n"
                "  feedback : %r",
                attempt_id,
                list(scoring_result.keys()),
                fluency, vocabulary, grammar, pronunciation, score,
                (feedback_text or "")[:200],
            )

            # ----------------------------------------------------------------
            # 5. Update Attempt
            # ----------------------------------------------------------------
            result = await session.execute(
                select(Attempt).where(Attempt.id == attempt_id)
            )
            attempt = result.scalar_one_or_none()
            if attempt is None:
                logger.error("Attempt %d not found during pipeline, aborting.", attempt_id)
                return
            if score is None:
                logger.error(
                    "Pipeline %d: LLM returned no score - marking failed:scoring. "
                    "scoring_result keys: %s",
                    attempt_id, list(scoring_result.keys()),
                )
                attempt.status = "failed:scoring"
                await session.commit()
                return

            attempt.transcript = transcript
            attempt.word_timestamps = word_timestamps_json
            attempt.duration_seconds = duration_seconds
            attempt.fluency = fluency
            attempt.vocabulary = vocabulary
            attempt.grammar = grammar
            attempt.pronunciation = pronunciation
            attempt.score = score
            attempt.feedback_text = feedback_text
            attempt.usage_errors = usage_errors
            attempt.status = "ready"

            # ----------------------------------------------------------------
            # 6. Update DailyActivity
            # ----------------------------------------------------------------
            today = date.today()
            da_result = await session.execute(
                select(DailyActivity).where(DailyActivity.date == today)
            )
            daily = da_result.scalar_one_or_none()
            if daily is None:
                daily = DailyActivity(date=today, attempts_count=1)
                session.add(daily)
                await session.flush()
            else:
                daily.attempts_count += 1

            # Compute intensity bucket (0-4)
            count = daily.attempts_count
            if count == 0:
                daily.intensity = 0
            elif count == 1:
                daily.intensity = 1
            elif count <= 3:
                daily.intensity = 2
            elif count <= 6:
                daily.intensity = 3
            else:
                daily.intensity = 4

            # ----------------------------------------------------------------
            # 7. Update UserStats streak
            # ----------------------------------------------------------------
            stats_result = await session.execute(
                select(UserStats).where(UserStats.id == 1)
            )
            stats = stats_result.scalar_one_or_none()
            if stats is None:
                stats = UserStats(
                    id=1, current_streak=0, longest_streak=0, total_attempts=0
                )
                session.add(stats)
                await session.flush()

            stats.total_attempts += 1

            # Recalculate streak: single bulk fetch, count consecutive days ending today
            recent = await session.execute(
                select(DailyActivity.date, DailyActivity.attempts_count)
                .order_by(DailyActivity.date.desc())
                .limit(1000)
            )
            rows = recent.all()
            streak = 0
            expected = today
            for row_date, count in rows:
                if row_date == expected and count > 0:
                    streak += 1
                    expected = date.fromordinal(expected.toordinal() - 1)
                else:
                    break

            stats.current_streak = streak
            if streak > stats.longest_streak:
                stats.longest_streak = streak

            # Update estimated_band as rolling average of recent scores
            if score is not None:
                recent_result = await session.execute(
                    select(Attempt.score)
                    .where(Attempt.status == "ready", Attempt.score.isnot(None))
                    .order_by(Attempt.created_at.desc())
                    .limit(BAND_ROLLING_WINDOW)
                )
                recent_scores = [r for r in recent_result.scalars().all()]
                if recent_scores:
                    stats.estimated_band = round(
                        sum(recent_scores) / len(recent_scores) * 2
                    ) / 2

            await session.commit()
            _t_total = time.perf_counter() - _t_start
            logger.info(
                "\n\n========== PIPELINE DONE attempt_id=%d ==========\n"
                "  transcription : %.2fs\n"
                "  signals       : %.2fs\n"
                "  llm_scoring   : %.2fs\n"
                "  total         : %.2fs",
                attempt_id, _t_transcription, _t_signals, _t_scoring, _t_total,
            )

        except Exception as exc:
            logger.exception("Pipeline failed for attempt %d: %s", attempt_id, exc)
            try:
                result = await session.execute(
                    select(Attempt).where(Attempt.id == attempt_id)
                )
                attempt = result.scalar_one_or_none()
                if attempt is not None:
                    attempt.status = "failed"
                    await session.commit()
                    logger.info("Pipeline %d: failed (unknown)", attempt_id)
            except Exception:
                logger.exception(
                    "Failed to mark attempt %d as failed", attempt_id
                )


@router.post("/submit", response_model=AttemptStatusOut, status_code=202)
async def submit_attempt(
    background_tasks: BackgroundTasks,
    audio: UploadFile,
    question_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
) -> AttemptStatusOut:
    settings = get_settings()

    # Validate question exists
    q_result = await db.execute(select(Question).where(Question.id == question_id))
    question = q_result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    # Create Attempt row (status=processing, no audio path yet)
    attempt = Attempt(question_id=question_id, status="processing")
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)

    # Save audio file
    try:
        audio_path = await audio_service.save_audio(
            upload_file=audio,
            attempt_id=attempt.id,
            audio_dir=settings.audio_dir,
        )
        attempt.audio_path = audio_path
        await db.commit()
        await db.refresh(attempt)
        file_size_kb = os.path.getsize(audio_path) / 1024 if os.path.exists(audio_path) else -1
        logger.info(
            "\n\n========== SUBMIT attempt_id=%d question_id=%d ==========\n"
            "  audio saved → %s  (%.1f KB)\n"
            "  content_type=%s",
            attempt.id, question_id, audio_path, file_size_kb, audio.content_type,
        )
    except Exception as exc:
        attempt.status = "failed"
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to save audio: {exc}") from exc

    # Launch pipeline in background
    background_tasks.add_task(
        _run_pipeline,
        attempt_id=attempt.id,
        question_id=question_id,
        audio_path=audio_path,
    )

    return AttemptStatusOut(
        id=attempt.id,
        status=attempt.status,
        score=attempt.score,
        fluency=attempt.fluency,
        vocabulary=attempt.vocabulary,
        grammar=attempt.grammar,
        pronunciation=attempt.pronunciation,
        feedback_text=attempt.feedback_text,
        usage_errors=attempt.usage_errors,
        transcript=attempt.transcript,
    )


@router.get("/{attempt_id}/status", response_model=AttemptStatusOut)
async def get_attempt_status(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
) -> AttemptStatusOut:
    result = await db.execute(select(Attempt).where(Attempt.id == attempt_id))
    attempt = result.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return AttemptStatusOut(
        id=attempt.id,
        status=attempt.status,
        score=attempt.score,
        fluency=attempt.fluency,
        vocabulary=attempt.vocabulary,
        grammar=attempt.grammar,
        pronunciation=attempt.pronunciation,
        feedback_text=attempt.feedback_text,
        usage_errors=attempt.usage_errors,
        transcript=attempt.transcript,
    )


_STALE_PROCESSING_THRESHOLD = timedelta(minutes=10)


@router.get("/history/{question_id}", response_model=List[AttemptOut])
async def get_attempt_history(
    question_id: int,
    db: AsyncSession = Depends(get_db),
) -> List[AttemptOut]:
    # Verify question exists
    q_result = await db.execute(select(Question).where(Question.id == question_id))
    if q_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Question not found")

    result = await db.execute(
        select(Attempt)
        .where(Attempt.question_id == question_id)
        .order_by(Attempt.created_at.desc())
    )
    attempts = result.scalars().all()

    # Mark any attempt stuck in 'processing' for longer than the threshold as
    # 'failed' so they don't show as infinite spinners in the UI.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    stale_found = False
    for attempt in attempts:
        if (
            attempt.status in ("processing", "transcribing", "scoring")
            and attempt.created_at is not None
            and now - attempt.created_at > _STALE_PROCESSING_THRESHOLD
        ):
            attempt.status = "failed"
            stale_found = True
            logger.warning("Marked stale attempt %d as failed (created_at=%s)", attempt.id, attempt.created_at)
    if stale_found:
        await db.commit()

    return [AttemptOut.model_validate(a) for a in attempts]


@router.post("/{attempt_id}/improve", response_model=ImproveOut)
async def improve_attempt(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
) -> ImproveOut:
    """Rewrite the attempt's response at one band higher using the LLM."""
    result = await db.execute(select(Attempt).where(Attempt.id == attempt_id))
    attempt = result.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found")

    if attempt.status != "ready" or attempt.transcript is None or attempt.score is None:
        raise HTTPException(
            status_code=400,
            detail="Attempt is not ready or has no transcript/score",
        )

    # Fetch question text
    q_result = await db.execute(
        select(Question).where(Question.id == attempt.question_id)
    )
    question = q_result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    # Compute target band: current score rounded to nearest 0.5 + 1.0, capped at 9.0
    current_band = round(attempt.score * 2) / 2
    target_band = min(current_band + 1.0, 9.0)

    try:
        improved = await improve_service.generate_improvement(
            question_text=question.text,
            transcript=attempt.transcript,
            current_band=current_band,
            target_band=target_band,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ImproveOut(
        improved_text=improved["improved_text"],
        target_band=target_band,
        explanation=improved["explanation"],
    )


@router.get("/{attempt_id}/pronunciation", response_model=PronunciationOut)
async def get_pronunciation(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
) -> PronunciationOut:
    """Return per-word pronunciation confidence from Whisper word timestamps."""
    result = await db.execute(select(Attempt).where(Attempt.id == attempt_id))
    attempt = result.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found")

    if attempt.status != "ready" or attempt.word_timestamps is None:
        raise HTTPException(
            status_code=400,
            detail="Attempt is not ready or has no word timestamps",
        )

    try:
        words_data = json.loads(attempt.word_timestamps)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=500, detail="Invalid word_timestamps data")

    words = []
    for w in words_data:
        confidence = w.get("probability", 0.0)
        if not isinstance(confidence, (int, float)):
            confidence = 0.0
        words.append(
            PronunciationWord(
                word=w.get("word", ""),
                confidence=round(confidence, 3),
                is_mispronounced=confidence < get_settings().low_confidence_threshold,
            )
        )

    return PronunciationOut(words=words)


@router.get("/{attempt_id}/audio")
async def get_attempt_audio(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Stream the recorded audio for a completed attempt."""
    result = await db.execute(select(Attempt).where(Attempt.id == attempt_id))
    attempt = result.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found")

    if not attempt.audio_path:
        raise HTTPException(status_code=404, detail="No audio recorded for this attempt")

    try:
        media_type = EXT_TO_MIME.get(Path(attempt.audio_path).suffix, "audio/webm")
        return FileResponse(attempt.audio_path, media_type=media_type)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Audio file no longer available (may have been cleaned up)",
        )
