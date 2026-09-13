"""#378: when each provider's free window resets or ends.

A $0 run becomes a paid one the moment a free window closes, and nothing tracked
when that happens. Same class as #580, where a persisted $0 last-run was silently
re-estimated at $0.1725.

Three states, kept distinct on purpose. A window with a date is **due** or not; a
window whose date has passed is **closed** and stays on the calendar rather than
dropping off it; a window with no date at all is **unknown**, which is not the
same as safe.

#722: a recurring window whose cadence `core/reset_window` already encodes carries
`"derive": "<provider>"` instead of a typed `resets`. The typed YouTube row said
`2026-09-11`; on 2026-09-12 the calendar reported a *daily* quota as a CLOSED free
window. Typed dates stay only for providers nothing in the repo can read.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

from config.paths import ROOT_DIR
from core.logging import get_logger

logger = get_logger("core.free_tier_calendar")

CONFIG_PATH = Path(ROOT_DIR) / "config" / "free_tiers.json"
_DEFAULT_NOTICE_DAYS = 7
_APIFY_PURPOSES = ("main", "tiktok_trends", "youtube_competitors")


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


def _derived_boundary(provider: str, today: date) -> date | None:
    """Next reset date from the encoded cadence; None when it cannot be derived."""
    try:
        from core.reset_window import next_reset, reset_window_enabled

        if not reset_window_enabled():
            return None
        # Midday UTC so the date is stable whatever the machine's local clock says.
        nxt = next_reset(provider, now=datetime.combine(today, time(12, 0), tzinfo=timezone.utc))
        return nxt.astimezone(timezone.utc).date() if nxt else None
    except Exception as exc:
        logger.debug("free-tier boundary for %s not derivable: %s", provider, exc)
        return None


def _apify_reading() -> str:
    """The last recorded `/users/me` reading, if any. No HTTP."""
    try:
        from core.quota_governor import apify_get_usage

        for purpose in _APIFY_PURPOSES:
            usage = apify_get_usage(purpose)
            if isinstance(usage, dict) and usage.get("limit"):
                return f"last reading ${float(usage.get('usage') or 0):.2f}/${float(usage['limit']):.2f}"
    except Exception as exc:
        logger.debug("apify reading unavailable for the calendar: %s", exc)
    return ""


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
        derive = str(row.get("derive") or "").strip()
        if derive:
            boundary = _derived_boundary(derive, now)
            recurring = True
            if derive == "apify":
                reading = _apify_reading()
                if reading:
                    note = str(row.get("note") or "").strip()
                    row = {**row, "note": f"{note}; {reading}" if note else reading}
        else:
            boundary = _parse(row.get("resets")) or _parse(row.get("ends"))
            recurring = bool(row.get("resets"))
        base = {**row, "derived": bool(derive)}
        if boundary is None:
            out.append({**base, "days": None, "closed": False, "unknown": True})
            continue
        days = (boundary - now).days
        if days < 0:
            out.append({**base, "days": days, "closed": True, "unknown": False})
        elif days <= limit:
            out.append(
                {**base, "days": days, "closed": False, "unknown": False, "recurring": recurring}
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
        source = "derived" if row.get("derived") else "typed"
        if row.get("unknown"):
            state = (
                "UNKNOWN  cadence not derivable - verify before a paid run"
                if row.get("derived")
                else "UNKNOWN  no published date - verify before a paid run"
            )
        elif row.get("closed"):
            state = f"CLOSED   {abs(int(row['days']))}d ago ({source})"
        else:
            verb = "resets" if row.get("recurring") else "ENDS"
            state = f"{verb:8} in {int(row['days'])}d ({source})"
        lines.append(f"  {provider:<20} {kind:<16} {state}")
        note = str(row.get("note") or "").strip()
        if note:
            lines.append(f"  {'':<20} {note}")
    lines.append("")
    lines.append(
        "derived = core/reset_window cadence (midnight Pacific, APIFY_RESET_DAY); "
        "typed = hand-maintained in config/free_tiers.json."
    )
    return "\n".join(lines)
