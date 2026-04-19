"""
PyInstaller entry point for the Articulate backend.

This script is bundled by backend.spec into a standalone executable.
Electron spawns it with ARTICULATE_PORT and ARTICULATE_NO_INTERACTIVE set.
"""

from __future__ import annotations

import os
import sys

# Redirect stdout/stderr to a file when ARTICULATE_LOG_PATH is set.
# Runs before every other import so import-time tracebacks and missing-DLL
# errors are captured. Windows windowed exes (console=False in backend.spec)
# have no usable stdout, so shell redirection `> foo.log` captures nothing —
# this is how CI smoke tests and end-user bug reports get diagnostic output.
_log_path = os.environ.get("ARTICULATE_LOG_PATH")
if _log_path:
    try:
        _log_file = open(_log_path, "a", buffering=1, encoding="utf-8", errors="replace")
        sys.stdout = _log_file
        sys.stderr = _log_file
    except OSError:
        pass

import multiprocessing  # noqa: E402

# Required for PyInstaller one-dir mode when the bundle uses multiprocessing.
multiprocessing.freeze_support()

# ── Read runtime config from environment ─────────────────────────────────────

port = int(os.environ.get("ARTICULATE_PORT", "8000"))
host = os.environ.get("ARTICULATE_HOST", "127.0.0.1")

# ── Patch PYTHONPATH so backend package imports resolve under _MEIPASS ────────

meipass = getattr(sys, "_MEIPASS", None)
if meipass and meipass not in sys.path:
    sys.path.insert(0, meipass)

# ── Launch uvicorn ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        workers=1,
        # Reload is meaningless (and broken) in a frozen executable.
        reload=False,
        log_level="info",
    )
