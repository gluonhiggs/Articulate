#!/usr/bin/env python3
"""
Verify a PyInstaller backend bundle.

Checks:
  1. Presence  -- every package the backend imports is in the bundle
  2. Variant   -- CPU: no nvidia-* wheel DLLs; GPU: >=3 CUDA runtime libs
  3. Size      -- bundle is big enough to contain the expected payload
  4. Smoke     -- backend starts and stays running for 10 s

Usage:
  MATRIX_VARIANT=cpu  uv run --no-sync python scripts/verify-bundle.py
  MATRIX_VARIANT=gpu  uv run --no-sync python scripts/verify-bundle.py

Called by Makefile's verify-cpu / verify-gpu targets AND (on Linux/macOS)
by .github/workflows/release.yml (which can also keep calling the .sh there).
"""

import fnmatch
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

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
env = os.environ.copy()
env.setdefault("ARTICULATE_NO_INTERACTIVE", "1")
env.setdefault("ARTICULATE_PORT", "8765")
# Pin smoke test to groq so the 10s window doesn't trigger a ~486 MB
# Whisper model download. CI verifies "bundle starts"; local mode is out of scope.
env.setdefault("TRANSCRIPTION_MODE", "groq")
env["ARTICULATE_LOG_PATH"] = str(smoke_log)

proc = subprocess.Popen([str(exe)], env=env)
time.sleep(10)

still_running = proc.poll() is None
if still_running:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    exit_code = 124  # sentinel: still running after 10s = pass
else:
    exit_code = proc.returncode

if smoke_log.exists():
    lines = smoke_log.read_text(encoding="utf-8", errors="replace").splitlines()
    print("--- smoke.log head (60 lines) ---")
    print("\n".join(lines[:60]))
    print("--- smoke.log tail (40 lines) ---")
    print("\n".join(lines[-40:]))
    print("--- end log ---")

if exit_code != 124:
    fail(f"backend exited with code {exit_code} (expected it to still be running after 10s)")

print("Smoke test passed")
