"""What the recommenders aim at (#938; operator, 2026-10-03: 7-day views, switchable).

The goal is views (#934), but the best bet, the length recommender and post time all
ranked on the engaged rate. They now read one per-video outcome from here:

- `views` (the default): the video's views in its first 7 days (`views_7d`), from YouTube
  Analytics' views by day (#563). Every video is measured at the same age, so an old video
  is not favoured for having had longer, and a new one is not counted until its seventh
  day is in. Values are kept on a log scale (`log1p`) for the means and shrinkage - one
  viral video does not drag a whole domain's average - and shown back as views.
- `engaged`: the engaged rate, exactly as before (`RECOMMEND_TARGET=engaged`).

A video counts under `views` only when its views-by-day series starts on its publish day
(the sync's 28-day window does not, for anything older than four weeks; `ops backfill
view-curve --apply` fetches from the publish day). The engagement predictor stays on the
engaged rate: its predictions are frozen into the grade and the ledger on that scale.
"""

from __future__ import annotations

import json
import math
import os
from datetime import date, datetime, timedelta
from typing import Any

TARGET_VIEWS = "views"
TARGET_ENGAGED = "engaged"
_LABELS = {TARGET_VIEWS: "7-day views", TARGET_ENGAGED: "engaged rate"}


def target() -> str:
    """`RECOMMEND_TARGET`: "views" (default) or "engaged"."""
    raw = (os.getenv("RECOMMEND_TARGET") or "").strip().lower()
    return TARGET_ENGAGED if raw in ("engaged", "engaged_rate", "engagement") else TARGET_VIEWS


def label(target_name: str | None = None) -> str:
    return _LABELS[target_name or target()]


def views_7d(metrics: dict[str, Any], published_at: datetime | None) -> int | None:
    """Views in the video's first 7 days (publish day + 6, Pacific), or None.

    None unless the series starts on or before the publish day and reaches its seventh
    day: a later start cannot say what the first days were, and a shorter series is not
    seven days yet. A video whose first day had no views at all reads as a late start -
    left out rather than guessed.
    """
    from analytics.view_curve import publish_day

    start = publish_day(published_at)
    if start is None or not isinstance(metrics, dict):
        return None
    series: dict[date, int] = {}
    for item in metrics.get("daily_views") or []:
        try:
            day, views = date.fromisoformat(str(item[0])[:10]), int(float(item[1]))
        except (TypeError, ValueError, IndexError):
            continue
        series[day] = views
    if not series or min(series) > start or max(series) < start + timedelta(days=6):
        return None
    end = start + timedelta(days=6)
    return sum(v for d, v in series.items() if start <= d <= end)


def outcome(
    metrics_json: str | None,
    published_at: datetime | None = None,
    *,
    target_name: str | None = None,
) -> float | None:
    """The per-video value a recommender ranks on, or None when the video has none."""
    from core.engagement import engaged_rate, under_view_floor

    name = target_name or target()
    if name == TARGET_ENGAGED:
        return engaged_rate(metrics_json or "{}")
    try:
        metrics = json.loads(metrics_json or "{}")
    except (TypeError, ValueError):
        return None
    if not isinstance(metrics, dict) or under_view_floor(metrics):
        return None
    views = views_7d(metrics, published_at)
    return math.log1p(views) if views is not None else None


def show(value: float, *, places: int = 1, target_name: str | None = None) -> str:
    """ "14.2% engagement" or "1,240 views in 7 days"."""
    if (target_name or target()) == TARGET_ENGAGED:
        return f"{value:.{places}%} engagement"
    return f"{math.expm1(value):,.0f} views in 7 days"


def interval_note(values: list[float], *, target_name: str | None = None) -> str:
    """The rationale's spread: "+/- 22pp" for a rate, a 95% range of views for views."""
    from core import recommender_confidence

    if (target_name or target()) == TARGET_ENGAGED:
        return recommender_confidence.interval_note(values)
    half = recommender_confidence.confidence_interval(values)
    if half is None:
        return ""
    mean = sum(values) / len(values)
    low, high = math.expm1(max(0.0, mean - half)), math.expm1(mean + half)
    return f" (95% range ~{low:,.0f}-{high:,.0f})"


def ranked_on_note(
    raw: float, adjusted: float | None, *, places: int = 1, target_name: str | None = None
) -> str:
    """Name the shrunk figure that ranked, when it differs from the printed one."""
    from core import recommender_confidence

    if (target_name or target()) == TARGET_ENGAGED:
        return recommender_confidence.ranked_on_note(raw, adjusted, places=places)
    if adjusted is None:
        return ""
    shown, ranked = round(math.expm1(raw)), round(math.expm1(adjusted))
    if shown == ranked:
        return ""
    return f" (ranked on ~{ranked:,} shrunk toward the channel mean)"
