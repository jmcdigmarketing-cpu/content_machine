"""Operator-owned pause flag for the scheduled overnight draft batch."""

from __future__ import annotations

import os
import time

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("core.overnight_pause")

DEFAULT_PAUSE_FILE = os.path.join(DATA_DIR, "overnight.paused")


def pause_file(path: str | None = None) -> str:
    return path or os.getenv("OVERNIGHT_PAUSE_FILE", "").strip() or DEFAULT_PAUSE_FILE


def is_paused(*, path: str | None = None) -> bool:
    """Whether the operator has paused future overnight batches."""
    try:
        return os.path.isfile(pause_file(path))
    except OSError as exc:
        logger.debug("overnight pause flag unreadable: %s", exc)
        return False


def set_paused(paused: bool, *, path: str | None = None) -> bool:
    """Create or remove the pause flag. False means the requested state was not applied."""
    target = pause_file(path)
    try:
        if paused:
            os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(f"paused_at={time.time():.3f}\n")
        else:
            try:
                os.remove(target)
            except FileNotFoundError:
                pass
        return is_paused(path=target) is paused
    except OSError as exc:
        logger.warning("overnight pause state not changed at %s: %s", target, exc)
        return False


def status_line(*, path: str | None = None) -> str:
    return "Overnight: paused" if is_paused(path=path) else "Overnight: ready"
