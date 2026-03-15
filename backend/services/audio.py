from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import aiofiles
from fastapi import UploadFile

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024  # 1 MB read chunks


async def save_audio(
    upload_file: UploadFile,
    attempt_id: int,
    audio_dir: str,
) -> str:
    """
    Save an uploaded audio file to disk.

    The file is stored as {audio_dir}/{attempt_id}.webm.

    Returns:
        The absolute file path as a string.
    """
    audio_path = Path(audio_dir)
    audio_path.mkdir(parents=True, exist_ok=True)

    dest = audio_path / f"{attempt_id}.webm"

    async with aiofiles.open(dest, "wb") as f:
        while True:
            chunk = await upload_file.read(CHUNK_SIZE)
            if not chunk:
                break
            await f.write(chunk)

    logger.info("Saved audio for attempt %d to %s", attempt_id, dest)
    return str(dest)


async def cleanup_old_audio(
    audio_dir: str,
    retention_days: int,
    max_size_mb: int,
) -> None:
    """
    Clean up old audio files.

    Phase 1: Delete files older than `retention_days` days.
    Phase 2: If total size still exceeds `max_size_mb`, delete the oldest files
             until the total size is within limits.
    """
    audio_path = Path(audio_dir)
    if not audio_path.exists():
        return

    cutoff = datetime.now() - timedelta(days=retention_days)

    # Collect all .webm files with their metadata
    files = []
    for f in audio_path.glob("*.webm"):
        try:
            stat = f.stat()
            files.append((f, stat.st_mtime, stat.st_size))
        except OSError:
            continue

    # Phase 1: Remove files older than retention period
    remaining = []
    for f, mtime, size in files:
        if datetime.fromtimestamp(mtime) < cutoff:
            try:
                f.unlink()
                logger.info("Deleted old audio file: %s", f)
            except OSError as exc:
                logger.warning("Could not delete %s: %s", f, exc)
        else:
            remaining.append((f, mtime, size))

    # Phase 2: Enforce total size limit
    total_bytes = sum(size for _, _, size in remaining)
    max_bytes = max_size_mb * 1024 * 1024

    if total_bytes > max_bytes:
        # Sort oldest first
        remaining.sort(key=lambda x: x[1])
        for f, mtime, size in remaining:
            if total_bytes <= max_bytes:
                break
            try:
                f.unlink()
                total_bytes -= size
                logger.info("Deleted audio file to free space: %s", f)
            except OSError as exc:
                logger.warning("Could not delete %s: %s", f, exc)
