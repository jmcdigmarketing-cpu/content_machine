"""Skip a scheduled slot when trailing RPM < fully-loaded cost (candidate 63).

Posting to lose money is not "staying consistent." Opt-in (``RPM_COST_GATE``
empty/0/off = disabled) so tests and unmonetized channels are not blocked.
No revenue / no views fail-open. Never writes quota stores.
"""

from __future__ import annotations

import os

from core.logging import get_logger
from core.unit_economics import ChannelEconomics, VideoEconomics, channel_economics

logger = get_logger("core.rpm_cost_gate")


def gate_enabled() -> bool:
    return os.getenv("RPM_COST_GATE", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def trailing_rpm_and_cost(
    videos: list[VideoEconomics],
    *,
    limit: int = 7,
) -> tuple[float | None, float]:
    """RPM ($/1k views) and mean fully-loaded cost over recent monetized uploads.

    Newest-first list; ``limit`` approximates trailing-7d as the last N uploads
    that have both revenue and views (publish timestamps are not on this ledger).
    """
    picked: list[VideoEconomics] = []
    for video in videos:
        if video.revenue_usd is None or video.views <= 0:
            continue
        picked.append(video)
        if len(picked) >= limit:
            break
    if not picked:
        return None, 0.0
    revenue = sum(float(v.revenue_usd or 0.0) for v in picked)
    views = sum(v.views for v in picked)
    cost = sum(v.cost_usd for v in picked) / len(picked)
    if views <= 0:
        return None, cost
    return (revenue / views) * 1000.0, cost


def expected_return(videos: list[VideoEconomics]) -> dict[str, float] | None:
    """What one more video should earn (#579): trailing RPM x median views per video.

    {usd, rpm, median_views}, or None when the channel has no revenue data - an
    unmonetized channel has no return to compare a cost against.
    """
    rpm, _cost = trailing_rpm_and_cost(videos)
    if rpm is None:
        return None
    views = sorted(int(v.views) for v in videos if v.views > 0)
    if not views:
        return None
    mid = len(views) // 2
    median = views[mid] if len(views) % 2 else (views[mid - 1] + views[mid]) / 2
    return {
        "usd": round(rpm * median / 1000.0, 4),
        "rpm": round(rpm, 4),
        "median_views": int(median),
    }


def return_line(projected_total: float, expected: dict | None) -> str:
    """The line under "Projected cost if you proceed", or "" without revenue data."""
    if not isinstance(expected, dict) or expected.get("usd") is None:
        return ""
    usd = float(expected["usd"])
    rpm = float(expected.get("rpm") or 0.0)
    views = int(expected.get("median_views") or 0)
    basis = f"the channel's RPM ${rpm:.2f}/1k x median {views:,} views"
    if projected_total > usd:
        return (
            f"! this video would return ~${usd:.2f} at {basis} - "
            f"less than its ${projected_total:.2f} cost"
        )
    return f"expected return ~${usd:.2f} at {basis}"


def rpm_below_cost_reason(
    *,
    rpm: float | None,
    cost_per_video: float,
) -> str | None:
    if not gate_enabled():
        return None
    if rpm is None:
        return None
    if cost_per_video <= 0:
        return None
    if rpm + 1e-9 >= cost_per_video:
        return None
    return (
        f"rpm-cost gate: trailing RPM ${rpm:.2f}/1k views "
        f"< fully-loaded ${cost_per_video:.2f}/video"
    )


def deferred_plain_reason(
    channel_id: str,
    *,
    econ: ChannelEconomics | None = None,
) -> str:
    """Booth sentence when trailing RPM < cost, or ''."""
    why = rpm_cost_gate_reason(channel_id, econ=econ)
    if not why:
        return ""
    return str(why).replace("rpm-cost gate:", "Deferred:", 1)


def rpm_cost_gate_reason(
    channel_id: str,
    *,
    econ: ChannelEconomics | None = None,
) -> str | None:
    """Why the next scheduled upload should wait, or None when posting is OK."""
    if not gate_enabled():
        return None
    try:
        snapshot = econ if econ is not None else channel_economics(channel_id)
    except Exception as exc:
        logger.debug("rpm-cost economics skipped: %s", exc)
        return None
    rpm, cost = trailing_rpm_and_cost(snapshot.videos)
    return rpm_below_cost_reason(rpm=rpm, cost_per_video=cost)


def next_retry_utc(*, days: int = 7):
    from datetime import datetime, timedelta, timezone

    return datetime.now(timezone.utc) + timedelta(days=days)
