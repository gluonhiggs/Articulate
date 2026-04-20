# Articulate — contributor workflow targets.
#
# The primary verbs (see `make help`) mirror what CI runs so a local pass
# gives you confidence CI won't fail. Sub-targets (install-backend,
# test-backend, typecheck-frontend, etc.) exist for composition and
# debugging; most contributors only need the primary verbs.
#
# On Windows: install Make via Git Bash (`pacman -S make`) or `scoop install
# make`. Git Bash is required anyway for pre-commit hooks.
# On Linux/macOS: system `make` works out of the box.

SHELL := /bin/bash

.DEFAULT_GOAL := help
.PHONY: help \
        install install-backend install-frontend install-electron \
        install-build install-build-gpu install-hooks \
        check check-backend typecheck-frontend typecheck-electron \
        format \
        test test-backend test-frontend \
        ci \
        frontend bundle-cpu bundle-gpu verify-cpu verify-gpu electron-package \
        release-cpu release-gpu \
        tag \
        clean

# ── Help ──────────────────────────────────────────────────────────────────────

help:
	@echo "Articulate — contributor targets"
	@echo ""
	@echo "  Primary verbs:"
	@echo "    make install         One-time dev env setup (backend + frontend + electron + hooks)"
	@echo "    make test            Run all tests (backend pytest + frontend vitest)"
	@echo "    make check           Lint + typecheck everything"
	@echo "    make format          Auto-fix style (ruff format + ruff --fix)"
	@echo "    make ci              check + test. Run before you push."
	@echo "    make release-cpu     Full PyInstaller + electron installer, CPU variant (~10 min)"
	@echo "    make release-gpu     Full PyInstaller + electron installer, GPU variant (~15 min)"
	@echo "    make tag VERSION=x.y.z  Bump all version strings, commit, and tag"
	@echo ""
	@echo "  Sub-targets (for composition / debugging):"
	@echo "    install-backend / install-frontend / install-electron / install-hooks"
	@echo "    install-build / install-build-gpu       (adds pyinstaller + faster-whisper)"
	@echo "    check-backend / typecheck-frontend / typecheck-electron"
	@echo "    test-backend / test-frontend"
	@echo "    frontend                                 Build frontend/dist"
	@echo "    bundle-cpu / bundle-gpu                  PyInstaller only"
	@echo "    verify-cpu / verify-gpu                  Run scripts/verify-bundle.sh"
	@echo "    electron-package                         electron-builder only"
	@echo "    clean                                    Remove dist/ build/ frontend/dist/"

# ── Install ───────────────────────────────────────────────────────────────────

# Source of truth for ci.yml's backend-checks install step. dev group only,
# no heavy ML packages. ci.yml calls `make install-backend` directly so the
# flag list can't drift. Contributors who want to run the bundle targets
# additionally need `install-build` (or `install-build-gpu`).
install-backend:
	uv sync --locked --group dev --no-group local-transcription \
	    --no-install-package torch \
	    --no-install-package kokoro \
	    --no-install-package spacy \
	    --no-install-package en-core-web-sm

install-frontend:
	cd frontend && bun install --frozen-lockfile

install-electron:
	cd electron && bun install --frozen-lockfile

install-hooks:
	pre-commit install --hook-type pre-commit --hook-type pre-push

install: install-backend install-frontend install-electron install-hooks
	@echo ""
	@echo "Dev env ready. Try 'make ci' to verify."

# Heavier install profiles used by release-cpu / release-gpu.
install-build:
	uv sync --group build --group local-transcription --no-group dev

install-build-gpu:
	uv sync --group build --group local-transcription --group local-transcription-gpu --no-group dev
	uv run --no-sync python -c "import nvidia.cublas, nvidia.cudnn, nvidia.cuda_runtime"

# ── Checks (lint + typecheck) ─────────────────────────────────────────────────

# Backend lint via ruff. Matches .pre-commit-config.yaml's ruff hooks so a
# passing `make check-backend` means the pre-commit stage won't touch anything.
check-backend:
	uv run --no-sync ruff check .
	uv run --no-sync ruff format --check .

# Frontend `bun run build` = `tsc && vite build`, which is the same thing CI
# runs for frontend-checks (typecheck + build in one step).
typecheck-frontend:
	cd frontend && bun run build

# Electron `bun run build` = `tsc` (no bundling; electron-builder does that).
typecheck-electron:
	cd electron && bun run build

check: check-backend typecheck-frontend typecheck-electron
	@echo ""
	@echo "All checks passed."

# ── Format (auto-fix) ─────────────────────────────────────────────────────────

format:
	uv run --no-sync ruff check --fix .
	uv run --no-sync ruff format .

# ── Tests ─────────────────────────────────────────────────────────────────────

# Source of truth for ci.yml's backend-checks pytest invocation. ci.yml
# calls `make test-backend` directly.
test-backend:
	uv run --no-sync pytest tests/ -x --tb=short -m "not requires_models"

# Mirrors ci.yml's frontend-checks `bun run test`.
test-frontend:
	cd frontend && bun run test

test: test-backend test-frontend
	@echo ""
	@echo "All tests passed."

# ── CI equivalent ─────────────────────────────────────────────────────────────

# This is the one target contributors should run before every push.
ci: check test
	@echo ""
	@echo "Local CI equivalent passed. Safe to push."

# ── Release artifacts (tag-push flow) ─────────────────────────────────────────

frontend:
	cd frontend && bun install --frozen-lockfile && bun run build

bundle-cpu: export ARTICULATE_BUILD_GPU := 0
bundle-cpu:
	uv run --no-sync pyinstaller backend.spec --noconfirm --clean

bundle-gpu: export ARTICULATE_BUILD_GPU := 1
bundle-gpu:
	uv run --no-sync pyinstaller backend.spec --noconfirm --clean

verify-cpu: export MATRIX_VARIANT := cpu
verify-cpu:
	uv run --no-sync python scripts/verify-bundle.py

verify-gpu: export MATRIX_VARIANT := gpu
verify-gpu:
	uv run --no-sync python scripts/verify-bundle.py

electron-package:
	uv run --no-sync python scripts/ensure-wincosign-cache.py
	cd electron && bun install --frozen-lockfile && bun run build && bun run package

release-cpu: export ARTICULATE_VARIANT := cpu
release-cpu: install-build frontend bundle-cpu verify-cpu electron-package
	@echo ""
	@echo "CPU release artifacts built and verified."

release-gpu: export ARTICULATE_VARIANT := gpu
release-gpu: install-build-gpu frontend bundle-gpu verify-gpu electron-package
	@echo ""
	@echo "GPU release artifacts built and verified."

# ── Tagging a release ─────────────────────────────────────────────────────────
#
# Usage: make tag VERSION=0.2.0
#
# What it does:
#   1. Validates VERSION is set (Make-level check, no shell required).
#   2. Calls scripts/bump-version.py — validates semver format, new > current,
#      clean working tree, on main branch, tag absent — then bumps all version
#      strings (electron/package.json, pyproject.toml, frontend/package.json,
#      frontend/package-lock.json, backend/main.py).
#   3. Runs `uv lock` to sync uv.lock with the new pyproject.toml version.
#   4. Commits all 6 files and creates the git tag.
#   4. Prints the two push commands — you decide when to run them.
#
# To publish after tagging:
#   git push && git push origin vVERSION

tag:
	$(if $(VERSION),,$(error Usage: make tag VERSION=x.y.z))
	uv run --no-sync python scripts/bump-version.py $(VERSION)
	uv lock
	git add electron/package.json pyproject.toml frontend/package.json frontend/package-lock.json backend/main.py uv.lock
	git commit -m "chore: bump version to $(VERSION)"
	git tag "v$(VERSION)"
	@echo ""
	@echo "Tagged v$(VERSION). To publish:"
	@echo "  git push && git push origin v$(VERSION)"

# ── Housekeeping ──────────────────────────────────────────────────────────────

clean:
	rm -rf dist build frontend/dist electron/dist-installer electron/dist
