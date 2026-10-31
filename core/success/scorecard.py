"""The bridge's scorecard (wave 134's items 6-10, built in wave 135).

- #1797 cost per 1,000 organic views: a run's stored cost over its first 7 days' organic views.
- #1728 the hours ledger: the long videos' organic watch hours a week, and the weeks to the bar.
- #1836 the wave scorecard: each shipped wave's metric 14 days after against 14 days before
  (`config/waves.json`, a row added when a wave ships).
- #1832 a breakout: a Short past 1,000 organic views within 24 hours raises one toast.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("core.success.scorecard")

_WAVES_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config",
    "waves.json",
)
SCORE_DAYS = 14
BREAKOUT_VIEWS, BREAKOUT_HOURS = 1000, 24


def cost_per_thousand(cost: float | None, views: int | None) -> str:
    """#1797: "$1.20" per 1,000 organic views, "no views", or "" when either is unknown."""
    if cost is None or views is None:
        return ""
    if views <= 0:
        return "no views"
    return f"${float(cost) * 1000 / views:,.2f}"


def week_cost_line(rows: list[dict[str, Any]]) -> str:
    """#1797: the week's run spend over the week's organic views at 7 days."""
    priced = [r for r in rows if r.get("cost") is not None and r.get("views") is not None]
    if not priced:
        return "cost per 1,000 organic views: not measured (no video with 7 days of views yet)"
    cost = sum(float(r["cost"]) for r in priced)
    views = sum(int(r["views"]) for r in priced)
    per = cost_per_thousand(cost, views)
    return (
        f"cost per 1,000 organic views (7 days): {per} - ${cost:,.2f} over {views:,} views "
        f"from {len(priced)} video(s)"
    )


def cost_rows(channel_id: str, *, today: date | None = None) -> list[dict[str, Any]]:
    """Videos published 7-14 days ago with their run cost and first-7-day organic views."""
    from core.success.videos import channel_videos
    from storage.repositories.content_runs import get_content_run_repository

    day = today or date.today()
    repo = get_content_run_repository()
    rows: list[dict[str, Any]] = []
    for video in channel_videos(channel_id):
        published = video.published_at.date() if video.published_at else None
        if published is None or not (
            day - timedelta(days=14) <= published <= day - timedelta(days=7)
        ):
            continue
        cost = None
        try:
            run = repo.get(int(video.run_id)) if video.run_id else None
            features = json.loads(getattr(run, "features_json", "") or "{}") if run else {}
            cost = ((features or {}).get("cost") or {}).get("total")
        except Exception as exc:
            logger.debug("run cost unread for %s: %s", video.video_id, exc)
        rows.append({"title": video.title, "cost": cost, "views": video.views_7d})
    return rows


def hours_week(minutes: list[float]) -> float:
    """#1728: the long videos' organic minutes this week, as hours."""
    return round(sum(float(m) for m in minutes) / 60.0, 1)


def weeks_to(target: float, have: float, per_week: float) -> str:
    if per_week <= 0:
        return "no pace yet"
    weeks = (float(target) - float(have)) / per_week
    return "reached" if weeks <= 0 else f"about {weeks:,.0f} weeks"


def long_minutes(channel_id: str) -> list[float]:
    """Each long video's organic minutes a week, from its synced window (`estimated_minutes_watched`
    over `period_start`-`period_end`, less the paid share). Long = a compilation or a long draft."""
    from storage.repositories.content_runs import get_content_run_repository
    from storage.repositories.publish_log import get_publish_log_repository

    repo = get_content_run_repository()
    out: list[float] = []
    for row in get_publish_log_repository().list_uploaded_for_channel(channel_id) or []:
        try:
            metrics = json.loads(getattr(row, "metrics_json", "") or "{}") or {}
            minutes = metrics.get("estimated_minutes_watched")
            run_id = getattr(row, "content_run_id", None)
            run = repo.get(int(run_id)) if run_id else None
            features = json.loads(getattr(run, "features_json", "") or "{}") if run else {}
        except Exception as exc:
            logger.debug("long minutes unread: %s", exc)
            continue
        if minutes is None or not (features.get("compilation") or features.get("long_form")):
            continue
        views, paid = float(metrics.get("views") or 0), float(metrics.get("paid_views") or 0)
        organic = float(minutes) * (1 - paid / views) if views > 0 else float(minutes)
        try:
            span = (date.fromisoformat(str(metrics["period_end"])[:10])
                    - date.fromisoformat(str(metrics["period_start"])[:10])).days + 1  # fmt: skip
        except (KeyError, ValueError):
            span = 28
        out.append(organic * 7 / max(span, 1))
    return out


def hours_lines(minutes: list[float], *, have: float | None, bars: tuple[int, int]) -> list[str]:
    """#1728: this week's long-form hours, and the weeks to today's bar and the new one."""
    if not minutes:
        return ["long-form hours this week: not measured (no long video with a synced window)"]
    week = hours_week(minutes)
    now_bar, new_bar = bars
    base = float(have or 0)
    if week <= 0:
        return [f"long-form hours this week: 0.0 from {len(minutes)} long video(s) - no pace yet"]
    return [
        f"long-form hours this week: {week:,.1f} from {len(minutes)} long video(s); at this pace "
        f"{now_bar:,} hours is {weeks_to(now_bar, base, week)} away, {new_bar:,} is "
        f"{weeks_to(new_bar, base, week)}"
    ]


def wave_rows() -> list[dict[str, Any]]:
    try:
        with open(_WAVES_FILE, encoding="utf-8") as handle:
            rows = (json.load(handle) or {}).get("waves") or []
    except (OSError, ValueError, AttributeError) as exc:
        logger.debug("waves.json unread: %s", exc)
        return []
    return [r for r in rows if isinstance(r, dict) and r.get("wave") and r.get("shipped")]


def scorecard_line(row: dict[str, Any], series: dict[date, int], *, today: date) -> str:
    """#1836: "wave 133 (views): 412 a day after against 251 before - up 64%", once 14 days have
    passed; "" before that or with no days to compare."""
    shipped = date.fromisoformat(str(row["shipped"])[:10])
    if today < shipped + timedelta(days=SCORE_DAYS):
        return ""
    before = [series.get(shipped - timedelta(days=i)) for i in range(1, SCORE_DAYS + 1)]
    after = [series.get(shipped + timedelta(days=i)) for i in range(0, SCORE_DAYS)]
    b = [v for v in before if v is not None]
    a = [v for v in after if v is not None]
    if not a or not b:
        return f"wave {row['wave']} ({row.get('lane')}): not measured - the days are not synced"
    mean_a, mean_b = sum(a) / len(a), sum(b) / len(b)
    change = (mean_a - mean_b) / mean_b * 100 if mean_b else 0.0
    word = "up" if change >= 0 else "down"
    return (
        f"wave {row['wave']} ({row.get('lane')}): {mean_a:,.0f} a day after against "
        f"{mean_b:,.0f} before - {word} {abs(change):.0f}%"
    )


def organic_daily(channel_id: str) -> dict[date, int]:
    from core.success.goals import channel_daily_views, channel_paid_daily

    views, _source = channel_daily_views(channel_id)
    paid = channel_paid_daily(channel_id)
    return {day: max(0, int(n) - int(paid.get(day, 0))) for day, n in views.items()}


def scorecard_lines(channel_id: str, *, today: date | None = None) -> list[str]:
    day = today or date.today()
    rows = wave_rows()
    if not rows:
        return []
    series = organic_daily(channel_id)
    lines = [scorecard_line(r, series, today=day) for r in rows]
    shown = [line for line in lines if line]
    waiting = sum(1 for line in lines if not line)
    out = ["Wave scorecard (organic views a day, 14 days after against 14 before):"]
    out += [f"  {line}" for line in shown]
    if waiting:
        out.append(f"  {waiting} wave(s) not 14 days old yet")
    return out


def breakouts(rows: list[dict[str, Any]], *, now: datetime) -> list[dict[str, Any]]:
    """#1832: videos past `BREAKOUT_VIEWS` organic views within `BREAKOUT_HOURS` of publishing."""
    out = []
    for row in rows:
        published = row.get("published_at")
        if not isinstance(published, datetime):
            continue
        stamp = published if published.tzinfo else published.replace(tzinfo=timezone.utc)
        age = (now - stamp).total_seconds() / 3600
        if 0 <= age <= BREAKOUT_HOURS and int(row.get("organic") or 0) >= BREAKOUT_VIEWS:
            out.append(row)
    return out


def toast_breakouts(channel_id: str, *, now: datetime | None = None) -> list[str]:
    """One toast a day per breakout video (`win_notify.toast_daily`). The titles toasted."""
    from core.win_notify import toast_daily
    from storage.repositories.publish_log import get_publish_log_repository

    moment = now or datetime.now(timezone.utc)
    rows = []
    for row in get_publish_log_repository().list_uploaded_for_channel(channel_id) or []:
        try:
            metrics = json.loads(getattr(row, "metrics_json", "") or "{}") or {}
        except ValueError:
            continue
        total = metrics.get("lifetime_views") or metrics.get("views") or 0
        organic = max(0, int(total) - int(metrics.get("paid_views") or 0))
        rows.append({"video_id": str(getattr(row, "youtube_video_id", "") or ""),
                     "title": str(getattr(row, "title", "") or ""),
                     "published_at": getattr(row, "published_at", None), "organic": organic})  # fmt: skip
    shown = []
    for hit in breakouts(rows, now=moment):
        title = hit["title"] or hit["video_id"]
        if toast_daily(f"breakout:{hit['video_id']}", "A Short is breaking out",
                       f"{title[:60]} - {hit['organic']:,} organic views in under a day. "
                       "A follow-up while it runs: py -m scripts.ops batch-review", now=moment):  # fmt: skip
            shown.append(title)
    return shown
