"""
Publishing cadence guardrail.

YouTube's inauthentic-content policy penalises high-volume sameness; the
sustainable, policy-safe band is ~2-5 videos/week WITH variation. This module
counts how many videos hit a channel inside a rolling window (recently
published + already scheduled) so automation can refuse to flood the channel.

Pairs with the Phase O authenticity variation check (variety), this enforces
volume.

Env:
  MAX_VIDEOS_PER_WEEK = 5 (default)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from config.channels import resolve_channel_id
from core.logging import get_logger

logger = get_logger("core.cadence")

_DEFAULT_CAP = 5


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
    def ok(self) -> bool:
        return self.total < self.cap


def max_videos_per_week() -> int:
    import os

    raw = os.getenv("MAX_VIDEOS_PER_WEEK", "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return _DEFAULT_CAP


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
    icon = "✓" if status.ok else "⚠"
    print_fn(
        f"\n  Cadence {icon} {status.total}/{status.cap} in a {status.window_days}-day window "
        f"({status.recent} recent + {status.upcoming} scheduled)"
    )
    if not status.ok:
        print_fn(
            "    At/over the safe cadence cap — spacing uploads out protects against "
            "'mass-produced' flags. Raise with MAX_VIDEOS_PER_WEEK if intentional."
        )
