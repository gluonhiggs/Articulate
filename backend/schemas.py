from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Question schemas
# ---------------------------------------------------------------------------


class QuestionOut(BaseModel):
    id: int
    part: str
    topic: Optional[str] = None
    category: Optional[str] = None
    parent_question_id: Optional[int] = None
    text: str
    bullet_points: Optional[List[str]] = None
    latest_score: Optional[float] = None
    topic_tag: Optional[str] = None
    source: Optional[str] = None
    last_seen_date: Optional[date] = None

    @field_validator("bullet_points", mode="before")
    @classmethod
    def parse_bullet_points(cls, v: Any) -> Optional[List[str]]:
        if v is None:
            return None
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
        return None

    model_config = {"from_attributes": True}


class Part3GroupOut(BaseModel):
    parent: QuestionOut
    questions: List[QuestionOut]


class ForecastEntry(BaseModel):
    topic_tag: str
    count: int
    last_seen_date: Optional[str] = None  # "YYYY-MM" format


# ---------------------------------------------------------------------------
# Create question request
# ---------------------------------------------------------------------------


class QuestionCreateIn(BaseModel):
    text: str
    part: Literal["1", "2", "3"]
    topic: Optional[str] = None
    category: Optional[str] = None
    parent_question_id: Optional[int] = None
    bullet_points: Optional[List[str]] = None
    topic_tag: Optional[str] = None
    source: Optional[str] = None
    last_seen_date: Optional[date] = None


# ---------------------------------------------------------------------------
# Attempt schemas
# ---------------------------------------------------------------------------


def _parse_json_list(v: Any) -> Optional[List[Any]]:
    """Parse a JSON string into a list, passthrough if already a list."""
    if v is None:
        return None
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
    return None


class AttemptOut(BaseModel):
    id: int
    question_id: int
    audio_path: Optional[str] = None
    transcript: Optional[str] = None
    score: Optional[float] = None
    fluency: Optional[float] = None
    vocabulary: Optional[float] = None
    grammar: Optional[float] = None
    pronunciation: Optional[float] = None
    feedback_text: Optional[str] = None
    usage_errors: Optional[List[Any]] = None
    word_timestamps: Optional[List[Any]] = None
    duration_seconds: Optional[int] = None
    status: str  # AttemptStatus on the write side; permissive here so an unknown value still serializes
    created_at: datetime

    @field_validator("usage_errors", "word_timestamps", mode="before")
    @classmethod
    def parse_json_fields(cls, v: Any) -> Optional[List[Any]]:
        return _parse_json_list(v)

    model_config = {"from_attributes": True}


class AttemptStatusOut(BaseModel):
    id: int
    status: str
    score: Optional[float] = None
    fluency: Optional[float] = None
    vocabulary: Optional[float] = None
    grammar: Optional[float] = None
    pronunciation: Optional[float] = None
    feedback_text: Optional[str] = None
    usage_errors: Optional[List[Any]] = None
    transcript: Optional[str] = None

    @field_validator("usage_errors", mode="before")
    @classmethod
    def parse_json_fields(cls, v: Any) -> Optional[List[Any]]:
        return _parse_json_list(v)

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Dashboard schemas
# ---------------------------------------------------------------------------


class HeatmapEntry(BaseModel):
    date: str
    count: int
    intensity: int


class DashboardOut(BaseModel):
    current_streak: int
    longest_streak: int
    total_attempts: int
    estimated_band: Optional[float] = None
    heatmap: List[HeatmapEntry]


# ---------------------------------------------------------------------------
# System info
# ---------------------------------------------------------------------------


class ImproveOut(BaseModel):
    improved_text: str
    target_band: float
    explanation: str


class PronunciationWord(BaseModel):
    word: str
    confidence: float
    tier: str


class PronunciationOut(BaseModel):
    words: List[PronunciationWord]


class SystemInfoOut(BaseModel):
    profile: str
    whisper_model: str
    whisper_device: str
    llm_model: str
    llm_assist_model: str = ""
    is_low_accuracy: bool = False
    llm_reachable: bool = False
    # --- Transcription mode ---
    transcription_mode: str = "groq"  # "groq" | "local"
    faster_whisper_installed: bool = False
    op_status: str = ""  # "" | "installing" | "loading" | "failed"
    is_desktop: bool = False  # True when running as a packaged Electron app


class SetModelRequest(BaseModel):
    model: str


class SetTranscriptionModeRequest(BaseModel):
    mode: str  # "groq" | "local"


# ---------------------------------------------------------------------------
# Interview practice schemas
# ---------------------------------------------------------------------------

InterviewRole = Literal["swe", "be", "fe", "de", "da", "ds", "other"]
InterviewLevel = Literal["junior", "mid", "senior"]
InterviewQuestionKind = Literal["technical", "behavioural"]
KeyPointVerdict = Literal["covered", "partial", "missing", "incorrect"]
ContentBand = Literal["strong", "developing", "weak", "incorrect", "ungraded"]
InterviewAnswerStatus = Literal[
    "processing",
    "transcribing",
    "needs_review",
    "grading",
    "graded",
    "pending_quota",
    "failed:transcription",
    "failed:empty_audio",
    "failed:grading",
]

PACK_FILE_FORMAT = "articulate-interview-pack"
PACK_FILE_FORMAT_VERSION = 1
MAX_PACK_VERSION = 1_000_000

QUESTION_TEXT_MAX = 2000
KEY_POINT_TEXT_MAX = 1000
SOURCE_QUOTE_MAX = 2000
MISCONCEPTION_TEXT_MAX = 1000
MAX_KEY_POINTS = 20
MAX_MISCONCEPTIONS = 20
MAX_FOLLOW_UPS = 10
ANSWER_SECONDS_MIN = 15
ANSWER_SECONDS_MAX = 600
DEFAULT_QUESTION_SECONDS = 120
DEFAULT_FOLLOW_UP_SECONDS = 90
SOURCE_URL_MAX = 500


def _web_url(value: Optional[str]) -> Optional[str]:
    # Source links open in the system browser, so a shared pack must not smuggle in file: or app URLs.
    url = (value or "").strip()
    if not url:
        return None
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("source URL must start with http:// or https://")
    return url


class PackFileKeyPoint(BaseModel):
    id: Optional[str] = Field(None, max_length=36)
    text: str = Field(min_length=1, max_length=KEY_POINT_TEXT_MAX)
    weight: int = Field(2, ge=1, le=3)
    source_quote: Optional[str] = Field(None, max_length=SOURCE_QUOTE_MAX)
    approved: bool = True


class PackFileMisconception(BaseModel):
    id: Optional[str] = Field(None, max_length=36)
    text: str = Field(min_length=1, max_length=MISCONCEPTION_TEXT_MAX)
    correction: str = Field("", max_length=MISCONCEPTION_TEXT_MAX)


class PackFileFollowUp(BaseModel):
    id: Optional[str] = Field(None, max_length=36)
    text: str = Field(min_length=1, max_length=QUESTION_TEXT_MAX)
    answer_seconds: int = Field(DEFAULT_FOLLOW_UP_SECONDS, ge=ANSWER_SECONDS_MIN, le=ANSWER_SECONDS_MAX)
    trigger_key_point_id: Optional[str] = Field(None, max_length=36)
    key_points: List[PackFileKeyPoint] = Field(default_factory=list, max_length=MAX_KEY_POINTS)
    misconceptions: List[PackFileMisconception] = Field(default_factory=list, max_length=MAX_MISCONCEPTIONS)


class PackFileQuestion(BaseModel):
    id: Optional[str] = Field(None, max_length=36)
    topic: str = Field("", max_length=100)
    kind: InterviewQuestionKind = "technical"
    text: str = Field(min_length=1, max_length=QUESTION_TEXT_MAX)
    answer_seconds: int = Field(DEFAULT_QUESTION_SECONDS, ge=ANSWER_SECONDS_MIN, le=ANSWER_SECONDS_MAX)
    key_points: List[PackFileKeyPoint] = Field(default_factory=list, max_length=MAX_KEY_POINTS)
    misconceptions: List[PackFileMisconception] = Field(default_factory=list, max_length=MAX_MISCONCEPTIONS)
    follow_ups: List[PackFileFollowUp] = Field(default_factory=list, max_length=MAX_FOLLOW_UPS)


class PackFileGlossaryTerm(BaseModel):
    term: str = Field(min_length=1, max_length=100)
    aliases: List[str] = Field(default_factory=list, max_length=20)


class PackFileSource(BaseModel):
    id: Optional[str] = Field(None, max_length=36)
    title: str = Field(min_length=1, max_length=200)
    url: Optional[str] = Field(None, max_length=SOURCE_URL_MAX)
    content: str = Field("", max_length=200_000)

    _check_url = field_validator("url")(_web_url)


class PackFileMeta(BaseModel):
    id: Optional[str] = Field(None, max_length=36)
    title: str = Field(min_length=1, max_length=200)
    role: InterviewRole
    level: InterviewLevel
    version: int = Field(1, ge=1, le=MAX_PACK_VERSION)
    author: str = Field("", max_length=100)
    job_description: str = Field("", max_length=20_000)


class PackFile(BaseModel):
    format: Literal["articulate-interview-pack"]
    format_version: Literal[1]
    pack: PackFileMeta
    glossary: List[PackFileGlossaryTerm] = Field(default_factory=list, max_length=500)
    sources: List[PackFileSource] = Field(default_factory=list, max_length=50)
    questions: List[PackFileQuestion] = Field(default_factory=list, max_length=300)


CV_TEXT_MAX = 60_000


class CandidateProfileIn(BaseModel):
    full_name: str = Field("", max_length=120)
    target_role: str = Field("", max_length=120)
    cv_text: str = Field("", max_length=CV_TEXT_MAX)
    cv_filename: str = Field("", max_length=260)


class CandidateProfileOut(BaseModel):
    full_name: str
    target_role: str
    cv_text: str
    cv_filename: str
    has_cv: bool


class CvFileOut(BaseModel):
    filename: str
    text: str
    characters: int
    truncated: bool


class InterviewPackCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    role: InterviewRole
    level: InterviewLevel
    job_description: str = Field("", max_length=20_000)
    author: str = Field("", max_length=100)


class InterviewPackUpdate(InterviewPackCreate):
    pass


class InterviewTopicReadiness(BaseModel):
    topic: str
    question_count: int
    graded_count: int
    average_content_score: Optional[float] = None


class InterviewPackSummaryOut(BaseModel):
    id: int
    uid: str
    title: str
    role: InterviewRole
    level: InterviewLevel
    version: int
    author: str
    question_count: int
    answered_question_count: int
    average_content_score: Optional[float] = None
    updated_at: datetime


class InterviewKeyPointIn(BaseModel):
    uid: Optional[str] = Field(None, max_length=36)
    text: str = Field(min_length=1, max_length=KEY_POINT_TEXT_MAX)
    weight: int = Field(2, ge=1, le=3)
    source_quote: Optional[str] = Field(None, max_length=SOURCE_QUOTE_MAX)
    approved: bool = False


class InterviewKeyPointOut(BaseModel):
    id: int
    uid: str
    text: str
    weight: int
    source_quote: Optional[str] = None
    quote_verified: Optional[bool] = None
    approved: bool


class InterviewMisconceptionIn(BaseModel):
    uid: Optional[str] = Field(None, max_length=36)
    text: str = Field(min_length=1, max_length=MISCONCEPTION_TEXT_MAX)
    correction: str = Field("", max_length=MISCONCEPTION_TEXT_MAX)


class InterviewMisconceptionOut(BaseModel):
    id: int
    uid: str
    text: str
    correction: str


class InterviewFollowUpIn(BaseModel):
    uid: Optional[str] = Field(None, max_length=36)
    text: str = Field(min_length=1, max_length=QUESTION_TEXT_MAX)
    answer_seconds: int = Field(DEFAULT_FOLLOW_UP_SECONDS, ge=ANSWER_SECONDS_MIN, le=ANSWER_SECONDS_MAX)
    trigger_key_point_uid: Optional[str] = Field(None, max_length=36)
    key_points: List[InterviewKeyPointIn] = Field(default_factory=list, max_length=MAX_KEY_POINTS)
    misconceptions: List[InterviewMisconceptionIn] = Field(default_factory=list, max_length=MAX_MISCONCEPTIONS)


class InterviewQuestionUpsert(BaseModel):
    topic: str = Field("", max_length=100)
    kind: InterviewQuestionKind = "technical"
    text: str = Field(min_length=1, max_length=QUESTION_TEXT_MAX)
    answer_seconds: int = Field(DEFAULT_QUESTION_SECONDS, ge=ANSWER_SECONDS_MIN, le=ANSWER_SECONDS_MAX)
    key_points: List[InterviewKeyPointIn] = Field(default_factory=list, max_length=MAX_KEY_POINTS)
    misconceptions: List[InterviewMisconceptionIn] = Field(default_factory=list, max_length=MAX_MISCONCEPTIONS)
    follow_ups: List[InterviewFollowUpIn] = Field(default_factory=list, max_length=MAX_FOLLOW_UPS)


class InterviewQuestionOut(BaseModel):
    id: int
    uid: str
    pack_id: int
    parent_question_id: Optional[int] = None
    trigger_key_point_uid: Optional[str] = None
    topic: str
    kind: InterviewQuestionKind = "technical"
    text: str
    answer_seconds: int
    retired: bool = False
    key_points: List[InterviewKeyPointOut]
    misconceptions: List[InterviewMisconceptionOut]
    follow_ups: List["InterviewQuestionOut"] = Field(default_factory=list)
    answer_count: int = 0
    latest_content_score: Optional[int] = None
    latest_delivery_score: Optional[int] = None


class InterviewGlossaryTermIn(BaseModel):
    term: str = Field(min_length=1, max_length=100)
    aliases: List[str] = Field(default_factory=list, max_length=20)


class InterviewGlossaryTermOut(InterviewGlossaryTermIn):
    id: int


class InterviewSourceIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    url: Optional[str] = Field(None, max_length=SOURCE_URL_MAX)
    content: str = Field(min_length=1, max_length=200_000)

    _check_url = field_validator("url")(_web_url)


class InterviewSourceOut(BaseModel):
    id: int
    uid: str
    title: str
    url: Optional[str] = None
    content_length: int
    preview: str


class InterviewPackDetailOut(InterviewPackSummaryOut):
    job_description: str
    glossary: List[InterviewGlossaryTermOut]
    sources: List[InterviewSourceOut]
    questions: List[InterviewQuestionOut]
    topics: List[InterviewTopicReadiness]


class InterviewDraftRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=100)
    count: int = Field(3, ge=1, le=5)
    source_ids: List[int] = Field(default_factory=list, max_length=20)


class InterviewGradeRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=20_000)


class InterviewGlossaryCorrectionOut(BaseModel):
    start: int
    end: int
    original: str
    replacement: str


class InterviewKeyPointResultOut(BaseModel):
    uid: str
    text: str
    weight: int
    verdict: KeyPointVerdict
    quote: Optional[str] = None
    reason: Optional[str] = None
    verifier_verdict: Optional[str] = None


class InterviewMisconceptionResultOut(BaseModel):
    uid: str
    text: str
    correction: str
    quote: Optional[str] = None
    verifier_confirmed: Optional[bool] = None


class InterviewGrammarIssueOut(BaseModel):
    text: str
    message: str
    replacements: List[str] = Field(default_factory=list)
    # Character offset into the answer's transcript, re-anchored on read; null when the
    # phrase can no longer be located because the candidate edited the transcript.
    offset: Optional[int] = None


class InterviewDeliveryOut(BaseModel):
    score: Optional[int] = None
    words: int
    speaking_seconds: float
    words_per_minute: Optional[float] = None
    long_pauses: int
    pauses_per_100_words: Optional[float] = None
    grammar_available: bool
    grammar_errors_per_100_words: Optional[float] = None
    grammar_issues: List[InterviewGrammarIssueOut] = Field(default_factory=list)
    lexical_diversity: Optional[float] = None
    components: dict[str, int] = Field(default_factory=dict)


class InterviewSentenceFixOut(BaseModel):
    original: str
    improved: str
    note: str = ""
    reasons: List[str] = Field(default_factory=list)


class InterviewFeedbackOut(BaseModel):
    content_tips: List[str] = Field(default_factory=list)
    english_tip: Optional[str] = None


class InterviewAnswerOut(BaseModel):
    id: int
    question_id: int
    status: InterviewAnswerStatus
    created_at: datetime
    graded_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    raw_transcript: Optional[str] = None
    transcript: Optional[str] = None
    transcript_edited: bool = False
    glossary_corrections: List[InterviewGlossaryCorrectionOut] = Field(default_factory=list)
    delivery: Optional[InterviewDeliveryOut] = None
    content_score: Optional[int] = None
    content_band: Optional[ContentBand] = None
    key_point_results: List[InterviewKeyPointResultOut] = Field(default_factory=list)
    misconceptions_found: List[InterviewMisconceptionResultOut] = Field(default_factory=list)
    feedback: Optional[InterviewFeedbackOut] = None
    sentence_fixes: List[InterviewSentenceFixOut] = Field(default_factory=list)
    next_follow_up_question_id: Optional[int] = None
    error_message: Optional[str] = None


InterviewQuestionOut.model_rebuild()
