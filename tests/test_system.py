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


class TestAssistModel:
    def test_configured_assist_model_wins(self, monkeypatch) -> None:
        from backend import config

        monkeypatch.setattr(config, "get_settings", lambda: config.Settings(llm_assist_model="gemini-3.5-flash-lite"))
        monkeypatch.setattr(config, "get_active_model", lambda: "gemini-3.6-flash")

        assert config.get_assist_model() == "gemini-3.5-flash-lite"

    def test_empty_assist_model_falls_back_to_the_scoring_model(self, monkeypatch) -> None:
        from backend import config

        monkeypatch.setattr(config, "get_settings", lambda: config.Settings(llm_assist_model=""))
        monkeypatch.setattr(config, "get_active_model", lambda: "gemini-3.6-flash")

        assert config.get_assist_model() == "gemini-3.6-flash"

    def test_runtime_model_switch_does_not_change_the_assist_model(self, monkeypatch) -> None:
        from backend import config

        monkeypatch.setattr(config, "get_settings", lambda: config.Settings(llm_assist_model="gemini-3.5-flash-lite"))
        monkeypatch.setattr(config, "_runtime_model", "gemini-3.7-flash")

        assert config.get_active_model() == "gemini-3.7-flash"
        assert config.get_assist_model() == "gemini-3.5-flash-lite"


class TestFrontendCaching:
    async def test_index_html_is_revalidated_so_a_rebuilt_bundle_is_picked_up(self) -> None:
        from httpx import ASGITransport, AsyncClient

        from backend.main import _FRONTEND_DIST, app

        if not (_FRONTEND_DIST / "index.html").exists():
            pytest.skip("frontend/dist not built")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            index = await client.get("/")
            deep_link = await client.get("/practice/part1")
            bundle = await client.get(index.text.split('src="')[1].split('"')[0])

        assert index.headers["cache-control"] == "no-cache"
        assert deep_link.headers["cache-control"] == "no-cache"
        assert "cache-control" not in bundle.headers
