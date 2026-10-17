"""
Publishing cadence guardrail.

YouTube's inauthentic-content policy penalises high-volume sameness; the
sustainable, policy-safe band is ~2-5 videos/week WITH variation. This module
counts how many videos hit a channel inside a rolling window (recently
published + already scheduled) so automation can refuse to flood the channel.

Pairs with the Phase O authenticity variation check (variety), this enforces
volume.

Env:
  MAX_VIDEOS_PER_WEEK = a cap; unset (the default since decision 65) means no cap - nothing
  warns, blocks an upload or skips a slot for volume.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from config.channels import resolve_channel_id
from core.logging import get_logger

logger = get_logger("core.cadence")

# Decision 65 (the operator, 2026-10-17: "Remove it"): no cap unless one is set.
_DEFAULT_CAP = 0


@dataclass
class CadenceStatus:
    recent: int  # published within the window
    upcoming: int  # scheduled within the window
    cap: int
    window_days: int

    @property
    def total(self) -> int:
        return self.recent + self.upcoming

    @property
    def capped(self) -> bool:
        return self.cap > 0

    @property
    def ok(self) -> bool:
        return not self.capped or self.total < self.cap


def max_videos_per_week() -> int:
    import os

    raw = os.getenv("MAX_VIDEOS_PER_WEEK", "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return _DEFAULT_CAP


_DEFAULT_TARGET = 3


def weekly_target() -> int:
    """The operator's floor for the week (3-5 set 2026-09-15); never above the cap."""
    import os

    raw = os.getenv("UPLOADS_PER_WEEK_TARGET", "").strip()
    target = int(raw) if raw.isdigit() and int(raw) > 0 else _DEFAULT_TARGET
    cap = max_videos_per_week()
    return min(target, cap) if cap else target


def week_band(status: CadenceStatus) -> str:
    """ "3-5" under a cap, "3+" without one (decision 65)."""
    target = min(weekly_target(), status.cap) if status.capped else weekly_target()
    if not status.capped:
        return f"{target}+"
    return f"{target}-{status.cap}" if status.cap > target else str(target)


def target_line(status: CadenceStatus) -> str:
    """ "Week: 1 of 3-5 ... short 2" when under target, else "" (#764)."""
    target = min(weekly_target(), status.cap) if status.capped else weekly_target()
    if status.total >= target:
        return ""
    band = week_band(status)
    return (
        f"Week: {status.total} of {band} ({status.recent} up, {status.upcoming} scheduled) - "
        f"short {target - status.total}: py -m scripts.ops batch-review"
    )


def _within(when: datetime | None, *, now: datetime, days: int, future: bool) -> bool:
    if not when:
        return False
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    delta = (when - now).total_seconds()
    horizon = days * 86400
    return 0 <= delta <= horizon if future else -horizon <= delta <= 0


def cadence_status(
    channel_id: str,
    *,
    window_days: int = 7,
    cap: int | None = None,
) -> CadenceStatus:
    """Videos published in the last `window_days` + scheduled in the next `window_days`."""
    channel_id = resolve_channel_id(channel_id)
    cap = cap or max_videos_per_week()
    now = datetime.now(timezone.utc)

    recent = upcoming = 0
    try:
        from storage.repositories.publish_log import get_publish_log_repository

        repo = get_publish_log_repository()
        for row in repo.list_uploaded_for_channel(channel_id):
            if _within(row.published_at, now=now, days=window_days, future=False):
                recent += 1
        for row in repo.list_future_scheduled(channel_id):
            if _within(row.published_at, now=now, days=window_days, future=True):
                upcoming += 1
    except Exception as exc:
        logger.debug("cadence: could not read publish log: %s", exc)

    return CadenceStatus(recent=recent, upcoming=upcoming, cap=cap, window_days=window_days)


def display_cadence(status: CadenceStatus, *, print_fn=print) -> None:
    if not status.capped:
        # Decision 65: no cap, so no cadence line - only the weekly floor, when short of it.
        line = target_line(status)
        if line:
            print_fn(f"\n  {line}")
        return
    icon = "✓" if status.ok else "⚠"
    try:
        from core.themes import meter

        gauge = meter(status.total, status.cap)
    except Exception:
        gauge = f"{status.total}/{status.cap}"
    print_fn(
        f"\n  Cadence {icon} {gauge} in a {status.window_days}-day window "
        f"({status.recent} recent + {status.upcoming} scheduled)"
    )
    if not status.ok:
        print_fn(
            "    At/over the safe cadence cap — spacing uploads out protects against "
            "'mass-produced' flags. Raise with MAX_VIDEOS_PER_WEEK if intentional."
        )
    line = target_line(status)
    if line:
        print_fn(f"    {line}")
