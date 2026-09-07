"""#481 pinned status line: channel, uploads-left, est. cost.

The formatter is always real. CSI pin is TTY-only and off under NO_COLOR —
non-interactive CI never writes escape codes and never warns.
"""

from __future__ import annotations

import os
import sys
from typing import Any

_channel_id: str | None = None
_quota_summary: dict[str, Any] | None = None
_cost: float | None = None
_last_pin: str = ""


def reset_pin() -> None:
    global _channel_id, _quota_summary, _cost, _last_pin
    _channel_id = None
    _quota_summary = None
    _cost = None
    _last_pin = ""


def set_pin_context(
    channel_id: str,
    *,
    quota_summary: dict[str, Any] | None = None,
    cost: float | None = None,
) -> None:
    global _channel_id, _quota_summary, _cost
    _channel_id = channel_id
    if quota_summary is not None:
        _quota_summary = quota_summary
    if cost is not None:
        _cost = cost


def set_pin_cost(cost: float) -> None:
    global _cost
    _cost = cost


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
    if os.getenv("CONTENT_UI_PIN", "1").strip().lower() in ("0", "false", "no"):
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


def refresh_pin() -> str:
    """Format the current context. Write CSI only when pin_enabled()."""
    global _last_pin
    if not _channel_id:
        return ""
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
    if pin_enabled():
        try:
            sys.stdout.write(pin_csi(line))
            sys.stdout.flush()
        except Exception as exc:
            from core.logging import get_logger

            get_logger("core.pinned_status").debug("pinned status CSI skipped: %s", exc)
    return line
