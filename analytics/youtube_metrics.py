"""
YouTube Analytics ingestion — views, engagement → learning loop.
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from typing import Any

from googleapiclient.errors import HttpError

from apis.topic_scorer import infer_domain
from config.channels import resolve_channel_id
from core.logging import get_logger
from core.run_recorder import record_publish_outcome
from storage.repositories.publish_log import get_publish_log_repository
from youtube.oauth import get_youtube_analytics_service

logger = get_logger("analytics.youtube_metrics")


def _analytics_enabled() -> bool:
    return os.getenv("YOUTUBE_ANALYTICS_SYNC", "").lower() in ("1", "true", "yes")


def _date_range(days: int = 28) -> tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=days)
    return start.isoformat(), end.isoformat()


def _parse_report_row(row: list, headers: list) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for i, name in enumerate(headers):
        if i < len(row):
            out[name] = row[i]
    return out


def _curve_sync_enabled() -> bool:
    return os.getenv("RETENTION_CURVE_SYNC", "true").lower() in ("1", "true", "yes")


def _fetch_retention_curve(video_id, service, start_date, end_date) -> list | None:
    """Audience-retention curve: [[elapsed_ratio, watch_ratio], ...] or None.

    A separate Analytics report from the headline metrics. Best-effort — short or
    low-watch videos return no rows (common on small channels), so it never breaks
    the main sync. Feeds the pacing model in core/retention.py.
    """
    if not _curve_sync_enabled():
        return None
    try:
        resp = (
            service.reports()
            .query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics="audienceWatchRatio",
                dimensions="elapsedVideoTimeRatio",
                filters=f"video=={video_id}",
            )
            .execute()
        )
    except Exception as exc:
        logger.debug("retention curve fetch failed for %s: %s", video_id, exc)
        return None
    curve: list[list[float]] = []
    for row in resp.get("rows") or []:
        try:
            curve.append([round(float(row[0]), 3), round(float(row[1]), 4)])
        except (ValueError, IndexError, TypeError):
            continue
    return curve or None


def _fetch_estimated_revenue(video_id, service, start_date, end_date) -> float | None:
    """AdSense estimatedRevenue for one video, or None (Pillar 1 unit economics).

    A separate report on purpose: the metric needs the yt-analytics-monetary
    scope AND a monetized channel — bundling it into the headline query would
    403 the whole sync for everyone else. Any failure reads as "no revenue
    data", never an error.
    """
    try:
        resp = (
            service.reports()
            .query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics="estimatedRevenue",
                filters=f"video=={video_id}",
            )
            .execute()
        )
        rows = resp.get("rows") or []
        if rows and rows[0]:
            return round(float(rows[0][-1] or 0.0), 4)
    except Exception as exc:
        logger.debug("estimatedRevenue fetch skipped for %s: %s", video_id, exc)
    return None


def fetch_video_metrics(
    youtube_video_id: str,
    *,
    channel_id: str | None = None,
) -> dict[str, Any] | None:
    """
    Query YouTube Analytics API for a single video (last 28 days).
    Requires yt-analytics.readonly on the channel OAuth token.
    """
    if not _analytics_enabled():
        return None

    channel_id = resolve_channel_id(channel_id)
    service = get_youtube_analytics_service(channel_id)
    if not service:
        return None

    start_date, end_date = _date_range()
    metrics = (
        "views,likes,comments,shares,subscribersGained,"
        "averageViewPercentage,estimatedMinutesWatched"
    )

    try:
        response = (
            service.reports()
            .query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics=metrics,
                dimensions="video",
                filters=f"video=={youtube_video_id}",
            )
            .execute()
        )
    except HttpError as e:
        logger.warning("Analytics query failed for %s: %s", youtube_video_id, e)
        return None
    except Exception as e:
        logger.warning("Analytics error: %s", e)
        return None

    headers = [h["name"] for h in response.get("columnHeaders", [])]
    rows = response.get("rows") or []
    if not rows:
        logger.debug("No analytics rows yet for video %s", youtube_video_id)
        return None

    parsed = _parse_report_row(rows[0], headers)
    views = int(float(parsed.get("views", 0) or 0))
    avg_pct = float(parsed.get("averageViewPercentage", 0) or 0)
    engaged_rate = round(avg_pct / 100.0, 4) if avg_pct else 0.0

    result = {
        "youtube_video_id": youtube_video_id,
        "views": views,
        "likes": int(float(parsed.get("likes", 0) or 0)),
        "comments": int(float(parsed.get("comments", 0) or 0)),
        "shares": int(float(parsed.get("shares", 0) or 0)),
        "subscribers_gained": int(float(parsed.get("subscribersGained", 0) or 0)),
        "average_view_percentage": avg_pct,
        "engaged_rate": engaged_rate,
        "estimated_minutes_watched": float(parsed.get("estimatedMinutesWatched", 0) or 0),
        "period_start": start_date,
        "period_end": end_date,
    }
    curve = _fetch_retention_curve(youtube_video_id, service, start_date, end_date)
    if curve:
        result["retention_curve"] = curve
    revenue = _fetch_estimated_revenue(youtube_video_id, service, start_date, end_date)
    if revenue is not None:
        result["estimated_revenue_usd"] = revenue
    return result


def refresh_publish_metrics(
    *,
    content_run_id: int,
    youtube_video_id: str,
    channel_id: str | None = None,
    topic: str = "",
    title: str = "",
    publish_log_id: int | None = None,
) -> bool:
    """
    Pull metrics for an uploaded video, update publish_log, and record learning.
    Returns True when metrics were applied.
    """
    channel_id = resolve_channel_id(channel_id)
    metrics = fetch_video_metrics(youtube_video_id, channel_id=channel_id)
    if not metrics:
        return False

    views = int(metrics.get("views", 0))
    engaged_rate = float(metrics.get("engaged_rate", 0.0))
    domain = infer_domain(topic or title, channel_id)

    repo = get_publish_log_repository()
    log_id = publish_log_id
    if not log_id:
        key = f"run:{channel_id}:{content_run_id}"
        row = repo.find_by_idempotency(key)
        if row:
            log_id = row.id
    if log_id:
        repo.update(log_id, {"metrics_json": json.dumps(metrics)})

    record_publish_outcome(
        channel_id=channel_id,
        topic=topic or title,
        domain=domain,
        views=views,
        engaged_rate=engaged_rate,
        likes=int(metrics.get("likes", 0)),
        subscribers_gained=int(metrics.get("subscribers_gained", 0)),
        content_run_id=content_run_id,
        title=title,
    )
    logger.info(
        "Synced metrics for %s: views=%s engaged_rate=%s",
        youtube_video_id,
        views,
        engaged_rate,
    )
    return True
