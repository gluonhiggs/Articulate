"""Rank the skills a candidate should drill, and find the questions for them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from backend.models import InterviewAnswer, InterviewPack, InterviewQuestion
from backend.services.skills import find_skills, label_of

WEAK_SCORE = 70


@dataclass(frozen=True)
class SkillRow:
    skill: str
    label: str
    question_count: int
    in_job: bool
    in_cv: bool
    best_score: Optional[int]
    answered: int

    @property
    def state(self) -> str:
        """Why this row sits where it does, in one word the page can show."""
        if self.question_count == 0:
            return "no_questions"
        if self.answered == 0:
            return "unpractised"
        if self.best_score is not None and self.best_score < WEAK_SCORE:
            return "weak"
        return "ready"


_STATE_ORDER = {"no_questions": 0, "weak": 1, "unpractised": 2, "ready": 3}


def sort_key(row: SkillRow) -> tuple:
    """
    Worst first, and a skill the job asks for always above one it does not.

    A gap the client will probe is the most expensive thing a candidate can leave
    unpractised, so it sits at the top even when there is nothing to practise yet.
    """
    return (
        0 if row.in_job else 1,
        _STATE_ORDER[row.state],
        row.best_score if row.best_score is not None else -1,
        -row.question_count,
        row.label.lower(),
    )


def question_tags(question: InterviewQuestion, stored: Sequence[str]) -> list[str]:
    return list(stored) if stored else find_skills(question.text)


def build_rows(
    tags_by_question: dict[int, Sequence[str]],
    scores_by_question: dict[int, list[int]],
    job_skills: Iterable[str],
    cv_skills: Iterable[str],
) -> list[SkillRow]:
    """One row per skill named by a question, by the job, or by the CV."""
    job = set(job_skills)
    cv = set(cv_skills)

    counts: dict[str, int] = {}
    answered: dict[str, int] = {}
    best: dict[str, int] = {}
    for question_id, tags in tags_by_question.items():
        scores = scores_by_question.get(question_id, [])
        for skill in tags:
            counts[skill] = counts.get(skill, 0) + 1
            if scores:
                answered[skill] = answered.get(skill, 0) + 1
                best[skill] = max(best.get(skill, 0), max(scores))

    rows = [
        SkillRow(
            skill=skill,
            label=label_of(skill),
            question_count=counts.get(skill, 0),
            in_job=skill in job,
            in_cv=skill in cv,
            best_score=best.get(skill),
            answered=answered.get(skill, 0),
        )
        for skill in set(counts) | job | cv
    ]
    return sorted(rows, key=sort_key)


def job_skills_of(pack: Optional[InterviewPack]) -> list[str]:
    if pack is None:
        return []
    return find_skills(" ".join([pack.title, pack.job_description]))


def matching_questions(
    questions: Iterable[InterviewQuestion],
    tags_by_question: dict[int, Sequence[str]],
    wanted: Sequence[str],
) -> list[InterviewQuestion]:
    """Top-level questions carrying any of the wanted skills, most matches first."""
    chosen = set(wanted)
    scored = []
    for question in questions:
        if question.retired or question.parent_question_id is not None:
            continue
        overlap = chosen.intersection(tags_by_question.get(question.id, []))
        if overlap:
            scored.append((-len(overlap), question.id, question))
    return [question for _, _, question in sorted(scored, key=lambda item: (item[0], item[1]))]


def latest_scores(answers: Iterable[InterviewAnswer]) -> dict[int, list[int]]:
    scores: dict[int, list[int]] = {}
    for answer in answers:
        if answer.content_score is not None:
            scores.setdefault(answer.question_id, []).append(answer.content_score)
    return scores
