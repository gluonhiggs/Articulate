"""The frontend mirrors the status vocabulary by hand; this fails when the copies drift."""

from __future__ import annotations

import re
from datetime import datetime
from types import SimpleNamespace

import pytest

from backend.constants import PROJECT_ROOT
from backend.statuses import AttemptStatus, is_failed, is_processing

STATUS_MODULE = PROJECT_ROOT / "frontend" / "src" / "types" / "attemptStatus.ts"


@pytest.fixture(scope="module")
def ts_source() -> str:
    if not (PROJECT_ROOT / "frontend" / "src").exists():
        pytest.skip("frontend sources not present")
    assert STATUS_MODULE.exists(), f"{STATUS_MODULE} moved - point this test at its new home"
    return STATUS_MODULE.read_text(encoding="utf-8")


def _ts_array(name: str, source: str) -> list[str]:
    match = re.search(rf"export const {name} = \[(.*?)\] as const", source, re.DOTALL)
    assert match, f"{name} not found in {STATUS_MODULE}"
    return re.findall(r"'([^']+)'", match.group(1))


def _ts_union(name: str, source: str, arrays: dict[str, list[str]]) -> set[str]:
    """An as-const array that may spread the other arrays, as AttemptStatus is derived from."""
    match = re.search(rf"export const {name} = \[(.*?)\] as const", source, re.DOTALL)
    assert match, f"{name} not found in {STATUS_MODULE}"
    body = match.group(1)
    values = set(re.findall(r"'([^']+)'", body))
    for spread in re.findall(r"\.\.\.(\w+)", body):
        assert spread in arrays, f"{name} spreads unknown {spread}"
        values.update(arrays[spread])
    return values


def test_frontend_knows_every_status(ts_source: str) -> None:
    processing = _ts_array("ATTEMPT_PROCESSING_STATUSES", ts_source)
    failed = _ts_array("ATTEMPT_FAILED_STATUSES", ts_source)

    assert set(processing) == {s.value for s in AttemptStatus if is_processing(s)}
    assert set(failed) == {s.value for s in AttemptStatus if is_failed(s)}

    everything = _ts_union(
        "ATTEMPT_STATUSES",
        ts_source,
        {"ATTEMPT_PROCESSING_STATUSES": processing, "ATTEMPT_FAILED_STATUSES": failed},
    )
    assert everything == {s.value for s in AttemptStatus}


def test_an_unknown_status_still_serializes_instead_of_failing_the_list() -> None:
    """A status a newer backend writes must degrade to one odd card, not 500 the history."""
    from backend.schemas import AttemptOut, AttemptStatusOut

    row = SimpleNamespace(
        id=1,
        question_id=1,
        audio_path=None,
        transcript=None,
        score=None,
        fluency=None,
        vocabulary=None,
        grammar=None,
        pronunciation=None,
        feedback_text=None,
        usage_errors=None,
        word_timestamps=None,
        duration_seconds=None,
        status="failed:something_new",
        created_at=datetime(2026, 9, 21, 6, 0, 0),
    )

    assert AttemptOut.model_validate(row).status == "failed:something_new"
    assert AttemptStatusOut.model_validate(row).status == "failed:something_new"
