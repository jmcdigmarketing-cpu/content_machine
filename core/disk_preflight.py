"""Disk-space preflight before ffmpeg (candidate 91).

Fail with GB free, not a half-written mp4. Opt-in: DISK_MIN_FREE_GB empty/0/off
= disabled so the unit suite cannot abort on a full CI volume.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from core.logging import get_logger

logger = get_logger("core.disk_preflight")


def min_free_gb() -> float | None:
    raw = os.getenv("DISK_MIN_FREE_GB", "").strip().lower()
    if raw in ("", "0", "off", "false", "no"):
        return None
    try:
        val = float(raw)
    except ValueError:
        return None
    return val if val > 0 else None


def free_gb(path: str | os.PathLike[str]) -> float | None:
    try:
        usage = shutil.disk_usage(path)
    except OSError as exc:
        logger.debug("disk_usage skipped: %s", exc)
        return None
    return usage.free / (1024**3)


def block_reason(path: str | os.PathLike[str], *, min_gb: float | None = None) -> str | None:
    """Why ffmpeg must not start, or None. Missing verifier fail-opens."""
    need = min_free_gb() if min_gb is None else min_gb
    if need is None:
        return None
    target = Path(path)
    probe = str(target if target.exists() else (target.parent if target.parent.exists() else "."))
    free = free_gb(probe)
    if free is None:
        return None
    if free < need:
        return (
            f"disk preflight: {free:.2f} GB free at {probe}, need >= {need:.2f} GB "
            "(refusing ffmpeg so the mp4 is not half-written)"
        )
    return None
