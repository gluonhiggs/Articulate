from __future__ import annotations

import json
from datetime import datetime
from typing import Any, List, Optional

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


# ---------------------------------------------------------------------------
# Create question request
# ---------------------------------------------------------------------------


class QuestionCreateIn(BaseModel):
    text: str
    part: str
    topic: Optional[str] = None
    category: Optional[str] = None
    parent_question_id: Optional[int] = None
    bullet_points: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Attempt schemas
# ---------------------------------------------------------------------------


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
    error_highlights: Optional[str] = None
    word_timestamps: Optional[str] = None
    duration_seconds: Optional[int] = None
    status: str
    created_at: datetime

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
    error_highlights: Optional[str] = None
    transcript: Optional[str] = None

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


class SystemInfoOut(BaseModel):
    profile: str
    whisper_model: str
    whisper_device: str
    ollama_model: str
