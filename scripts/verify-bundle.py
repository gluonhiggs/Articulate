#!/usr/bin/env python3
"""
Verify a PyInstaller backend bundle.

Checks:
  1. Presence  -- every package the backend imports is in the bundle
  2. Variant   -- CPU: no nvidia-* wheel DLLs; GPU: >=3 CUDA runtime libs
  3. Size      -- bundle is big enough to contain the expected payload
  4. Smoke     -- backend completes lifespan startup (TTS, LanguageTool,
                 Oxford, etc.) within SMOKE_TIMEOUT_S seconds. Pass signal =
                 "Application startup complete." in the log.

Usage:
  MATRIX_VARIANT=cpu  uv run --no-sync python scripts/verify-bundle.py
  MATRIX_VARIANT=gpu  uv run --no-sync python scripts/verify-bundle.py

Called by Makefile's verify-cpu / verify-gpu targets AND (on Linux/macOS)
by .github/workflows/release.yml (which can also keep calling the .sh there).
"""

import fnmatch
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Windows GitHub Actions runners default stdout/stderr to cp1252. When we echo
# smoke.log contents back (which can contain tqdm progress-bar characters like
# U+258F from huggingface_hub model downloads on a fresh runner with no cache),
# `print()` crashes with UnicodeEncodeError before we ever reach the ready/fail
# check. Force UTF-8 with errors="replace" so diagnostic echo is bulletproof.
# Local Windows runs don't hit this because the user's HuggingFace cache
# already has the weights — no download, no progress bar in the log.
for _stream in (sys.stdout, sys.stderr):
    if getattr(_stream, "reconfigure", None):
        _stream.reconfigure(encoding="utf-8", errors="replace")

BUNDLE = Path(os.environ.get("BUNDLE", "dist/articulate_backend/_internal"))
VARIANT = os.environ.get("MATRIX_VARIANT", "cpu")
RUNNER_OS_VAL = os.environ.get("RUNNER_OS", platform.system())


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


# ── 1. Presence check ────────────────────────────────────────────────────────

print(f"=== Presence check (variant={VARIANT}) ===")
PACKAGES = [
    "uvicorn",
    "spacy",
    "kokoro",
    "torch",
    "pydantic_core",
    "faster_whisper",
    "ctranslate2",
    # Transitive chain through kokoro -> misaki. Each layer ships data files
    # PyInstaller doesn't auto-collect; missing any of them produces a
    # FileNotFoundError at lifespan startup (observed on Linux CI 2026-04-20
    # when language_tags/data/json/index.json was missing).
    "misaki",
    "phonemizer",
    "segments",
    "csvw",
    "language_tags",
    "espeakng_loader",
]
for pkg in PACKAGES:
    pkg_dir = BUNDLE / pkg
    if not pkg_dir.is_dir():
        fail(f"{pkg_dir} is missing — bundle is incomplete")
    print(f"OK: {pkg}")


# ── 2. Variant shape check ───────────────────────────────────────────────────

CUDA_PATTERNS = (
    "cublas64*.dll",
    "libcublas*.so*",
    "cudart64*.dll",
    "libcudart*.so*",
    "cudnn*.dll",
    "libcudnn*.so*",
)


def find_files(root: Path, *patterns: str) -> list[Path]:
    result: list[Path] = []
    if not root.exists():
        return result
    for path in root.rglob("*"):
        if path.is_file():
            name = path.name.lower()
            if any(fnmatch.fnmatch(name, p) for p in patterns):
                result.append(path)
    return result


if VARIANT == "gpu":
    print("=== GPU check: CUDA runtime libs ===")
    found = find_files(BUNDLE, *CUDA_PATTERNS)
    if len(found) < 3:
        fail(f"GPU variant bundled only {len(found)} CUDA libs; expected >= 3 (cuBLAS, cuDNN, cudart)")
    print(f"OK: {len(found)} CUDA runtime files present")
else:
    print("=== CPU check: no nvidia-* wheel runtime ===")
    nvidia_dir = BUNDLE / "nvidia"
    nvidia_libs = find_files(nvidia_dir, *CUDA_PATTERNS) if nvidia_dir.is_dir() else []
    if nvidia_libs:
        fail(
            f"CPU variant bundle contains {len(nvidia_libs)} nvidia-* wheel libs under _internal/nvidia/ — should be 0"
        )
    print("OK: CPU variant has no nvidia-* wheel runtime")


# ── 3. Size check ────────────────────────────────────────────────────────────

print("=== Size check ===")
bundle_root = Path("dist/articulate_backend")
total_bytes = sum(f.stat().st_size for f in bundle_root.rglob("*") if f.is_file())
SIZE_MB = total_bytes // (1024 * 1024)
print(f"Bundle size: {SIZE_MB} MB")

if VARIANT == "gpu":
    MIN_MB = 1000
elif RUNNER_OS_VAL in ("macOS", "Darwin"):
    MIN_MB = 400
else:
    MIN_MB = 450

if SIZE_MB < MIN_MB:
    fail(f"bundle is {SIZE_MB} MB, expected >= {MIN_MB} MB for {RUNNER_OS_VAL}/{VARIANT}")


# ── 4. Smoke test ────────────────────────────────────────────────────────────

print("=== Smoke test ===")
exe = Path("dist/articulate_backend/articulate_backend")
if not exe.exists():
    exe = exe.with_suffix(".exe")
if not exe.exists():
    fail(f"Executable not found: {exe}")

try:
    size = exe.stat().st_size
    print(f"{exe}: {size:,} bytes")
except OSError as e:
    fail(str(e))

smoke_log = Path("smoke.log")
if smoke_log.exists():
    smoke_log.unlink()  # fresh log per run so readiness poll can't match stale lines

# Hermetic runtime env. Four reasons:
#   1. A gitignored `./data/mode` on a dev machine (saved from prior runs)
#      would otherwise override TRANSCRIPTION_MODE back to "local" inside the
#      backend's lifespan, routing startup into the ~minute-long Whisper load
#      path and skipping the Kokoro TTS path where bundle bugs usually hide.
#      CI checkouts don't have that file -- this makes the smoke match CI.
#   2. Force TRANSCRIPTION_MODE=groq at the env level (not setdefault) so
#      nothing downstream can re-route into faster-whisper.
#   3. Isolate every external model/jar cache under a fresh tmpdir. A dev box
#      has ~/.cache/huggingface/ (Kokoro weights, ~330MB) and
#      ~/.cache/language_tool_python/ (LT JAR, ~250MB) populated from prior
#      runs, so network-gated first-init code paths (tqdm progress bars,
#      download retry logic, URL changes) never execute. A fresh CI runner
#      has empty caches and does run them -- that's how v0.1.7 Windows hit
#      the U+258F tqdm character in smoke.log while local was green. Point
#      each cache at the tmpdir and every release-cpu run exercises the
#      cold-cache paths CI sees. Cost: ~60-90s per run for the downloads.
#   4. Force PYTHONUTF8=1 so the backend subprocess emits UTF-8 to stdout/
#      stderr regardless of the host's code page. backend_launcher.py already
#      reassigns sys.stdout/stderr to an utf-8 file, but native C stderr paths
#      that slip past that reassignment still land as UTF-8 with this flag.
#      Defense-in-depth on the encoding side of the `feedback_windows_console_
#      encoding.md` class of bug.
smoke_data_dir = Path(tempfile.mkdtemp(prefix="articulate-smoke-data-"))
smoke_cache_dir = Path(tempfile.mkdtemp(prefix="articulate-smoke-cache-"))
env = os.environ.copy()
# pydantic-settings (backend/config.py Settings) has no env_prefix, so the
# env var it actually reads for `data_dir` is DATA_DIR, not ARTICULATE_DATA_DIR.
# Set both: DATA_DIR wins at Settings load; ARTICULATE_DATA_DIR is what
# Electron's spawnBackend sets in production, so we mirror it for parity.
env["DATA_DIR"] = str(smoke_data_dir)
env["ARTICULATE_DATA_DIR"] = str(smoke_data_dir)
env["TRANSCRIPTION_MODE"] = "groq"
env.setdefault("ARTICULATE_NO_INTERACTIVE", "1")
env.setdefault("ARTICULATE_PORT", "8765")
env["ARTICULATE_LOG_PATH"] = str(smoke_log)
# Cache isolation (see reason 3 above). XDG_CACHE_HOME catches LanguageTool's
# JAR cache and anything else that follows the XDG Base Directory spec.
env["HF_HOME"] = str(smoke_cache_dir / "hf")
env["HUGGINGFACE_HUB_CACHE"] = str(smoke_cache_dir / "hf" / "hub")
env["TRANSFORMERS_CACHE"] = str(smoke_cache_dir / "hf" / "transformers")
env["TORCH_HOME"] = str(smoke_cache_dir / "torch")
env["XDG_CACHE_HOME"] = str(smoke_cache_dir / "xdg")
# Force UTF-8 stdio in the backend subprocess (see reason 4 above).
env["PYTHONUTF8"] = "1"

# uvicorn prints "Application startup complete." only after the FastAPI
# lifespan exits successfully -- i.e. Kokoro TTS loaded, LanguageTool inited,
# Oxford 5000 loaded, DB ready. This is the real "bundle works" signal.
# A weaker "still running after N seconds" check would false-green if the
# backend was blocked mid-startup on e.g. a missing data file.
READY_MARKER = "Application startup complete."
# Cold first-run budget: Kokoro weights (~330MB, ~30-60s on fast link) +
# LanguageTool JAR (~250MB, ~20-40s) + backend init. 60s was fine when the
# HF cache was warm but fails on a fresh CI runner; 180s has slack for
# slow-network matrix legs while still failing fast on real hangs.
SMOKE_TIMEOUT_S = int(os.environ.get("SMOKE_TIMEOUT_S", "180"))

print(f"Launching backend; waiting up to {SMOKE_TIMEOUT_S}s for {READY_MARKER!r}...")
print(f"Data dir:  {smoke_data_dir}")
print(f"Cache dir: {smoke_cache_dir}")

try:
    proc = subprocess.Popen([str(exe)], env=env)

    deadline = time.monotonic() + SMOKE_TIMEOUT_S
    ready = False
    exit_code: int | None = None
    while time.monotonic() < deadline:
        exit_code = proc.poll()
        if exit_code is not None:
            break  # backend died before reaching ready marker
        if smoke_log.exists():
            log_text = smoke_log.read_text(encoding="utf-8", errors="replace")
            if READY_MARKER in log_text:
                ready = True
                break
        time.sleep(0.5)

    # Stop the backend (whether ready or timed out).
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    if smoke_log.exists():
        lines = smoke_log.read_text(encoding="utf-8", errors="replace").splitlines()
        print("--- smoke.log head (60 lines) ---")
        print("\n".join(lines[:60]))
        print("--- smoke.log tail (40 lines) ---")
        print("\n".join(lines[-40:]))
        print("--- end log ---")

    if not ready:
        if exit_code is not None:
            fail(f"backend exited with code {exit_code} before reaching {READY_MARKER!r}")
        fail(f"{READY_MARKER!r} not observed within {SMOKE_TIMEOUT_S}s")

    print("Smoke test passed")
finally:
    # Clean up ~400MB of downloaded models + the data sqlite. ignore_errors
    # because on Windows a stuck-terminated backend subprocess may still hold
    # file handles inside the cache dir for a moment; a leaked tmpdir is a
    # smaller problem than a failed smoke test.
    for _dir in (smoke_data_dir, smoke_cache_dir):
        shutil.rmtree(_dir, ignore_errors=True)
