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


def _today() -> date:
    """Today in YouTube Analytics' day (Pacific)."""
    return datetime.now(_REPORT_TZ).date()


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


def _earliest(*values: Any) -> str | None:
    days = sorted(str(v)[:10] for v in values if _day(v) is not None)
    return days[0] if days else None


def _latest(*values: Any) -> str | None:
    days = sorted(str(v)[:10] for v in values if _day(v) is not None)
    return days[-1] if days else None


def merge_view_curve(
    existing: dict[str, Any], merged: dict[str, Any], published_at: datetime | None
) -> dict[str, Any]:
    """Carry the day series and `first_views` into a freshly merged metrics dict.

    #954: the paid views by day are kept the same way, with what the fetches covered:
    `views_since` / `views_until` and `paid_since` widen, never narrow.
    """
    old = existing if isinstance(existing, dict) else {}
    daily = merge_daily(old.get("daily_views"), merged.get("daily_views"))
    if daily:
        merged["daily_views"] = daily
    if "daily_paid_views" in old or "daily_paid_views" in merged:
        merged["daily_paid_views"] = merge_daily(
            old.get("daily_paid_views"), merged.get("daily_paid_views")
        )
    for key, pick in (("views_since", _earliest), ("paid_since", _earliest)):
        value = pick(old.get(key), merged.get(key))
        if value:
            merged[key] = value
    until = _latest(old.get("views_until"), merged.get("views_until"))
    if until:
        merged["views_until"] = until
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


def first_week_covered(metrics: dict[str, Any], start: date) -> bool:
    """The fetched days include the first 7 from `start`, paid series too (#947 #954).

    Read from what the fetches covered (`views_since` / `views_until`, `paid_since`) - a
    day with no views has no row, so the series alone cannot say. Rows from before those
    markers fall back to the series' own first and last day.
    """
    end = start + timedelta(days=6)
    series = merge_daily([], metrics.get("daily_views"))
    since = _day(metrics.get("views_since")) or (_day(series[0][0]) if series else None)
    until = _day(metrics.get("views_until")) or (_day(series[-1][0]) if series else None)
    paid_since = _day(metrics.get("paid_since"))
    return (
        since is not None
        and since <= start
        and until is not None
        and until >= end
        and paid_since is not None
        and paid_since <= start
    )


def _needs_curve(row: Any) -> bool:
    """#947: stale while the first week (views and paid views) is not fetched.

    It used to read "no `first_views`" - a video that never reached the threshold has none,
    so every `ops all` fetched its whole history again. A video under a week old is left to
    the metrics sync, which reads every young video (#918).
    """
    if not getattr(row, "youtube_video_id", "") or getattr(row, "published_at", None) is None:
        return False
    from storage.repositories.publish_log import is_seeded

    if is_seeded(row):  # #927: a seeded id is not a YouTube video and its day is invented
        return False
    start = publish_day(row.published_at)
    if start is None or start + timedelta(days=7) > _today():
        return False
    try:
        metrics = json.loads(row.metrics_json or "{}")
    except (TypeError, ValueError):
        metrics = {}
    return not isinstance(metrics, dict) or not first_week_covered(metrics, start)


def backfill(channel_id: str, apply: bool, force: bool) -> dict[str, int]:
    """Fetch views by day and paid views by day (#954) from each video's publish day;
    network only with `apply`."""
    from analytics import youtube_metrics
    from storage.repositories.publish_log import get_publish_log_repository

    repo = get_publish_log_repository()
    rows = list(repo.list_timed_outcomes(channel_id) or [])
    todo = [r for r in rows if force or _needs_curve(r)]
    updated = 0
    if apply:
        today = _today()
        for row in todo:
            start = publish_day(row.published_at)
            if start is None or not row.youtube_video_id:
                continue
            end = min(start + timedelta(days=28), today)
            window = {"start": start.isoformat(), "end": end.isoformat()}
            daily = youtube_metrics.fetch_daily_views(
                row.youtube_video_id, channel_id=channel_id, **window
            )
            if daily is None:
                continue
            paid = youtube_metrics.fetch_daily_paid_views(
                row.youtube_video_id, channel_id=channel_id, **window
            )
            try:
                metrics = json.loads(row.metrics_json or "{}")
            except (TypeError, ValueError):
                metrics = {}
            metrics = metrics if isinstance(metrics, dict) else {}
            fresh = dict(
                metrics,
                daily_views=daily,
                views_since=window["start"],
                views_until=window["end"],
            )
            if paid is not None:
                fresh.update(daily_paid_views=paid, paid_since=window["start"])
            merged = merge_view_curve(metrics, fresh, row.published_at)
            repo.update(row.id, {"metrics_json": json.dumps(merged)})
            updated += 1
    return {"runs": len(rows), "stale": len(todo), "would_update": len(todo), "updated": updated}
