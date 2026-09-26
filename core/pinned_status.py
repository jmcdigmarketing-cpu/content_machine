"""#481 pinned status line: channel, uploads-left, est. cost.

The formatter is always real. CSI pin is TTY-only and off under NO_COLOR —
non-interactive CI never writes escape codes and never warns.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any

from core import process_state

_channel_id: str | None = None
_quota_summary: dict[str, Any] | None = None
_cost: float | None = None
_last_pin: str = ""


def reset_pin() -> None:
    global _channel_id, _quota_summary, _cost, _last_pin, _last_pin_at
    _channel_id = None
    _quota_summary = None
    _cost = None
    _last_pin = ""
    # Clear the throttle clock too, or a reset context would be served a stale
    # line for up to _PIN_MIN_INTERVAL -- and tests would leak state into
    # each other through it.
    _last_pin_at = 0.0


def set_pin_context(
    channel_id: str,
    *,
    quota_summary: dict[str, Any] | None = None,
    cost: float | None = None,
) -> None:
    global _channel_id, _quota_summary, _cost, _last_pin_at
    _channel_id = channel_id
    if quota_summary is not None:
        _quota_summary = quota_summary
    if cost is not None:
        _cost = cost
    _last_pin_at = 0.0  # a changed context must not wait out the throttle


def set_pin_cost(cost: float) -> None:
    global _cost, _last_pin_at
    _cost = cost
    _last_pin_at = 0.0  # cost moved; recompute rather than serve the cached line


def last_pin_text() -> str:
    return _last_pin


def format_pinned_status(
    channel_id: str,
    *,
    quota_summary: dict[str, Any] | None = None,
    cost: float | None = None,
) -> str:
    from apis.youtube_quota import format_uploads_left

    uploads = format_uploads_left(quota_summary).splitlines()[0]
    cost_part = "" if cost is None else f"  est. ${cost:.2f}"
    return f"{channel_id}  {uploads}{cost_part}"


def pin_enabled() -> bool:
    if os.getenv("NO_COLOR", "").strip():
        return False
    raw = os.getenv("CONTENT_UI_PIN")
    if raw is not None and raw.strip().lower() in ("0", "false", "no"):
        return False
    # Run 76: CSI save/restore bled the quota line across every PowerShell row.
    # Default off on Windows; opt in with CONTENT_UI_PIN=1.
    if sys.platform == "win32":
        if raw is None or raw.strip() == "":
            return False
        if raw.strip().lower() not in ("1", "true", "yes"):
            return False
    try:
        return bool(sys.stdout.isatty())
    except Exception:
        return False


def pin_csi(line: str, *, rows: int | None = None) -> str:
    if rows is None:
        try:
            rows = max(2, int(os.get_terminal_size().lines))
        except OSError:
            rows = 24
    # Save cursor, jump to last row, erase, paint, restore. Direct CSI so CI
    # can assert the sequence without a Windows Terminal.
    return f"\033[s\033[{rows};1H\033[2K{line}\033[u"


# Seconds between recomputes. `emit()` refreshes the pin on every printed line,
# and formatting it reaches format_uploads_left -> get_usage_summary -> a
# json.load of data/youtube_quota.json. With 27 `print_fn=emit` defaults, several
# in loops, a chatty phase re-read that file once per line. None of the numbers on
# the pin can change faster than this, so recomputing faster only costs I/O.
_PIN_MIN_INTERVAL = 1.0
_last_pin_at = 0.0


def refresh_pin(*, force: bool = False) -> str:
    """Format the current context. Write CSI only when pin_enabled()."""
    global _last_pin, _last_pin_at
    if not _channel_id:
        return ""
    now = time.monotonic()
    if not force and _last_pin and (now - _last_pin_at) < _PIN_MIN_INTERVAL:
        # Repaint the cached line -- cheap, and keeps the pin pinned while a
        # burst of output scrolls past. Only the recompute is throttled.
        if pin_enabled():
            _write_pin(_last_pin)
        return _last_pin
    try:
        line = format_pinned_status(
            _channel_id,
            quota_summary=_quota_summary,
            cost=_cost,
        )
    except Exception as exc:
        from core.logging import get_logger

        get_logger("core.pinned_status").debug("pinned status skipped: %s", exc)
        return ""
    _last_pin = line
    _last_pin_at = now
    if pin_enabled():
        _write_pin(line)
    return line


def _write_pin(line: str) -> None:
    try:
        sys.stdout.write(pin_csi(line))
        sys.stdout.flush()
    except Exception as exc:
        from core.logging import get_logger

        get_logger("core.pinned_status").debug("pinned status CSI skipped: %s", exc)


process_state.register_reset("core.pinned_status", reset_pin)  # #827
