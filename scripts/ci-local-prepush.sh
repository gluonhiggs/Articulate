#!/usr/bin/env bash
#
# Invoked by pre-commit's pre-push stage (see .pre-commit-config.yaml).
#
# Two modes:
#   - Tag push matching v*.*.* → `make release-cpu` (full bundle + installer).
#   - Branch push (refs/heads/*) → `make ci` (lint + typecheck + tests).
#   - Anything else             → exit 0.
#
# pre-commit sets PRE_COMMIT_REMOTE_BRANCH to the remote ref being pushed
# (e.g. refs/heads/main or refs/tags/v0.1.6). See:
# https://pre-commit.com/#pre-commit-during-push
#
# Bypass with `git push --no-verify` in emergencies.
#
set -euo pipefail

REMOTE_BRANCH="${PRE_COMMIT_REMOTE_BRANCH:-}"

case "$REMOTE_BRANCH" in
  refs/tags/v*.*.*)
    echo "[pre-push] Tag push detected: $REMOTE_BRANCH"
    echo "[pre-push] Running 'make release-cpu' to build + verify the bundle."
    echo "[pre-push] To bypass: git push --no-verify (NOT recommended for tags)."
    echo ""
    exec make release-cpu
    ;;
  refs/heads/*)
    echo "[pre-push] Branch push detected: $REMOTE_BRANCH"
    echo "[pre-push] Running 'make ci' to mirror GitHub Actions ci.yml."
    echo "[pre-push] To bypass: git push --no-verify."
    echo ""
    exec make ci
    ;;
  *)
    # Non-version tags, notes, other refs: skip.
    exit 0
    ;;
esac
