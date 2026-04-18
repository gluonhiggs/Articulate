"""Capability gate for transcription mode.

The gate's job: if the saved preference is `local` but faster-whisper is not
available in this runtime (e.g. a packaged bundle that excluded the group),
run as `groq` for this session without overwriting data/mode. The saved
preference survives for environments where local IS supported.
"""
from __future__ import annotations

import pytest

from backend.main import _should_downgrade_to_groq


@pytest.mark.parametrize(
    "mode,fw_installed,expected",
    [
        ("local", False, True),   # the whole reason this gate exists
        ("local", True, False),   # source install with the group: run local
        ("groq", False, False),   # user already chose groq: no-op
        ("groq", True, False),    # user chose groq despite having fw: no-op
        (None, False, False),     # mode unset: gate should not fire
        (None, True, False),      # mode unset: gate should not fire
        ("", False, False),       # empty string: treat as unset
    ],
)
def test_capability_gate(mode: str | None, fw_installed: bool, expected: bool) -> None:
    assert _should_downgrade_to_groq(mode, fw_installed) is expected
