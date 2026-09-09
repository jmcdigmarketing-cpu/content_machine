"""#605: refuse upload when the operator has not been seen for N days."""

from __future__ import annotations

import os
import time

from core.logging import get_logger

logger = get_logger("core.publish_deadman")


def deadman_days() -> float | None:
    raw = os.getenv("PUBLISH_DEADMAN_DAYS", "").strip().lower()
    if raw in ("", "0", "off", "false", "no"):
        return None
    try:
        val = float(raw)
    except ValueError:
        return None
    return val if val > 0 else None


def deadman_block_reason(
    *,
    last_human_at: float | None = None,
    now: float | None = None,
) -> str | None:
    """None when the gate is off or the heartbeat is fresh. A sentence when armed."""
    days = deadman_days()
    if days is None:
        return None
    stamp = last_human_at
    if stamp is None:
        try:
            from core.human_presence import last_human_at as read_stamp

            stamp = read_stamp()
        except Exception as exc:
            logger.debug("deadman heartbeat read skipped: %s", exc)
            stamp = None
    if stamp is None:
        return (
            f"publish dead-man's switch: no operator heartbeat " f"(PUBLISH_DEADMAN_DAYS={days:g})"
        )
    current = float(now if now is not None else time.time())
    age_days = max(0.0, (current - float(stamp)) / 86400.0)
    if age_days > days:
        return f"publish dead-man's switch: last seen {age_days:.0f}d ago " f"(limit {days:g}d)"
    return None
