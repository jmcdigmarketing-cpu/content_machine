"""Retry when Windows Defender (or another process) locks an mp4 mid-write.

Same class as the vanished-intro bug: os.replace / ffmpeg can hit WinError 32
("being used by another process") for a second. Opt-in delay via
FFMPEG_LOCK_RETRIES (default 5). Never raises from is_lock_error.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import TypeVar

from core.logging import get_logger

logger = get_logger("core.file_lock")

T = TypeVar("T")

_WIN_LOCK = {5, 32, 33}  # ACCESS_DENIED, SHARING_VIOLATION, LOCK_VIOLATION


def lock_retries() -> int:
    raw = os.getenv("FFMPEG_LOCK_RETRIES", "5").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 5


def lock_delay_sec() -> float:
    raw = os.getenv("FFMPEG_LOCK_DELAY_SEC", "0.4").strip()
    try:
        val = float(raw)
        return val if val > 0 else 0.4
    except ValueError:
        return 0.4


def is_lock_error(exc: BaseException | None, stderr: str = "") -> bool:
    blob = (stderr or "").lower()
    if "being used by another process" in blob or "access is denied" in blob:
        return True
    if "permission denied" in blob and ("mp4" in blob or "output" in blob):
        return True
    if exc is None:
        return False
    if isinstance(exc, PermissionError):
        return True
    if isinstance(exc, OSError):
        win = getattr(exc, "winerror", None)
        if win in _WIN_LOCK:
            return True
        if getattr(exc, "errno", None) in (13, 11):
            return True
        msg = str(exc).lower()
        if "being used by another process" in msg or "access is denied" in msg:
            return True
    return False


def retry_locked(
    fn: Callable[[], T], *, attempts: int | None = None, delay: float | None = None
) -> T:
    """Call fn, retrying lock errors. Last exception propagates."""
    n = attempts if attempts is not None else lock_retries()
    wait = delay if delay is not None else lock_delay_sec()
    last: BaseException | None = None
    for i in range(max(1, n)):
        try:
            return fn()
        except Exception as exc:
            last = exc
            if not is_lock_error(exc) or i >= n - 1:
                raise
            logger.warning("File lock (attempt %s/%s): %s", i + 1, n, exc)
            time.sleep(wait * (i + 1))
    assert last is not None
    raise last
