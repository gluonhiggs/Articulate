"""
Tag questions written before the skill vocabulary existed.

Usage: python -m backend.scripts.tag_questions [--apply]

Without --apply it only reports what would change. Re-running is safe: the tags are
derived from the question and its key points, so the same text always gives the same
result.
"""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from backend.database import AsyncSessionLocal  # noqa: E402
from backend.models import InterviewQuestion  # noqa: E402
from backend.services.skills import find_skills, label_of  # noqa: E402


def skills_of(question: InterviewQuestion) -> list[str]:
    parts = [question.text, *(key_point.text for key_point in question.key_points)]
    return find_skills(" ".join(parts))


async def tag_questions(apply_changes: bool) -> int:
    changed = 0
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(InterviewQuestion)
            .options(selectinload(InterviewQuestion.key_points))
            .order_by(InterviewQuestion.id)
        )
        for question in result.scalars().all():
            stored = json.loads(question.tags or "[]")
            found = skills_of(question)
            if stored == found:
                continue
            changed += 1
            labels = ", ".join(label_of(skill) for skill in found) or "(none)"
            print(f"question {question.id}: {labels}")
            print(f"    {question.text[:90]}")
            if apply_changes:
                question.tags = json.dumps(found)
        if apply_changes:
            await session.commit()
    return changed


async def main() -> None:
    apply_changes = "--apply" in sys.argv
    changed = await tag_questions(apply_changes)
    print()
    if apply_changes:
        print(f"{changed} question(s) tagged.")
    else:
        print(f"{changed} question(s) would be tagged. Re-run with --apply to write them.")


if __name__ == "__main__":
    asyncio.run(main())
