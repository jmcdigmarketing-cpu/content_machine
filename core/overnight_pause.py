"""Operator-owned pause flag for the scheduled overnight draft batch."""

from __future__ import annotations

import os
import time
from datetime import date

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("core.overnight_pause")

DEFAULT_PAUSE_FILE = os.path.join(DATA_DIR, "overnight.paused")


def pause_file(path: str | None = None) -> str:
    return path or os.getenv("OVERNIGHT_PAUSE_FILE", "").strip() or DEFAULT_PAUSE_FILE


def paused_until(*, path: str | None = None) -> date | None:
    """#1338: the last day of a dated pause, or None (no date, or no pause)."""
    try:
        with open(pause_file(path), encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("until="):
                    return date.fromisoformat(line.split("=", 1)[1].strip())
    except (OSError, ValueError):
        return None
    return None


def is_paused(*, path: str | None = None, today: date | None = None) -> bool:
    """Whether the operator has paused future overnight batches. #1338: a pause with a date ends
    the day after it - the flag is removed then."""
    target = pause_file(path)
    try:
        if not os.path.isfile(target):
            return False
    except OSError as exc:
        logger.debug("overnight pause flag unreadable: %s", exc)
        return False
    until = paused_until(path=target)
    if until is not None and (today or date.today()) > until:
        set_paused(False, path=target)
        return False
    return True


def set_paused(paused: bool, *, path: str | None = None, until: date | None = None) -> bool:
    """Create or remove the pause flag - until a date when one is given (#1338). False means the
    requested state was not applied."""
    target = pause_file(path)
    try:
        if paused:
            os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(f"paused_at={time.time():.3f}\n")
                if until is not None:
                    fh.write(f"until={until.isoformat()}\n")
        else:
            try:
                os.remove(target)
            except FileNotFoundError:
                pass
        return os.path.isfile(target) is paused
    except OSError as exc:
        logger.warning("overnight pause state not changed at %s: %s", target, exc)
        return False


def status_line(*, path: str | None = None, today: date | None = None) -> str:
    if not is_paused(path=path, today=today):
        return "Overnight: ready"
    until = paused_until(path=path)
    return f"Overnight: paused until {until:%a %b} {until.day}" if until else "Overnight: paused"
