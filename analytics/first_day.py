"""A first-day alert: a video far below (or above) the channel's usual first day (#49).

The metrics sync freezes each video's 24-hour snapshot and nothing compared it with
anything, so a video that died on day one was found at the weekly report. When a sync first
captures a video's 24h snapshot, `judge` compares its organic views (paid views out, #954)
with the median of the channel's other 24h snapshots:

- below `FIRST_DAY_LOW` (0.5) x the median -> "low"; above `FIRST_DAY_HIGH` (2) x -> "high";
- fewer than `FIRST_DAY_MIN_BASELINE` (5) other videos -> "collecting", and nothing is said.

The verdict is stored once as `metrics["first_day"]`. The sync prints each low or high
video, `ops status` repeats it for a week (`recent_lines`), and an automation webhook gets
a `first_day_anomaly` event (only when `EVENT_WEBHOOK_URL` is set). Never raises.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("analytics.first_day")

EVENT = "first_day_anomaly"
_RECENT_DAYS = 7


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "") or default)
    except ValueError:
        return default


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _repo() -> Any:
    from storage.repositories.publish_log import get_publish_log_repository

    return get_publish_log_repository()


def _median(values: list[int]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    return float(ordered[mid]) if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def organic_first_day(snapshot: dict[str, Any] | None) -> int | None:
    """A 24h snapshot's views without its paid views; None when it has no views."""
    if not isinstance(snapshot, dict) or snapshot.get("views") is None:
        return None
    try:
        return max(0, int(snapshot["views"]) - int(snapshot.get("paid_views") or 0))
    except (TypeError, ValueError):
        return None


def judge(views: int, baseline: list[int]) -> dict[str, Any]:
    """{verdict, views, baseline, ratio, n}: low / high / normal, or collecting."""
    need = int(_env_float("FIRST_DAY_MIN_BASELINE", 5))
    out: dict[str, Any] = {"views": int(views), "n": len(baseline)}
    if len(baseline) < max(1, need):
        return {**out, "verdict": "collecting"}
    median = _median(baseline)
    ratio = views / median if median > 0 else None
    out.update(baseline=round(median), ratio=round(ratio, 3) if ratio is not None else None)
    if ratio is None:
        return {**out, "verdict": "normal"}
    if ratio < _env_float("FIRST_DAY_LOW", 0.5):
        return {**out, "verdict": "low"}
    if ratio > _env_float("FIRST_DAY_HIGH", 2.0):
        return {**out, "verdict": "high"}
    return {**out, "verdict": "normal"}


def _metrics(row: Any) -> dict[str, Any]:
    try:
        loaded = json.loads(getattr(row, "metrics_json", None) or "{}")
    except (TypeError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _baseline(channel_id: str, exclude_id: Any) -> list[int]:
    out: list[int] = []
    for row in _repo().list_uploaded_for_channel(channel_id) or []:
        if getattr(row, "id", None) == exclude_id:
            continue
        snaps = _metrics(row).get("snapshots")
        views = organic_first_day(snaps.get("24h") if isinstance(snaps, dict) else None)
        if views is not None:
            out.append(views)
    return out


def check(
    channel_id: str,
    metrics: dict[str, Any],
    *,
    log_id: Any,
    run_id: Any = None,
    video_id: str = "",
    title: str = "",
) -> dict[str, Any] | None:
    """Judge a video whose 24h snapshot is new and not judged yet; stores the verdict in
    `metrics` and sends the event for low or high. None when there is nothing to judge."""
    try:
        if isinstance(metrics.get("first_day"), dict):
            return None
        snaps = metrics.get("snapshots")
        views = organic_first_day(snaps.get("24h") if isinstance(snaps, dict) else None)
        if views is None:
            return None
        verdict = judge(views, _baseline(channel_id, log_id))
        verdict["judged_at"] = _now().isoformat()
        metrics["first_day"] = verdict
        if verdict["verdict"] in ("low", "high"):
            from core.events import emit_event

            emit_event(EVENT, {"channel_id": channel_id, "run_id": run_id,
                               "youtube_video_id": video_id, "title": title,
                               **verdict})  # fmt: skip
            logger.info("%s", line(title or video_id, verdict))
        return verdict
    except Exception as exc:
        logger.debug("first-day check skipped: %s", exc)
        return None


def line(title: str, verdict: dict[str, Any]) -> str:
    word = "below" if verdict.get("verdict") == "low" else "above"
    ratio = verdict.get("ratio")
    times = f"{ratio:.1f}x" if isinstance(ratio, int | float) else "?"
    return (
        f"First day: '{title[:50]}' had {verdict.get('views', 0):,} views - {times} the "
        f"channel's usual {verdict.get('baseline', 0):,} (median of {verdict.get('n', 0)}), "
        f"well {word} normal"
    )


def recent_lines(
    channel_id: str, *, days: int = _RECENT_DAYS, since: datetime | None = None
) -> list[str]:
    """Low or high first days judged in the last `days` days (or since `since`), newest
    first."""
    cutoff = since or (_now() - timedelta(days=days))
    found: list[tuple[datetime, str]] = []
    try:
        for row in _repo().list_uploaded_for_channel(channel_id) or []:
            verdict = _metrics(row).get("first_day")
            if not isinstance(verdict, dict) or verdict.get("verdict") not in ("low", "high"):
                continue
            try:
                when = datetime.fromisoformat(str(verdict.get("judged_at") or ""))
            except ValueError:
                continue
            when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
            if when >= cutoff:
                title = str(getattr(row, "detail", "") or getattr(row, "youtube_video_id", ""))
                found.append((when, line(title, verdict)))
    except Exception as exc:
        logger.debug("first-day lines skipped: %s", exc)
    return [text for _when, text in sorted(found, reverse=True)]
