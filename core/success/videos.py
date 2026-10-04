"""The channel's published videos as one list, for the success modules.

Read from the publish log (`list_timed_outcomes`: live videos with a publish time). Seeded
rows (#927) keep their real titles and views - the winners library and verdicts may use
them - but their publish times are invented, so anything dated leaves them out.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.logging import get_logger
from core.success.target import views_7d

logger = get_logger("core.success.videos")


@dataclass
class Video:
    video_id: str
    title: str
    published_at: datetime | None
    views: int
    engaged_rate: float | None
    run_id: int | None
    seeded: bool
    domain: str = ""
    first_views_days: int | None = None
    daily_views: list[list[Any]] = field(default_factory=list)
    views_7d: int | None = None  # #940: views in the first 7 days, comparable across ages
    lifetime_views: int | None = None  # #940: to date, from videos.list statistics
    daily_paid_views: list[list[Any]] = field(default_factory=list)  # #954
    paid_views: int = 0  # #954: every paid (ADVERTISING) view the sync has seen, all days
    paid_window: int = 0  # #954: the paid views inside `views`' 28-day window
    packaging: dict[str, Any] = field(default_factory=dict)  # #951: analytics/packaging

    @property
    def organic_views(self) -> int:
        """`views` (the last sync's window) without its paid views (#954)."""
        return max(0, self.views - self.paid_window)


def _metrics(raw: Any) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _int(value: Any) -> int:
    try:
        return max(0, int(float(value or 0)))
    except (TypeError, ValueError):
        return 0


def _total(daily: list[Any]) -> int:
    total = 0
    for item in daily:
        try:
            total += int(float(item[1]))
        except (TypeError, ValueError, IndexError):
            continue
    return total


def _packaging(metrics: dict[str, Any]) -> dict[str, Any]:
    try:
        from analytics.packaging import packaging_figures

        return packaging_figures(metrics)
    except Exception as exc:
        logger.debug("packaging figures skipped: %s", exc)
        return {}


def channel_videos(channel_id: str, *, include_seeded: bool = True) -> list[Video]:
    """Every live video of the channel, newest first. Never raises."""
    try:
        from storage.repositories.publish_log import get_publish_log_repository, is_seeded

        rows = get_publish_log_repository().list_timed_outcomes(channel_id)
    except Exception as exc:
        logger.debug("publish log unavailable for %s: %s", channel_id, exc)
        return []
    out: list[Video] = []
    seen: set[str] = set()
    for row in rows:
        video_id = str(getattr(row, "youtube_video_id", "") or "")
        if not video_id or video_id in seen:
            continue
        seeded = is_seeded(row)
        if seeded and not include_seeded:
            continue
        seen.add(video_id)
        metrics = _metrics(getattr(row, "metrics_json", None))
        try:
            views = int(float(metrics.get("views") or 0))
        except (TypeError, ValueError):
            views = 0
        rate = metrics.get("engaged_rate")
        first = metrics.get("first_views")
        published_at = _utc(getattr(row, "published_at", None))
        lifetime = metrics.get("lifetime_views")
        run_id = getattr(row, "content_run_id", None)
        paid_daily = list(metrics.get("daily_paid_views") or [])
        out.append(
            Video(
                video_id=video_id,
                title=str(getattr(row, "detail", "") or "").strip() or "(untitled)",
                published_at=published_at,
                views=views,
                engaged_rate=float(rate) if isinstance(rate, (int, float)) else None,
                run_id=int(run_id) if isinstance(run_id, int) else None,
                seeded=seeded,
                domain=str(metrics.get("domain") or ""),
                first_views_days=first.get("days") if isinstance(first, dict) else None,
                daily_views=list(metrics.get("daily_views") or []),
                views_7d=None if seeded else views_7d(metrics, published_at),
                lifetime_views=int(lifetime) if isinstance(lifetime, (int, float)) else None,
                daily_paid_views=paid_daily,
                paid_views=_total(paid_daily),
                paid_window=_int(metrics.get("paid_views")),
                packaging=_packaging(metrics),
            )
        )
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    out.sort(key=lambda v: v.published_at or epoch, reverse=True)
    return out


# #940: the measure a ranking of videos uses. The stored `views` is the last sync's 28-day
# window, so a three-month-old hit reads as small; views in the first 7 days compare every
# video at the same age, and lifetime views are the honest second best. #954: every measure
# is organic - lifetime views less the paid views the sync has seen (a lower bound on the
# paid part, so an upper bound on organic), the window less its own paid views.
COMPARABLE_MIN = 8
_MEASURES = {
    "7d": ("views in their first 7 days", "views in 7 days"),
    "lifetime": ("views to date", "views to date"),
    "window": ("views (the 28-day window at each video's last sync)", "views"),
}


def comparable_views(
    videos: list[Video], *, min_count: int = COMPARABLE_MIN
) -> tuple[list[tuple[Video, int]], str, str]:
    """([(video, value)] best first, the ranking's label, the value's unit).

    The first measure that `min_count` videos have wins - a ranking never mixes two.
    """
    for key, read in (
        ("7d", lambda v: v.views_7d),
        (
            "lifetime",
            lambda v: (
                max(0, v.lifetime_views - v.paid_views) if v.lifetime_views is not None else None
            ),
        ),
        ("window", lambda v: v.organic_views or None),
    ):
        pairs = [(v, int(value)) for v in videos if (value := read(v))]
        if len(pairs) >= min_count or key == "window":
            pairs.sort(key=lambda p: p[1], reverse=True)
            heading, unit = _MEASURES[key]
            return pairs, heading, unit
    return [], *_MEASURES["window"]
