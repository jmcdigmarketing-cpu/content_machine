"""#378: when each provider's free window resets or ends.

A $0 run becomes a paid one the moment a free window closes, and nothing tracked
when that happens. Same class as #580, where a persisted $0 last-run was silently
re-estimated at $0.1725.

Three states, kept distinct on purpose. A window with a date is **due** or not; a
window whose date has passed is **closed** and stays on the calendar rather than
dropping off it; a window with no date at all is **unknown**, which is not the
same as safe. Hand-maintained dates in `config/free_tiers.json` -- this is a
reminder, not a live reading, and it says so.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from config.paths import ROOT_DIR
from core.logging import get_logger

logger = get_logger("core.free_tier_calendar")

CONFIG_PATH = Path(ROOT_DIR) / "config" / "free_tiers.json"
_DEFAULT_NOTICE_DAYS = 7


def _config() -> dict[str, Any]:
    try:
        with CONFIG_PATH.open(encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("free-tier calendar unreadable, no expiry notice: %s", exc)
        return {}


def load_windows() -> list[dict[str, Any]]:
    rows = _config().get("windows") or []
    return [row for row in rows if isinstance(row, dict) and row.get("provider")]


def notice_days() -> int:
    try:
        return max(1, int(_config().get("notice_days") or _DEFAULT_NOTICE_DAYS))
    except (TypeError, ValueError):
        return _DEFAULT_NOTICE_DAYS


def _parse(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def expiring_windows(
    *,
    today: str | date | None = None,
    windows: list[dict[str, Any]] | None = None,
    notice_days: int | None = None,
) -> list[dict[str, Any]]:
    """Rows needing attention: due inside the notice period, already closed, or
    carrying no date at all."""
    rows = windows if windows is not None else load_windows()
    limit = notice_days if notice_days is not None else globals()["notice_days"]()
    now = _parse(today) or (today if isinstance(today, date) else None) or date.today()

    out: list[dict[str, Any]] = []
    for row in rows:
        boundary = _parse(row.get("resets")) or _parse(row.get("ends"))
        recurring = bool(row.get("resets"))
        if boundary is None:
            out.append({**row, "days": None, "closed": False, "unknown": True})
            continue
        days = (boundary - now).days
        if days < 0:
            out.append({**row, "days": days, "closed": True, "unknown": False})
        elif days <= limit:
            out.append(
                {**row, "days": days, "closed": False, "unknown": False, "recurring": recurring}
            )
    return out


def render_calendar(rows: list[dict[str, Any]] | None = None) -> str:
    rows = rows if rows is not None else expiring_windows()
    lines = ["Free-tier calendar", "=" * 60]
    if not rows:
        lines.append("  nothing due, closed or undated inside the notice period")
        return "\n".join(lines)
    for row in rows:
        provider = str(row.get("provider"))
        kind = str(row.get("kind") or "?")
        if row.get("unknown"):
            state = "UNKNOWN  no published date - verify before a paid run"
        elif row.get("closed"):
            state = f"CLOSED   {abs(int(row['days']))}d ago"
        else:
            verb = "resets" if row.get("recurring") else "ENDS"
            state = f"{verb:8} in {int(row['days'])}d"
        lines.append(f"  {provider:<20} {kind:<16} {state}")
        note = str(row.get("note") or "").strip()
        if note:
            lines.append(f"  {'':<20} {note}")
    lines.append("")
    lines.append("Hand-maintained dates. A reminder, not a live reading of any provider.")
    return "\n".join(lines)
