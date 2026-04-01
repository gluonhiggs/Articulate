from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, field_validator, model_validator


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
    error_highlights: Optional[List[Any]] = None
    word_timestamps: Optional[List[Any]] = None
    duration_seconds: Optional[int] = None
    status: str
    created_at: datetime

    @field_validator("error_highlights", "word_timestamps", mode="before")
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
    error_highlights: Optional[List[Any]] = None
    transcript: Optional[str] = None

    @field_validator("error_highlights", mode="before")
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
    is_flagged: bool


class PronunciationOut(BaseModel):
    words: List[PronunciationWord]


class SystemInfoOut(BaseModel):
    profile: str
    whisper_model: str
    whisper_device: str
    llm_model: str
    is_low_accuracy: bool = False
    llm_reachable: bool = False


class SetModelRequest(BaseModel):
    model: str
