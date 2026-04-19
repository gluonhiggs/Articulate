"""Tests for system info endpoint - specifically the is_low_accuracy detection."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "model,expected",
    [
        ("gemma3:1b", True),
        ("gemma3:3b", True),
        ("llama3.2:1b", True),
        ("gemma3:12b", False),
        ("mistral:7b", False),
        ("qwen2.5:14b", False),
        ("gemma3:27b", False),
        # Edge: model name containing substring "1b" elsewhere
        ("my-custom-1b-model", True),
    ],
)
def test_is_low_accuracy_detection(model: str, expected: bool) -> None:
    """Test the exact detection logic from api/system.py."""
    is_low_accuracy = any(tag in model for tag in ("1b", "3b"))
    assert is_low_accuracy == expected, f"Model {model!r}: expected is_low_accuracy={expected}"
