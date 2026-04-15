"""
PyInstaller entry point for the Articulate backend.

This script is bundled by backend.spec into a standalone executable.
Electron spawns it with ARTICULATE_PORT and ARTICULATE_NO_INTERACTIVE set.
"""
from __future__ import annotations

import multiprocessing
import os
import sys

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
