"""Unit tests for ai_assist.py — specifically the JSON repair logic."""
from __future__ import annotations

import json

import pytest

from backend.services.ai_assist import _repair_vocab_json


def test_repair_valid_json_round_trips():
    """Already-valid JSON is returned without modification."""
    raw = (
        '{"vocabulary": [{"term": "proliferate", "type": "verb",'
        ' "definition": "grow rapidly", "example": "Cities proliferate."}]}'
    )
    repaired = _repair_vocab_json(raw)
    data = json.loads(repaired)
    assert "vocabulary" in data
    assert len(data["vocabulary"]) == 1
    assert data["vocabulary"][0]["term"] == "proliferate"


def test_repair_truncated_missing_close_array_and_brace():
    """JSON truncated after last item — missing ] and }."""
    raw = (
        '{"vocabulary": [{"term": "proliferate", "type": "verb",'
        ' "definition": "grow rapidly", "example": "test"}'
        # missing ]} at end
    )
    repaired = _repair_vocab_json(raw)
    data = json.loads(repaired)
    assert "vocabulary" in data
    assert len(data["vocabulary"]) == 1


def test_repair_truncated_two_items_third_partial():
    """Three items where third is cut mid-value — only two complete items recovered."""
    raw = (
        '{"vocabulary": ['
        '{"term": "a", "type": "noun", "definition": "def a", "example": "ex a"}, '
        '{"term": "b", "type": "verb", "definition": "def b", "example": "ex b"}, '
        '{"term": "c", "type": "adj", "definition":'  # truncated here
    )
    repaired = _repair_vocab_json(raw)
    data = json.loads(repaired)
    assert len(data["vocabulary"]) == 2


def test_repair_no_json_raises_value_error():
    """No JSON at all raises ValueError."""
    with pytest.raises(ValueError, match="No JSON found"):
        _repair_vocab_json("just random text without any braces")


def test_repair_no_complete_object_raises_value_error():
    """Opening brace but no closing brace raises ValueError."""
    with pytest.raises(ValueError, match="No complete JSON object found"):
        _repair_vocab_json('{"vocabulary": [{"term": "no closing brace ever')
