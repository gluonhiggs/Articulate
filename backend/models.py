from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
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

from backend.statuses import STATUS_MAX_LENGTH, AttemptStatus


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
    status: Mapped[str] = mapped_column(String(STATUS_MAX_LENGTH), default=AttemptStatus.PROCESSING, index=True)
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


class InterviewPack(Base):
    __tablename__ = "interview_packs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uid: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))
    level: Mapped[str] = mapped_column(String(20))
    job_description: Mapped[str] = mapped_column(Text, default="")
    author: Mapped[str] = mapped_column(String(100), default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    questions: Mapped[List["InterviewQuestion"]] = relationship(back_populates="pack", cascade="all, delete-orphan")
    glossary_terms: Mapped[List["InterviewGlossaryTerm"]] = relationship(
        back_populates="pack", cascade="all, delete-orphan"
    )
    sources: Mapped[List["InterviewSource"]] = relationship(back_populates="pack", cascade="all, delete-orphan")


class InterviewSource(Base):
    __tablename__ = "interview_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uid: Mapped[str] = mapped_column(String(36), index=True)
    pack_id: Mapped[int] = mapped_column(ForeignKey("interview_packs.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    pack: Mapped["InterviewPack"] = relationship(back_populates="sources")


class InterviewGlossaryTerm(Base):
    __tablename__ = "interview_glossary_terms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pack_id: Mapped[int] = mapped_column(ForeignKey("interview_packs.id"), index=True)
    term: Mapped[str] = mapped_column(String(100))
    aliases: Mapped[str] = mapped_column(Text, default="[]")  # JSON list of spoken forms

    pack: Mapped["InterviewPack"] = relationship(back_populates="glossary_terms")


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uid: Mapped[str] = mapped_column(String(36), index=True)
    pack_id: Mapped[int] = mapped_column(ForeignKey("interview_packs.id"), index=True)
    parent_question_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("interview_questions.id"), nullable=True, index=True
    )
    trigger_key_point_uid: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    topic: Mapped[str] = mapped_column(String(100), default="")
    text: Mapped[str] = mapped_column(Text)
    answer_seconds: Mapped[int] = mapped_column(Integer, default=120)
    position: Mapped[int] = mapped_column(Integer, default=0)
    retired: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    pack: Mapped["InterviewPack"] = relationship(back_populates="questions")
    key_points: Mapped[List["InterviewKeyPoint"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="InterviewKeyPoint.position"
    )
    misconceptions: Mapped[List["InterviewMisconception"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )
    follow_ups: Mapped[List["InterviewQuestion"]] = relationship(
        "InterviewQuestion", back_populates="parent", order_by="InterviewQuestion.position"
    )
    parent: Mapped[Optional["InterviewQuestion"]] = relationship(
        "InterviewQuestion", back_populates="follow_ups", remote_side="InterviewQuestion.id"
    )
    answers: Mapped[List["InterviewAnswer"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        foreign_keys="InterviewAnswer.question_id",
    )


class InterviewKeyPoint(Base):
    __tablename__ = "interview_key_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uid: Mapped[str] = mapped_column(String(36), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("interview_questions.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    weight: Mapped[int] = mapped_column(Integer, default=2)  # 3 core, 2 supporting, 1 detail
    source_quote: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quote_verified: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)

    question: Mapped["InterviewQuestion"] = relationship(back_populates="key_points")


class InterviewMisconception(Base):
    __tablename__ = "interview_misconceptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uid: Mapped[str] = mapped_column(String(36), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("interview_questions.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    correction: Mapped[str] = mapped_column(Text, default="")

    question: Mapped["InterviewQuestion"] = relationship(back_populates="misconceptions")


class InterviewAnswer(Base):
    __tablename__ = "interview_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("interview_questions.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="processing", index=True)
    audio_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    raw_transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transcript_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    word_timestamps: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    glossary_corrections: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    delivery_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    delivery_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    content_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content_band: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    key_point_results: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    misconceptions_found: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    proposer_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    sentence_fixes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    next_follow_up_question_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("interview_questions.id"), nullable=True
    )
    grader_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    verifier_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)
    grading_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    graded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    question: Mapped["InterviewQuestion"] = relationship(back_populates="answers", foreign_keys=[question_id])
