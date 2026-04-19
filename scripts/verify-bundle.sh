#!/usr/bin/env bash
#
# Verify a PyInstaller backend bundle.
#
# Runs three checks:
#   1. Presence — every package the backend imports is in the bundle
#   2. Variant shape — CPU: no nvidia-* wheel DLLs; GPU: >=3 CUDA runtime libs
#   3. Size floor — bundle is big enough to contain the expected payload
#   4. Smoke — backend starts and stays running for 10s
#
# Usage:
#   MATRIX_VARIANT=cpu bash scripts/verify-bundle.sh
#   MATRIX_VARIANT=gpu bash scripts/verify-bundle.sh
#
# Called by .github/workflows/release.yml AND scripts/ci-local.sh. Keeping one
# script means CI and local runs exercise the same code path.
#
set -uo pipefail

BUNDLE="${BUNDLE:-dist/articulate_backend/_internal}"
VARIANT="${MATRIX_VARIANT:-cpu}"
RUNNER_OS_VAL="${RUNNER_OS:-$(uname -s)}"

echo "=== Presence check (variant=${VARIANT}) ==="
PACKAGES="uvicorn spacy kokoro torch pydantic_core faster_whisper ctranslate2"
for pkg in $PACKAGES; do
  if [ ! -d "$BUNDLE/$pkg" ]; then
    echo "FAIL: $BUNDLE/$pkg is missing — bundle is incomplete"
    exit 1
  fi
  echo "OK: $pkg"
done

if [ "${VARIANT}" = "gpu" ]; then
  # PyInstaller can flatten nvidia.* (PEP 420 namespace package) into
  # _internal/ root OR keep _internal/nvidia/*/bin/ hierarchy. Don't
  # rely on directory existence — grep for the actual DLL/SO filenames.
  echo "=== GPU check: CUDA runtime libs ==="
  FOUND=$(find "$BUNDLE" \
    -iname "cublas64*.dll" -o -iname "libcublas*.so*" \
    -o -iname "cudart64*.dll" -o -iname "libcudart*.so*" \
    -o -iname "cudnn*.dll" -o -iname "libcudnn*.so*" \
    2>/dev/null | wc -l)
  if [ "$FOUND" -lt 3 ]; then
    echo "FAIL: GPU variant bundled only ${FOUND} CUDA libs; expected >= 3 (cuBLAS, cuDNN, cudart)"
    find "$BUNDLE" -iname "*cuda*" -o -iname "*cublas*" -o -iname "*cudnn*" 2>/dev/null | head -20 || true
    exit 1
  fi
  echo "OK: ${FOUND} CUDA runtime files present"
else
  # CPU variant must NOT ship nvidia-* wheel DLLs. Scope the search to
  # _internal/nvidia/ (the path nvidia-cublas-cu12 / nvidia-cudnn-cu12 /
  # nvidia-cuda-runtime-cu12 install into). Other packages can ship
  # their own CUDA-named stubs (ctranslate2>=4.5 ships a 266KB
  # cudnn64_9.dll loader inside ctranslate2/); those are package-owned
  # and not what this check is trying to forbid.
  echo "=== CPU check: no nvidia-* wheel runtime ==="
  if [ -d "$BUNDLE/nvidia" ]; then
    NVIDIA_LIBS=$(find "$BUNDLE/nvidia" \
      -iname "cublas64*.dll" -o -iname "libcublas*.so*" \
      -o -iname "cudnn*.dll" -o -iname "libcudnn*.so*" \
      -o -iname "cudart64*.dll" -o -iname "libcudart*.so*" \
      2>/dev/null | wc -l)
  else
    NVIDIA_LIBS=0
  fi
  if [ "$NVIDIA_LIBS" -gt 0 ]; then
    echo "FAIL: CPU variant bundle contains ${NVIDIA_LIBS} nvidia-* wheel libs under _internal/nvidia/ — should be 0"
    find "$BUNDLE/nvidia" -iname "*.dll" -o -iname "*.so*" 2>/dev/null | head -20 || true
    exit 1
  fi
  echo "OK: CPU variant has no nvidia-* wheel runtime"
fi

echo "=== Size check ==="
SIZE_MB=$(du -sm dist/articulate_backend | cut -f1)
echo "Bundle size: ${SIZE_MB} MB"
# Size floors per variant/OS:
#   macOS (cpu only): ~510 MB → floor 400
#   Win/Linux CPU:    ~510 MB → floor 450
#   Win/Linux GPU:    ~1.7 GB → floor 1000
if [ "${VARIANT}" = "gpu" ]; then
  MIN_MB=1000
elif [ "${RUNNER_OS_VAL}" = "macOS" ] || [ "${RUNNER_OS_VAL}" = "Darwin" ]; then
  MIN_MB=400
else
  MIN_MB=450
fi
if [ "$SIZE_MB" -lt "$MIN_MB" ]; then
  echo "FAIL: bundle is ${SIZE_MB} MB, expected >= ${MIN_MB} MB for ${RUNNER_OS_VAL}/${VARIANT}"
  exit 1
fi

echo "=== Smoke test ==="
EXE="dist/articulate_backend/articulate_backend"
[ -f "${EXE}.exe" ] && EXE="${EXE}.exe"
ls -la "$EXE" || true
# Windows windowed exes (console=False) have no usable stdout, so shell
# redirection captures nothing. backend_launcher.py honours ARTICULATE_LOG_PATH
# and writes sys.stdout/stderr to the file itself — works on all three OSes.
export ARTICULATE_NO_INTERACTIVE="${ARTICULATE_NO_INTERACTIVE:-1}"
export ARTICULATE_PORT="${ARTICULATE_PORT:-8765}"
# Pin smoke test to groq so the 10s window doesn't trigger a ~486 MB
# Whisper model download. CI verifies "bundle starts"; exercising local
# mode end-to-end is out of scope for smoke.
export TRANSCRIPTION_MODE="${TRANSCRIPTION_MODE:-groq}"
ARTICULATE_LOG_PATH=smoke.log "$EXE" &
PID=$!
sleep 10
EXIT=0
if kill -0 "$PID" 2>/dev/null; then
  kill "$PID" 2>/dev/null || true
  wait "$PID" 2>/dev/null || true
  EXIT=124
else
  # Process exited before 10s; capture its code without tripping `set -e`.
  wait "$PID" || EXIT=$?
fi
# Print head + tail so import tracebacks with the real error
# message at the bottom aren't truncated away by the cap.
echo "--- smoke.log head (60 lines) ---"
head -60 smoke.log || true
echo "--- smoke.log tail (40 lines) ---"
tail -40 smoke.log || true
echo "--- end log ---"
if [ "$EXIT" -ne 124 ]; then
  echo "FAIL: backend exited with code $EXIT (expected it to still be running after 10s)"
  exit 1
fi
echo "Smoke test passed"
