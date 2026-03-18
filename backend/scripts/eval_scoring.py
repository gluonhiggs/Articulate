"""
Scoring eval script — verifies prompt quality against golden test cases.
Usage: python -m backend.scripts.eval_scoring

Requires Ollama to be running. Not for CI — run manually after prompt changes.
"""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.services.scoring import score_attempt

CASES_FILE = ROOT / "data" / "scoring_testcases.json"


async def run_eval():
    cases = json.loads(CASES_FILE.read_text())
    passed = 0
    for case in cases:
        print(f"\n[{case['id']}]")
        try:
            result = await score_attempt(
                question_text=case["question"],
                part=case["part"],
                transcript=case["transcript"],
                flagged_words=[],
            )
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        score = result.get("score")
        lo, hi = case["expect_score_range"]
        score_ok = score is not None and lo <= score <= hi

        error_ok = True
        if case.get("expect_error_word"):
            words = [h["word"] for h in result.get("error_highlights", [])]
            corrections = {h["word"]: h["correction"] for h in result.get("error_highlights", [])}
            expected_word = case["expect_error_word"]
            expected_correction = case.get("expect_correction", "")
            error_ok = (
                expected_word in words
                and corrections.get(expected_word, "MISSING") == expected_correction
            )

        ok = score_ok and error_ok
        if ok:
            passed += 1
        status = "PASS" if ok else "FAIL"
        print(
            f"  {status}  score={score} (expected {lo}–{hi})  "
            f"errors={[h['word'] for h in result.get('error_highlights', [])]}"
        )

    total = len(cases)
    print(f"\n{'='*40}")
    print(f"Result: {passed}/{total} passed")
    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_eval())
