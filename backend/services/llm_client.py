"""
LLM HTTP client - any OpenAI-compatible cloud API (Gemini, Groq, OpenAI, etc.).

Uses one lazily created module-level httpx.AsyncClient; close_if_initialized()
closes it at lifespan shutdown.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

_client: Optional[httpx.AsyncClient] = None

_RETRY_BACKOFF_SECONDS = (2.0, 6.0)
_MAX_RETRY_AFTER_SECONDS = 20.0
_DAILY_QUOTA_RE = re.compile(r"per\s*day", re.IGNORECASE)


class LLMRateLimitError(RuntimeError):
    """The provider kept answering 429 after retries (free-tier quota or rate limit)."""


class LLMOutputError(RuntimeError):
    """The provider answered, but the output was truncated or not the requested JSON."""


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient()
    return _client


def _chat_completions_url(base_url: str) -> str:
    """
    Build the chat completions endpoint from a base URL.

    Cloud APIs expose a base that already includes a version segment, so
    appending another /v1 would break the path:
    - OpenAI   https://api.openai.com/v1                   -> .../chat/completions
    - Groq     https://api.groq.com/openai/v1              -> .../chat/completions
    - Gemini   https://generativelanguage.../v1beta/openai -> .../chat/completions
    Bare base URLs get /v1/chat/completions appended.
    """
    base = base_url.rstrip("/")
    versioned_suffixes = ("/v1", "/openai", "/v1beta/openai")
    if any(base.endswith(s) for s in versioned_suffixes):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def _retry_delay(response: httpx.Response, retry_index: int) -> float:
    retry_after = response.headers.get("retry-after")
    if retry_after:
        try:
            return min(max(float(retry_after), 0.0), _MAX_RETRY_AFTER_SECONDS)
        except ValueError:
            pass
    return _RETRY_BACKOFF_SECONDS[retry_index]


async def _post_chat_completion(url: str, payload: dict, api_key: str, timeout: float) -> dict:
    """
    POST a chat completion and return the decoded response body.

    Retries once on ConnectError and up to twice on 429/5xx. Raises LLMRateLimitError
    when 429 persists and RuntimeError for any other failure.
    """
    client = _get_client()
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    model = payload.get("model")

    connect_retried = False
    dropped_reasoning_effort = False
    status_retries = 0
    while True:
        try:
            response = await client.post(url, json=payload, headers=headers, timeout=httpx.Timeout(timeout))
        except httpx.ConnectError as exc:
            if not connect_retried:
                connect_retried = True
                logger.warning("LLM ConnectError, retrying: %s", exc)
                continue
            logger.exception("LLM ConnectError after retry: %s", exc)
            raise RuntimeError(f"LLM endpoint unreachable: {exc}") from exc
        except httpx.HTTPError as exc:
            logger.exception("LLM HTTP error: %s", exc)
            raise RuntimeError(f"LLM request failed: {exc}") from exc

        status = response.status_code
        # A per-day quota cannot recover within the retry window, unlike a per-minute rate limit.
        if status == 429 and _DAILY_QUOTA_RE.search(response.text):
            raise LLMRateLimitError(f"LLM daily free-tier quota exhausted for model {model}")
        if (status == 429 or status >= 500) and status_retries < len(_RETRY_BACKOFF_SECONDS):
            delay = _retry_delay(response, status_retries)
            status_retries += 1
            logger.warning("LLM HTTP %d from model=%s, retry %d in %.1fs", status, model, status_retries, delay)
            await asyncio.sleep(delay)
            continue
        if status == 429:
            raise LLMRateLimitError(f"LLM rate limit or free-tier quota exceeded for model {model}")
        # Support for reasoning_effort varies per model (gemini-3.5-flash-lite rejects "none"
        # with a 400 that gemini-3.6-flash accepts), so drop it rather than fail the request.
        if status == 400 and "reasoning_effort" in payload and not dropped_reasoning_effort:
            dropped_reasoning_effort = True
            effort = payload.pop("reasoning_effort")
            logger.warning("Model %s rejected reasoning_effort=%r; retrying without it", model, effort)
            continue
        if status >= 400:
            raise RuntimeError(f"LLM request failed: HTTP {status}: {response.text[:500]}")
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(f"LLM returned a non-JSON response: {response.text[:200]}") from exc


def _first_choice(data: dict) -> dict:
    choices = data.get("choices")
    if not choices:
        raise RuntimeError(f"LLM returned no choices: {data}")
    return choices[0]


async def generate(
    base_url: str,
    model: str,
    prompt: str,
    *,
    api_key: str = "",
    temperature: float = 0.4,
    num_predict: int = 1024,
    num_ctx: int = 2048,  # ignored (cloud APIs set context server-side)
    num_gpu: int = 0,  # ignored
    timeout: float = 120.0,
    reasoning_effort: str = "",
) -> str:
    """
    Call an OpenAI-compatible /chat/completions endpoint and return the
    assistant response text.

    reasoning_effort ("none"/"minimal"/"low"/...) is only sent when non-empty; on a
    thinking model it decides how much of max_tokens is spent before the visible answer.

    Retries once on ConnectError and up to twice on 429/5xx. Raises RuntimeError
    (LLMRateLimitError for a persistent 429) if the endpoint stays unreachable,
    returns an HTTP error, or the response has no content.
    """
    payload: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": num_predict,
        "stream": False,
    }
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    t0 = time.monotonic()
    data = await _post_chat_completion(_chat_completions_url(base_url), payload, api_key, timeout)
    choice = _first_choice(data)
    content = choice.get("message", {}).get("content")
    if content is None:
        raise RuntimeError(f"LLM choice has no content: {choice}")
    logger.info(
        "LLM generate: model=%s prompt_len=%d resp_len=%d latency_ms=%d",
        model,
        len(prompt),
        len(content),
        int((time.monotonic() - t0) * 1000),
    )
    return content


_CODE_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


def parse_json_object(raw: str) -> dict:
    """Decode a JSON object from model output, tolerating a surrounding code fence. Raises ValueError."""
    fenced = _CODE_FENCE_RE.match(raw)
    data = json.loads(fenced.group(1) if fenced else raw.strip())
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    return data


async def generate_json(
    *,
    base_url: str,
    model: str,
    prompt: str,
    api_key: str,
    schema: dict,
    schema_name: str,
    strict: bool = False,
    temperature: float = 0.0,
    max_tokens: int = 8192,
    timeout: float = 120.0,
    reasoning_effort: str = "",
) -> dict[str, Any]:
    """
    Request a JSON object constrained by a JSON schema (response_format json_schema).

    reasoning_effort ("none"/"minimal"/"low"/...) is only sent when non-empty; on a
    thinking model it decides how much of max_tokens is spent before the visible answer.

    Raises LLMOutputError when the output is truncated (finish_reason "length") or is
    still not a JSON object after one re-request, plus the errors of generate().
    """
    json_schema: dict[str, Any] = {"name": schema_name, "schema": schema}
    if strict:
        json_schema["strict"] = True
    payload: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
        "response_format": {"type": "json_schema", "json_schema": json_schema},
    }
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    url = _chat_completions_url(base_url)

    parse_error: ValueError | None = None
    for _ in range(2):
        t0 = time.monotonic()
        data = await _post_chat_completion(url, payload, api_key, timeout)
        choice = _first_choice(data)
        finish_reason = choice.get("finish_reason")
        content = choice.get("message", {}).get("content") or ""
        logger.info(
            "LLM generate_json: model=%s schema=%s prompt_len=%d resp_len=%d finish=%s latency_ms=%d",
            model,
            schema_name,
            len(prompt),
            len(content),
            finish_reason,
            int((time.monotonic() - t0) * 1000),
        )
        if finish_reason == "length":
            raise LLMOutputError(f"{model} output was cut off at max_tokens={max_tokens}")
        try:
            return parse_json_object(content)
        except ValueError as exc:
            parse_error = exc
            logger.warning("LLM %s returned invalid JSON: %s", model, exc)
    raise LLMOutputError(f"{model} did not return a valid JSON object: {parse_error}")


async def close_if_initialized() -> None:
    """Close the persistent client. No-op if generate() was never called."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
        logger.info("LLM client closed.")
