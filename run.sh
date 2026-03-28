#!/usr/bin/env bash
# Usage: ./run.sh [auto|laptop|pc|gemini]
#
# auto (default): uses API mode if LLM_API_KEY is set in .env.gemini,
#                 falls back to GPU (pc) mode otherwise.
set -e
PROFILE=${1:-auto}

# ── Auto-detect mode ──────────────────────────────────────────────────────────
if [ "$PROFILE" = "auto" ]; then
  HAS_KEY=0
  if [ -f ".env.gemini" ]; then
    KEY_VALUE=$(grep '^LLM_API_KEY=' .env.gemini 2>/dev/null | cut -d'=' -f2 | tr -d ' ')
    # A real key: non-empty and not the placeholder
    if [ -n "$KEY_VALUE" ] && ! echo "$KEY_VALUE" | grep -q '^your-'; then
      HAS_KEY=1
    fi
  fi
  if [ "$HAS_KEY" = "1" ]; then
    PROFILE="gemini"
    echo "[auto] API key found  -> using API mode (no GPU)"
  else
    PROFILE="pc"
    echo "[auto] No API key     -> using GPU mode (Ollama)"
  fi
fi

ENV_FILE=".env.$PROFILE"
if [ ! -f "$ENV_FILE" ]; then
  echo "Error: $ENV_FILE not found"
  exit 1
fi
export $(grep -v '^#' "$ENV_FILE" | xargs)

SSL_ARGS=""
if [ -f certs/cert.pem ]; then
  SSL_ARGS="--ssl-certfile certs/cert.pem --ssl-keyfile certs/key.pem"
  echo "HTTPS enabled (certs/cert.pem found)"
else
  echo "WARNING: certs/ not found, running HTTP only (phone mic will not work)"
fi

exec uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1 --reload $SSL_ARGS
