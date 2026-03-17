#!/usr/bin/env bash
set -e
PROFILE=${1:-laptop}
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
