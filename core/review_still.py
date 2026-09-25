"""#266: save the current review-room frame into an operator stills folder."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from core.logging import get_logger

logger = get_logger("core.review_still")

_STILL_EXT = {".png", ".jpg", ".jpeg", ".webp"}


def review_stills_dir() -> str:
    from core.html_report import html_dir

    path = os.path.join(html_dir(), "stills")
    os.makedirs(path, exist_ok=True)
    return path


def save_review_frame(source: str, dest: str, *, position_ms: int = 0) -> str:
    """Copy a still, or grab one ffmpeg frame from an mp4. Not a thumbnail API."""
    src = Path(source)
    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if not src.is_file():
        raise FileNotFoundError(source)
    if src.suffix.lower() in _STILL_EXT:
        shutil.copyfile(src, dest_path)
        return str(dest_path)
    ss = max(0, int(position_ms)) / 1000.0
    proc = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{ss:.3f}",
            "-i",
            str(src),
            "-frames:v",
            "1",
            str(dest_path),
        ],
        capture_output=True,
        check=False,
        timeout=20,
    )
    if dest_path.is_file() and dest_path.stat().st_size > 0:
        return str(dest_path)
    logger.debug("review frame grab failed: %s", proc.stderr[-200:] if proc.stderr else "")
    raise OSError(f"could not grab frame from {source}")
