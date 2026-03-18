"""
Singleton Ollama HTTP client.

  ┌────────────────────────────────────────────────────┐
  │  OllamaClient (module-level singleton)             │
  │  ─────────────────────────────────────────────     │
  │  _client: httpx.AsyncClient (persistent pool)      │
  │                                                    │
  │  generate(model, prompt, *, temperature,           │
  │           num_predict, timeout) → str              │
  │    ├─ POST /api/generate                           │
  │    ├─ on ConnectError → retry once (cold-start)    │
  │    └─ logs model, prompt_len, resp_len, latency_ms │
  │                                                    │
  │  close_if_initialized()  ← lifespan shutdown       │
  │    └─ no-op if generate() was never called        │
  └────────────────────────────────────────────────────┘
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


async def generate(
    base_url: str,
    model: str,
    prompt: str,
    *,
    temperature: float = 0.4,
    num_predict: int = 1024,
    num_ctx: int = 2048,
    timeout: float = 120.0,
) -> str:
    """
    Call Ollama /api/generate and return the response text.

    Retries once on ConnectError to handle Ollama cold-start.
    Raises RuntimeError on persistent failure.
    """
    client = _get_client()
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
            "num_ctx": num_ctx,
        },
    }
    url = f"{base_url}/api/generate"
    attempt = 0
    while True:
        attempt += 1
        t0 = time.monotonic()
        try:
            response = await client.post(
                url,
                json=payload,
                timeout=httpx.Timeout(timeout),
            )
            response.raise_for_status()
            data = response.json()
            raw = data.get("response", "")
            latency_ms = int((time.monotonic() - t0) * 1000)
            logger.info(
                "Ollama generate: model=%s prompt_len=%d resp_len=%d latency_ms=%d",
                model,
                len(prompt),
                len(raw),
                latency_ms,
            )
            return raw
        except httpx.ConnectError as exc:
            if attempt == 1:
                logger.warning("Ollama ConnectError (attempt %d), retrying: %s", attempt, exc)
                continue
            logger.exception("Ollama ConnectError after retry: %s", exc)
            raise RuntimeError(f"Ollama unreachable: {exc}") from exc
        except httpx.HTTPError as exc:
            logger.exception("Ollama HTTP error: %s", exc)
            raise RuntimeError(f"Ollama request failed: {exc}") from exc


async def close_if_initialized() -> None:
    """Close the persistent client. No-op if generate() was never called."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
        logger.info("Ollama client closed.")
