"""Known quota reset cadences → auto-re-enable disabled providers (O10).

Providers recover on a fixed schedule that we can encode instead of guessing
with a flat TTL:

- **YouTube Data API** — daily at midnight Pacific Time.
- **Apify** — monthly usage cycle (billing day via ``APIFY_RESET_DAY``, default 1).
- **Odds API** — monthly on the 1st (UTC).

`apis/apify_client.py` uses `seconds_until_reset("apify")` so a hard 402 /
monthly-limit / operator-budget trip stays persisted *until the cycle actually
resets* (instead of re-checking every 6h for weeks), and `apis/youtube_quota.py`
uses `next_reset("youtube")` so a blocked upload retries right after the real
daily reset instead of a heuristic +1 day.

Master switch: ``RESET_WINDOW_AUTO_ENABLE`` (default on). When off, callers
fall back to their previous flat TTL behaviour.
"""

from __future__ import annotations

import calendar
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

_YOUTUBE_TZ = "America/Los_Angeles"  # documented Data API reset: midnight PT


def reset_window_enabled() -> bool:
    return os.getenv("RESET_WINDOW_AUTO_ENABLE", "true").lower() in ("1", "true", "yes")


def _apify_reset_day() -> int:
    """Day-of-month the Apify usage cycle resets (operator's billing day)."""
    raw = os.getenv("APIFY_RESET_DAY", "1").strip()
    try:
        return max(1, min(31, int(raw)))
    except ValueError:
        return 1


def _next_monthly(now: datetime, day: int) -> datetime:
    """First occurrence of `day` (UTC midnight) strictly after `now`; clamps to month length."""
    year, month = now.year, now.month
    for _ in range(3):
        days_in_month = calendar.monthrange(year, month)[1]
        candidate = datetime(year, month, min(day, days_in_month), tzinfo=timezone.utc)
        if candidate > now:
            return candidate
        month += 1
        if month > 12:
            month, year = 1, year + 1
    return now + timedelta(days=31)  # unreachable; defensive


def next_reset(provider: str, *, now: datetime | None = None) -> datetime | None:
    """Next quota reset time (UTC, tz-aware) for a known provider, else None."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    key = (provider or "").strip().lower()

    if key == "youtube":
        local = now.astimezone(ZoneInfo(_YOUTUBE_TZ))
        nxt = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return nxt.astimezone(timezone.utc)
    if key == "apify":
        return _next_monthly(now, _apify_reset_day())
    if key == "odds":
        return _next_monthly(now, 1)
    return None


def seconds_until_reset(provider: str, *, now: datetime | None = None) -> int | None:
    """Seconds until the provider's next reset (min 60), or None for unknown providers."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    nxt = next_reset(provider, now=now)
    if nxt is None:
        return None
    return max(60, int((nxt - now).total_seconds()))
