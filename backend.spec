# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the Articulate backend.

Build command (run from project root):
    pyinstaller backend.spec --noconfirm --clean

Output: dist/articulate_backend/   (one-dir mode — faster startup than onefile)

Electron-builder bundles this directory into the installer via extraResources.
"""

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

ROOT = Path(SPECPATH)

# ── Collect packages with complex dynamic imports ────────────────────────────

kokoro_datas, kokoro_binaries, kokoro_hiddenimports = collect_all("kokoro")
spacy_datas, spacy_binaries, spacy_hiddenimports = collect_all("spacy")
en_core_datas, en_core_binaries, en_core_hiddenimports = collect_all("en_core_web_sm")
misaki_datas, misaki_binaries, misaki_hiddenimports = collect_all("misaki")
uvicorn_datas, uvicorn_binaries, uvicorn_hiddenimports = collect_all("uvicorn")
# Kokoro -> misaki -> phonemizer -> segments -> csvw. PyInstaller static
# analysis catches the top-level imports but misses submodules and data files
# deeper in the chain (phonemizer backends, segments.tokenizer, csvw metadata
# profiles). Collect each layer explicitly so the runtime import chain works.
phonemizer_datas, phonemizer_binaries, phonemizer_hiddenimports = collect_all("phonemizer")
segments_datas, segments_binaries, segments_hiddenimports = collect_all("segments")
csvw_datas, csvw_binaries, csvw_hiddenimports = collect_all("csvw")
# Local transcription stack — shipped in all three OS installers. macOS gets
# CPU-only ctranslate2 (no GPU backend exists); Linux/Windows additionally
# bundle the nvidia-* CUDA runtime so GPU owners work out-of-box.
fw_datas, fw_binaries, fw_hiddenimports = collect_all("faster_whisper")
ct2_datas, ct2_binaries, ct2_hiddenimports = collect_all("ctranslate2")

# ── Data files ────────────────────────────────────────────────────────────────

datas = [
    # Built React frontend (served by FastAPI as static files)
    (str(ROOT / "frontend" / "dist"), "frontend/dist"),
    # Oxford 5000 vocabulary list
    (str(ROOT / "backend" / "data" / "oxford_5000.csv"), "backend/data"),
    # LLM prompt templates
    (str(ROOT / "backend" / "prompts"), "backend/prompts"),
    # IELTS band descriptors (read at import time by backend/services/scoring.py)
    (str(ROOT / "BAND-SCORES.md"), "."),
    # simplemma language data
    *collect_data_files("simplemma"),
    # spaCy + model
    *spacy_datas,
    *en_core_datas,
    # Kokoro TTS package data (model weights downloaded at first run to HF cache)
    *kokoro_datas,
    # Misaki phoneme data (Kokoro dependency)
    *misaki_datas,
    # phonemizer / segments / csvw — transitive deps through misaki
    *phonemizer_datas,
    *segments_datas,
    *csvw_datas,
    # uvicorn package data
    *uvicorn_datas,
    # faster-whisper + ctranslate2 (Whisper models download lazily to HF cache)
    *fw_datas,
    *ct2_datas,
]

# ── Binaries ──────────────────────────────────────────────────────────────────

binaries = [
    *spacy_binaries,
    *en_core_binaries,
    *kokoro_binaries,
    *misaki_binaries,
    *phonemizer_binaries,
    *segments_binaries,
    *csvw_binaries,
    *uvicorn_binaries,
    *fw_binaries,
    *ct2_binaries,
]

# ── NVIDIA CUDA runtime (GPU variant only; Linux/Windows) ────────────────────
# Gated on ARTICULATE_BUILD_GPU=1 so CPU variants skip the ~1.2 GB of nvidia-*
# wheels entirely. CI sets this env var only on GPU matrix legs.
# macOS is always excluded — ctranslate2 has no CUDA backend on macOS.
# collect_dynamic_libs picks up cublas64_*.dll, cudart64_*.dll, cudnn_*.dll
# from site-packages/nvidia/*/bin (Windows) or .../lib (Linux). These paths
# are added to PATH at runtime by backend/services/transcription.py:_patch_cuda_dll_path.
if os.environ.get("ARTICULATE_BUILD_GPU") == "1" and sys.platform != "darwin":
    for _pkg in ("nvidia.cublas", "nvidia.cudnn", "nvidia.cuda_runtime"):
        try:
            binaries.extend(collect_dynamic_libs(_pkg))
            datas.extend(collect_data_files(_pkg))
        except Exception as _e:
            # GPU leg requested this package via `uv sync --group
            # local-transcription-gpu`; silent skip would produce a partial
            # bundle that can clear the size floor in release.yml. Fail loudly.
            print(f"[backend.spec] GPU collect failed for {_pkg}: {_e}", file=sys.stderr)
            raise

# ── Hidden imports ────────────────────────────────────────────────────────────

hiddenimports = [
    # uvicorn — fully collected to avoid static-analysis misses
    *uvicorn_hiddenimports,
    # Database
    "aiosqlite",
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.ext.asyncio",
    # Pydantic / settings
    "pydantic_settings",
    "pydantic.v1",
    # HTTP / multipart
    "multipart",
    "email.mime.text",
    "email.mime.multipart",
    # All backend submodules (avoids missing-module errors for dynamic imports)
    *collect_submodules("backend"),
    # spaCy / NLP
    *spacy_hiddenimports,
    *en_core_hiddenimports,
    # Kokoro TTS + transitive phonemizer/segments/csvw chain
    *kokoro_hiddenimports,
    *misaki_hiddenimports,
    *phonemizer_hiddenimports,
    *segments_hiddenimports,
    *csvw_hiddenimports,
    # Local transcription
    *fw_hiddenimports,
    *ct2_hiddenimports,
    # Other potentially-dynamic imports
    "simplemma",
    "groq",
    "httpx",
    "aiofiles",
    "language_tool_python",
]

# ── Excludes (not needed in desktop build) ───────────────────────────────────

excludes = [
    # Test / dev tools
    "pytest",
    "pytest_asyncio",
    # IPython / Jupyter (pulled in transitively by some packages)
    "IPython",
    "jupyter",
    "notebook",
    # GUI toolkits not needed
    "tkinter",
    "wx",
    "PyQt5",
    "PyQt6",
    # Chinese normalization path in misaki requires pypinyin which we do not
    # install (English-only IELTS app). Excluding avoids a collect warning
    # and keeps the bundle from trying to resolve the dep.
    "misaki.zh_normalization",
    "pypinyin",
]

# ── Analysis ──────────────────────────────────────────────────────────────────

a = Analysis(
    [str(ROOT / "backend_launcher.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    # Copy metadata for packages that use importlib.metadata at runtime
    copy_metadata=[
        "en_core_web_sm",
        "spacy",
        "spacy_legacy",
        "spacy_loggers",
        "kokoro",
        "pydantic",
        "pydantic_settings",
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "aiosqlite",
    ],
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="articulate_backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # Hide the console window on Windows (Electron manages the UI)
    console=False if sys.platform == "win32" else True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="articulate_backend",
)
