#!/usr/bin/env bash
set -e
PROFILE=${1:-laptop}
ENV_FILE=".env.$PROFILE"
if [ ! -f "$ENV_FILE" ]; then
  echo "Error: $ENV_FILE not found"
  exit 1
fi
export $(grep -v '^#' "$ENV_FILE" | xargs)
exec uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1 --reload
