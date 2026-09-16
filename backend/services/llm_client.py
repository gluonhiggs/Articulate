"""
LLM HTTP client - any OpenAI-compatible cloud API (Gemini, Groq, OpenAI, etc.).

Uses one lazily created module-level httpx.AsyncClient; close_if_initialized()
closes it at lifespan shutdown.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_client: Optional[httpx.AsyncClient] = None


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
) -> str:
    """
    Call an OpenAI-compatible /chat/completions endpoint and return the
    assistant response text.

    Retries once on ConnectError. Raises RuntimeError if the endpoint stays
    unreachable, returns an HTTP error, or the response has no content.
    """
    client = _get_client()
    url = _chat_completions_url(base_url)

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": num_predict,
        "stream": False,
    }

    attempt = 0
    while True:
        attempt += 1
        t0 = time.monotonic()
        try:
            response = await client.post(
                url,
                json=payload,
                headers=headers,
                timeout=httpx.Timeout(timeout),
            )
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices")
            if not choices:
                raise RuntimeError(f"LLM returned no choices: {data}")
            content = choices[0].get("message", {}).get("content")
            if content is None:
                raise RuntimeError(f"LLM choice has no content: {choices[0]}")
            raw: str = content
            latency_ms = int((time.monotonic() - t0) * 1000)
            logger.info(
                "LLM generate: model=%s prompt_len=%d resp_len=%d latency_ms=%d",
                model,
                len(prompt),
                len(raw),
                latency_ms,
            )
            return raw
        except httpx.ConnectError as exc:
            if attempt == 1:
                logger.warning("LLM ConnectError (attempt %d), retrying: %s", attempt, exc)
                continue
            logger.exception("LLM ConnectError after retry: %s", exc)
            raise RuntimeError(f"LLM endpoint unreachable: {exc}") from exc
        except httpx.HTTPError as exc:
            logger.exception("LLM HTTP error: %s", exc)
            raise RuntimeError(f"LLM request failed: {exc}") from exc


async def close_if_initialized() -> None:
    """Close the persistent client. No-op if generate() was never called."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
        logger.info("LLM client closed.")
