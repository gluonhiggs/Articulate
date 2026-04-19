from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    part: Mapped[str] = mapped_column(String(10))  # "1", "2", "3", "custom"
    topic: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Part 1 grouping
    category: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # person/object/activity/place
    parent_question_id: Mapped[Optional[int]] = mapped_column(ForeignKey("questions.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    bullet_points: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string, Part 2 only
    topic_tag: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g. "environment", "technology"
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g. "IELTS community", "Cambridge 17"
    last_seen_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True
    )  # When this topic last appeared in real IELTS
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    attempts: Mapped[List["Attempt"]] = relationship(back_populates="question", cascade="all, delete-orphan")
    children: Mapped[List["Question"]] = relationship("Question", back_populates="parent")
    parent: Mapped[Optional["Question"]] = relationship(
        "Question",
        back_populates="children",
        remote_side="Question.id",
    )


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    audio_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fluency: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vocabulary: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    grammar: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pronunciation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    feedback_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    usage_errors: Mapped[Optional[str]] = mapped_column("error_highlights", Text, nullable=True)  # JSON
    word_timestamps: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="processing", index=True)  # processing | ready | failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)

    question: Mapped["Question"] = relationship(back_populates="attempts")


class DailyActivity(Base):
    __tablename__ = "daily_activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, unique=True)
    attempts_count: Mapped[int] = mapped_column(Integer, default=0)
    intensity: Mapped[int] = mapped_column(Integer, default=0)  # 0-4 for heatmap


class UserStats(Base):
    __tablename__ = "user_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    total_attempts: Mapped[int] = mapped_column(Integer, default=0)
    estimated_band: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
