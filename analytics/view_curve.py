"""Time to the first 100 views, from YouTube Analytics' views by day (#563).

The 7-day engaged rate takes a week; how fast a video reaches its first views is known in
a day or two. Each metrics sync asks for views by day (`youtube_metrics.fetch_daily_views`)
over the same 28-day window; `merge_daily` keeps the union so days survive the moving
window, and `first_views` is frozen once the threshold is reached.

Days are YouTube Analytics days, which are Pacific time, so the publish day is taken in
Pacific time too. A series that starts after the publish day cannot say when the 100th view
came, so it says nothing rather than a late number.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from core.logging import get_logger

logger = get_logger("analytics.view_curve")

_REPORT_TZ = ZoneInfo("America/Los_Angeles")
_MIN_MEASURED = 5


def threshold() -> int:
    """`FIRST_VIEWS_THRESHOLD` (default 100)."""
    try:
        value = int(os.getenv("FIRST_VIEWS_THRESHOLD", "") or 100)
    except ValueError:
        value = 100
    return max(1, value)


def publish_day(published_at: datetime | None) -> date | None:
    if published_at is None:
        return None
    when = published_at if published_at.tzinfo else published_at.replace(tzinfo=timezone.utc)
    return when.astimezone(_REPORT_TZ).date()


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def merge_daily(existing: Any, new: Any) -> list[list[Any]]:
    """[[YYYY-MM-DD, views], ...] - the union by day, a newer value winning, sorted."""
    by_day: dict[str, int] = {}
    for series in (existing, new):
        for item in series or []:
            try:
                day, views = item[0], int(float(item[1]))
            except (TypeError, ValueError, IndexError):
                continue
            if _day(day) is not None:
                by_day[str(day)[:10]] = views
    return [[day, by_day[day]] for day in sorted(by_day)]


def days_to_views(daily: Any, published_on: date | str | None, limit: int) -> dict | None:
    """`{threshold, days, reached_on}` - days counted from the publish day - or None when
    not reached, or when the series starts after the publish day (it cannot tell)."""
    start = published_on if isinstance(published_on, date) else _day(published_on)
    series = merge_daily([], daily)
    first = _day(series[0][0]) if series else None
    if start is None or first is None or first > start:
        return None
    total = 0
    for day_str, views in series:
        day = _day(day_str)
        if day is None or day < start:
            continue
        total += views
        if total >= limit:
            return {"threshold": limit, "days": (day - start).days, "reached_on": day_str}
    return None


def merge_view_curve(
    existing: dict[str, Any], merged: dict[str, Any], published_at: datetime | None
) -> dict[str, Any]:
    """Carry the day series and `first_views` into a freshly merged metrics dict."""
    old = existing if isinstance(existing, dict) else {}
    daily = merge_daily(old.get("daily_views"), merged.get("daily_views"))
    if daily:
        merged["daily_views"] = daily
    if isinstance(old.get("first_views"), dict):
        merged["first_views"] = old["first_views"]  # frozen once reached
    elif daily:
        reached = days_to_views(daily, publish_day(published_at), threshold())
        if reached:
            merged["first_views"] = reached
    return merged


def _median(values: list[int]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    return float(ordered[mid]) if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def report_line(channel_id: str) -> str:
    """`ops predictions`: time to the first views, and whether it tracks the engaged rate."""
    from core.engagement import engaged_rate
    from core.grade_calibration import _pearson
    from storage.repositories.publish_log import get_publish_log_repository

    label = f"  time to {threshold()} views"
    pairs: list[tuple[int, float]] = []
    pending = 0
    for log in get_publish_log_repository().list_timed_outcomes(channel_id):
        try:
            metrics = json.loads(log.metrics_json or "{}")
        except (TypeError, ValueError):
            continue
        first = metrics.get("first_views") if isinstance(metrics, dict) else None
        rate = engaged_rate(log.metrics_json)
        if isinstance(first, dict) and isinstance(first.get("days"), int):
            if rate is not None:
                pairs.append((first["days"], float(rate)))
        elif rate is not None:
            pending += 1
    tail = f"; {pending} not there yet" if pending else ""
    if len(pairs) < _MIN_MEASURED:
        return f"{label}: collecting (n={len(pairs)}, a rate needs {_MIN_MEASURED}){tail}"
    days = [d for d, _ in pairs]
    r = _pearson([float(d) for d in days], [rate for _, rate in pairs])
    corr = f"r={r:+.2f} with the engaged rate" if r is not None else "no variance"
    median = _median(days)
    shown = f"{median:.0f}" if median == int(median) else f"{median:.1f}"
    return f"{label}: median {shown} day(s) (n={len(pairs)}); {corr}{tail}"


# ---- backfill (#870 registry): past videos, fetched from their publish day ------------


def stale(run: Any) -> bool:
    """A content run whose live video has no day series yet."""
    try:
        from publishing.idempotency import idempotency_key
        from storage.repositories.publish_log import get_publish_log_repository

        row = get_publish_log_repository().find_by_idempotency(
            idempotency_key(int(run.id), str(getattr(run, "channel_id", "") or ""))
        )
    except Exception as exc:
        logger.debug("view-curve stale check skipped: %s", exc)
        return False
    return row is not None and _needs_curve(row)


def _needs_curve(row: Any) -> bool:
    if not getattr(row, "youtube_video_id", "") or getattr(row, "published_at", None) is None:
        return False
    try:
        metrics = json.loads(row.metrics_json or "{}")
    except (TypeError, ValueError):
        metrics = {}
    return not isinstance(metrics, dict) or "first_views" not in metrics


def backfill(channel_id: str, apply: bool, force: bool) -> dict[str, int]:
    """Fetch views by day from each video's publish day; network only with `apply`."""
    from analytics.youtube_metrics import fetch_daily_views
    from storage.repositories.publish_log import get_publish_log_repository

    repo = get_publish_log_repository()
    rows = list(repo.list_timed_outcomes(channel_id) or [])
    todo = [r for r in rows if force or _needs_curve(r)]
    updated = 0
    if apply:
        today = datetime.now(_REPORT_TZ).date()
        for row in todo:
            start = publish_day(row.published_at)
            if start is None or not row.youtube_video_id:
                continue
            end = min(start + timedelta(days=28), today)
            daily = fetch_daily_views(
                row.youtube_video_id,
                channel_id=channel_id,
                start=start.isoformat(),
                end=end.isoformat(),
            )
            if not daily:
                continue
            try:
                metrics = json.loads(row.metrics_json or "{}")
            except (TypeError, ValueError):
                metrics = {}
            metrics = metrics if isinstance(metrics, dict) else {}
            merged = merge_view_curve(metrics, dict(metrics, daily_views=daily), row.published_at)
            repo.update(row.id, {"metrics_json": json.dumps(merged)})
            updated += 1
    return {"runs": len(rows), "stale": len(todo), "would_update": len(todo), "updated": updated}
