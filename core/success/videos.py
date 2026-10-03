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
        run_id = getattr(row, "content_run_id", None)
        out.append(
            Video(
                video_id=video_id,
                title=str(getattr(row, "detail", "") or "").strip() or "(untitled)",
                published_at=_utc(getattr(row, "published_at", None)),
                views=views,
                engaged_rate=float(rate) if isinstance(rate, (int, float)) else None,
                run_id=int(run_id) if isinstance(run_id, int) else None,
                seeded=seeded,
                domain=str(metrics.get("domain") or ""),
                first_views_days=first.get("days") if isinstance(first, dict) else None,
                daily_views=list(metrics.get("daily_views") or []),
            )
        )
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    out.sort(key=lambda v: v.published_at or epoch, reverse=True)
    return out
