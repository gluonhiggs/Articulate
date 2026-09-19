"""llm_client retry and error classification, with httpx.MockTransport instead of a real provider."""

from __future__ import annotations

import json

import httpx
import pytest

from backend.services import llm_client
from backend.services.llm_client import LLMOutputError, LLMRateLimitError

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}


def _completion(content: str, finish_reason: str = "stop") -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}, "finish_reason": finish_reason}]})


@pytest.fixture
async def provider(monkeypatch):
    """Queue responses (or exceptions to raise) for the shared client and record requests and backoff sleeps."""
    state = {"responses": [], "requests": [], "sleeps": []}

    def handler(request: httpx.Request) -> httpx.Response:
        state["requests"].append(request)
        response = state["responses"].pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    async def fake_sleep(seconds: float) -> None:
        state["sleeps"].append(seconds)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(llm_client, "_client", client)
    monkeypatch.setattr(llm_client.asyncio, "sleep", fake_sleep)
    yield state
    await client.aclose()


async def _generate_json(**overrides):
    kwargs = dict(
        base_url="https://api.groq.com/openai/v1",
        model="openai/gpt-oss-120b",
        prompt="grade this",
        api_key="key",
        schema=SCHEMA,
        schema_name="check",
    )
    kwargs.update(overrides)
    return await llm_client.generate_json(**kwargs)


async def test_generate_json_sends_json_schema_and_parses_fenced_output(provider):
    provider["responses"] = [_completion('```json\n{"ok": true}\n```')]

    assert await _generate_json(strict=True) == {"ok": True}

    [request] = provider["requests"]
    assert str(request.url) == "https://api.groq.com/openai/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer key"
    body = json.loads(request.content)
    assert body["max_tokens"] == 8192
    assert body["temperature"] == 0.0
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "check", "schema": SCHEMA, "strict": True},
    }


async def test_non_strict_schema_omits_strict_flag(provider):
    provider["responses"] = [_completion('{"ok": false}')]
    await _generate_json()
    body = json.loads(provider["requests"][0].content)
    assert "strict" not in body["response_format"]["json_schema"]


async def test_429_then_success_retries_with_backoff(provider):
    provider["responses"] = [httpx.Response(429), httpx.Response(503), _completion('{"ok": true}')]
    assert await _generate_json() == {"ok": True}
    assert provider["sleeps"] == [2.0, 6.0]


async def test_retry_after_header_is_honored_and_capped(provider):
    provider["responses"] = [
        httpx.Response(429, headers={"retry-after": "3"}),
        httpx.Response(429, headers={"retry-after": "120"}),
        _completion('{"ok": true}'),
    ]
    await _generate_json()
    assert provider["sleeps"] == [3.0, 20.0]


async def test_persistent_429_raises_rate_limit_error(provider):
    provider["responses"] = [httpx.Response(429) for _ in range(3)]
    with pytest.raises(LLMRateLimitError):
        await _generate_json()
    assert len(provider["requests"]) == 3


async def test_persistent_5xx_raises_runtime_error_not_rate_limit(provider):
    provider["responses"] = [httpx.Response(500, text="boom") for _ in range(3)]
    with pytest.raises(RuntimeError) as excinfo:
        await _generate_json()
    assert not isinstance(excinfo.value, LLMRateLimitError)
    assert len(provider["requests"]) == 3


async def test_client_error_is_not_retried(provider):
    provider["responses"] = [httpx.Response(401, text="bad key")]
    with pytest.raises(RuntimeError, match="HTTP 401"):
        await _generate_json()
    assert len(provider["requests"]) == 1
    assert provider["sleeps"] == []


async def test_truncated_output_raises_output_error(provider):
    provider["responses"] = [_completion('{"ok": tr', finish_reason="length")]
    with pytest.raises(LLMOutputError, match="max_tokens"):
        await _generate_json()
    assert len(provider["requests"]) == 1


async def test_invalid_json_is_requested_once_more(provider):
    provider["responses"] = [_completion("not json"), _completion('{"ok": true}')]
    assert await _generate_json() == {"ok": True}
    assert len(provider["requests"]) == 2


async def test_invalid_json_twice_raises_output_error(provider):
    provider["responses"] = [_completion("[1, 2]"), _completion("still not json")]
    with pytest.raises(LLMOutputError):
        await _generate_json()


async def test_connect_error_is_retried_once(provider):
    provider["responses"] = [httpx.ConnectError("offline"), _completion('{"ok": true}')]
    assert await _generate_json() == {"ok": True}
    assert len(provider["requests"]) == 2


async def test_generate_keeps_returning_plain_text(provider):
    provider["responses"] = [httpx.Response(429), _completion("Band 6 feedback")]
    text = await llm_client.generate(
        "https://generativelanguage.googleapis.com/v1beta/openai", "gemma", "prompt", api_key="k", num_predict=50
    )
    assert text == "Band 6 feedback"
    body = json.loads(provider["requests"][-1].content)
    assert body["max_tokens"] == 50
    assert "response_format" not in body
