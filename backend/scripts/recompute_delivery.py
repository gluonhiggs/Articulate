"""
Re-measure delivery for answers graded before the current grammar filter.

Usage: python -m backend.scripts.recompute_delivery [--apply]

Without --apply it only reports what would change. Stored sentence rewrites are left
alone, so an LLM call already paid for is never discarded.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from backend.config import get_settings  # noqa: E402
from backend.database import AsyncSessionLocal  # noqa: E402
from backend.models import InterviewAnswer, InterviewGlossaryTerm, InterviewQuestion  # noqa: E402
from backend.services.grammar import check_grammar  # noqa: E402
from backend.services.interview_delivery import compute_delivery  # noqa: E402
from backend.services.interview_packs import glossary_entries  # noqa: E402


def issue_texts(details: Optional[str]) -> list[str]:
    if not details:
        return []
    stored = json.loads(details).get("grammar_issues") or []
    return [str(issue.get("text") or "") for issue in stored]


async def ignore_terms_for(session, question_id: int) -> list[str]:
    question = await session.get(InterviewQuestion, question_id)
    if question is None:
        return []
    result = await session.execute(
        select(InterviewGlossaryTerm).where(InterviewGlossaryTerm.pack_id == question.pack_id)
    )
    entries = glossary_entries(result.scalars().all())
    return [entry.term for entry in entries] + [alias for entry in entries for alias in entry.aliases]


async def recompute(apply_changes: bool) -> int:
    gap_threshold = get_settings().gap_threshold
    changed = 0

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(InterviewAnswer)
            .where(
                InterviewAnswer.delivery_details.is_not(None),
                InterviewAnswer.word_timestamps.is_not(None),
                InterviewAnswer.raw_transcript.is_not(None),
            )
            .order_by(InterviewAnswer.id)
        )
        for answer in result.scalars().all():
            words = json.loads(answer.word_timestamps)
            terms = await ignore_terms_for(session, answer.question_id)
            issues = check_grammar(answer.raw_transcript, terms)
            delivery = compute_delivery(words, issues, gap_threshold)

            before = issue_texts(answer.delivery_details)
            after = [str(issue["text"]) for issue in delivery["grammar_issues"]]
            if before == after and answer.delivery_score == delivery["score"]:
                print(f"answer {answer.id}: unchanged ({len(after)} issue(s), score {answer.delivery_score})")
                continue

            changed += 1
            dropped = [text for text in before if text not in after]
            print(
                f"answer {answer.id}: score {answer.delivery_score} -> {delivery['score']}, "
                f"issues {len(before)} -> {len(after)}"
            )
            if dropped:
                print(f"  dropped: {', '.join(repr(text) for text in dropped)}")
            if after:
                print(f"  kept   : {', '.join(repr(text) for text in after)}")

            if apply_changes:
                answer.delivery_details = json.dumps(delivery)
                answer.delivery_score = delivery["score"]

        if apply_changes:
            await session.commit()

    return changed


async def main() -> None:
    apply_changes = "--apply" in sys.argv
    changed = await recompute(apply_changes)
    print()
    if not apply_changes:
        print(f"{changed} answer(s) would change. Re-run with --apply to write them.")
    else:
        print(f"{changed} answer(s) updated.")


if __name__ == "__main__":
    asyncio.run(main())
