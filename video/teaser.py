"""Cut a short vertical teaser from a finished render without changing the source (#511)."""

from __future__ import annotations

import os
import subprocess

from core.logging import get_logger

logger = get_logger("video.teaser")

DEFAULT_SECONDS = 5.0


def teaser_argv(src: str, dest: str, *, seconds: float, start: float = 0.0) -> list[str]:
    """#1264: `-nostdin` - a console stdin can stall ffmpeg (#1228) - and `-ss` before `-i`, so
    the teaser starts after the channel intro instead of being its 2.15 s sting."""
    return [
        "ffmpeg",
        "-nostdin",
        "-y",
        "-loglevel",
        "error",
        "-ss",
        f"{max(0.0, float(start)):.3f}",
        "-t",
        f"{float(seconds):.3f}",
        "-i",
        src,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-an",
        dest,
    ]


def create_teaser(
    source: str,
    dest: str,
    *,
    seconds: float = DEFAULT_SECONDS,
    start: float = 0.0,
) -> str:
    """Write ``seconds`` of ``source`` from ``start`` to ``dest``. The source is not rewritten."""
    src = os.path.abspath(source)
    out = os.path.abspath(dest)
    if not os.path.isfile(src):
        raise FileNotFoundError(src)
    parent = os.path.dirname(out)
    if parent:
        os.makedirs(parent, exist_ok=True)
    cmd = teaser_argv(src, out, seconds=seconds, start=start)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"teaser encode timed out after {exc.timeout:.0f}s") from exc
    if proc.returncode != 0 or not os.path.isfile(out):
        err = (proc.stderr or proc.stdout or "")[-400:]
        raise RuntimeError(f"teaser encode failed: {err}")
    logger.info("Teaser written: %s", out)
    return out
