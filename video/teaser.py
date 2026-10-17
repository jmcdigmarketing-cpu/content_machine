"""Cut a short vertical teaser from a finished render without changing the source (#511)."""

from __future__ import annotations

import os
import subprocess

from core.logging import get_logger

logger = get_logger("video.teaser")

DEFAULT_SECONDS = 5.0


def create_teaser(
    source: str,
    dest: str,
    *,
    seconds: float = DEFAULT_SECONDS,
) -> str:
    """Write the first ``seconds`` of ``source`` to ``dest``. The source file is not rewritten."""
    src = os.path.abspath(source)
    out = os.path.abspath(dest)
    if not os.path.isfile(src):
        raise FileNotFoundError(src)
    parent = os.path.dirname(out)
    if parent:
        os.makedirs(parent, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-t",
        f"{float(seconds):.3f}",
        "-i",
        src,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-an",
        out,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not os.path.isfile(out):
        err = (proc.stderr or proc.stdout or "")[-400:]
        raise RuntimeError(f"teaser encode failed: {err}")
    logger.info("Teaser written: %s", out)
    return out
