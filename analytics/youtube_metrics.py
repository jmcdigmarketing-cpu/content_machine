"""
YouTube Analytics ingestion — views, engagement → learning loop.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

from googleapiclient.errors import HttpError

from apis.topic_scorer import infer_domain
from config.channels import resolve_channel_id
from core.logging import get_logger
from core.run_recorder import record_publish_outcome
from storage.repositories.publish_log import get_publish_log_repository
from youtube.oauth import get_youtube_analytics_service, get_youtube_service

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


def _fetch_engaged_views(video_id, service, start_date, end_date) -> int | None:
    """`engagedViews` for one video, or None (#951). Its own best-effort query: a metric the
    API rejected would otherwise take the headline numbers down with it.

    Since 2025-03-31 a Shorts view is any start or replay; engaged views keep the old
    counting, so engaged / views is the share of starts that were not swiped away.
    """
    try:
        resp = (
            service.reports()
            .query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics="engagedViews",
                dimensions="video",
                filters=f"video=={video_id}",
            )
            .execute()
        )
        rows = _named_rows(resp or {})
        return int(float(rows[0]["engagedViews"])) if rows else None
    except Exception as exc:
        logger.debug("engagedViews fetch skipped for %s: %s", video_id, exc)
        return None


def _fetch_views_by_day(video_id, service, start_date, end_date) -> list[list[Any]] | None:
    """[[YYYY-MM-DD, views], ...] for one video - or the whole channel when `video_id` is
    None (#934) - or None when the query failed (#563). Best-effort, like the retention
    curve: a failure never breaks the headline sync. [] is "asked, no views" (#947: a video
    with none must still count as fetched, or the backfill asks again forever)."""
    query: dict[str, Any] = {
        "ids": "channel==MINE",
        "startDate": start_date,
        "endDate": end_date,
        "metrics": "views",
        "dimensions": "day",
        "sort": "day",
    }
    if video_id:
        query["filters"] = f"video=={video_id}"
    try:
        resp = service.reports().query(**query).execute()
    except Exception as exc:
        logger.debug("views by day fetch failed for %s: %s", video_id, exc)
        return None
    daily: list[list[Any]] = []
    for row in resp.get("rows") or []:
        try:
            daily.append([str(row[0])[:10], int(float(row[1]))])
        except (ValueError, IndexError, TypeError):
            continue
    return daily


def fetch_daily_views(
    youtube_video_id: str, *, channel_id: str | None = None, start: str, end: str
) -> list[list[Any]] | None:
    """Views by day between two dates - `ops backfill view-curve` asks from the publish day."""
    if not _analytics_enabled():
        return None
    service = get_youtube_analytics_service(resolve_channel_id(channel_id))
    if not service:
        return None
    return _fetch_views_by_day(youtube_video_id, service, start, end)


def fetch_channel_daily_views(
    *, channel_id: str | None = None, start: str, end: str
) -> list[list[Any]] | None:
    """The channel's views by day (every video, Shorts included) - the scoreboard (#934)."""
    if not _analytics_enabled():
        return None
    service = get_youtube_analytics_service(resolve_channel_id(channel_id))
    if not service:
        return None
    return _fetch_views_by_day(None, service, start, end)


# #954: what YouTube calls paid traffic. Promotion views, watch time and subscribers do not
# count toward YPP, and a boosted video is not a winner the recommenders should chase.
PAID_SOURCES = frozenset({"ADVERTISING"})
# creatorContentType values whose watch time counts toward YPP's 4,000 public hours.
LONG_FORM_TYPES = frozenset({"VIDEO_ON_DEMAND", "LIVE_STREAM"})


def _named_rows(resp: dict[str, Any]) -> list[dict[str, Any]]:
    """The report's rows as {column name: value}, read by header, not by position."""
    headers = [str(h.get("name") or "") for h in resp.get("columnHeaders") or []]
    return [dict(zip(headers, row, strict=False)) for row in resp.get("rows") or []]


def _fetch_views_by_source_day(
    video_id: str | None, service: Any, start_date: str, end_date: str
) -> tuple[list[list[Any]], dict[str, int]] | None:
    """(paid views by day, {traffic source: views} over the range), or None (#954).

    One Analytics query - views by day and `insightTrafficSourceType`, for one video or (no
    id) the whole channel. An empty paid list means "asked, none paid".
    """
    query: dict[str, Any] = {
        "ids": "channel==MINE",
        "startDate": start_date,
        "endDate": end_date,
        "metrics": "views",
        "dimensions": "day,insightTrafficSourceType",
        "sort": "day",
    }
    if video_id:
        query["filters"] = f"video=={video_id}"
    try:
        resp = service.reports().query(**query).execute()
    except Exception as exc:
        logger.debug("views by source failed for %s: %s", video_id or "channel", exc)
        return None
    paid: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for row in _named_rows(resp or {}):
        try:
            day = str(row["day"])[:10]
            source = str(row["insightTrafficSourceType"])
            views = int(float(row["views"]))
        except (KeyError, TypeError, ValueError):
            continue
        by_source[source] = by_source.get(source, 0) + views
        if source in PAID_SOURCES:
            paid[day] = paid.get(day, 0) + views
    return [[day, paid[day]] for day in sorted(paid)], by_source


def _fetch_watch_by_source(
    video_id: str, service: Any, start_date: str, end_date: str
) -> dict[str, tuple[int, float]] | None:
    """{traffic source: (views, minutes watched)} for one video, or None (#957)."""
    try:
        resp = (
            service.reports()
            .query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics="views,estimatedMinutesWatched",
                dimensions="insightTrafficSourceType",
                filters=f"video=={video_id}",
            )
            .execute()
        )
    except Exception as exc:
        logger.debug("watch time by source failed for %s: %s", video_id, exc)
        return None
    out: dict[str, tuple[int, float]] = {}
    for row in _named_rows(resp or {}):
        try:
            source = str(row["insightTrafficSourceType"])
            views, minutes = int(float(row["views"])), float(row["estimatedMinutesWatched"])
        except (KeyError, TypeError, ValueError):
            continue
        old_views, old_minutes = out.get(source, (0, 0.0))
        out[source] = (old_views + views, old_minutes + minutes)
    return out


def organic_engaged_rate(
    average_view_percentage: float, watch: dict[str, tuple[int, float]]
) -> float | None:
    """#957: the average view % without the paid viewers, as a 0..1 rate, or None.

    organic % = total % x (organic minutes / organic views) / (all minutes / all views) -
    the video's length cancels out. None when either side has no views or minutes.
    """
    all_views = sum(v for v, _m in watch.values())
    all_minutes = sum(m for _v, m in watch.values())
    organic = [(v, m) for source, (v, m) in watch.items() if source not in PAID_SOURCES]
    org_views = sum(v for v, _m in organic)
    org_minutes = sum(m for _v, m in organic)
    if not (average_view_percentage and all_views and all_minutes and org_views and org_minutes):
        return None
    ratio = (org_minutes / org_views) / (all_minutes / all_views)
    return round(min(1.0, average_view_percentage / 100.0 * ratio), 4)


def fetch_daily_paid_views(
    youtube_video_id: str, *, channel_id: str | None = None, start: str, end: str
) -> list[list[Any]] | None:
    """A video's paid views by day - `ops backfill view-curve` asks from the publish day."""
    if not _analytics_enabled():
        return None
    service = get_youtube_analytics_service(resolve_channel_id(channel_id))
    if not service:
        return None
    result = _fetch_views_by_source_day(youtube_video_id, service, start, end)
    return result[0] if result is not None else None


def fetch_channel_paid_daily_views(
    *, channel_id: str | None = None, start: str, end: str
) -> list[list[Any]] | None:
    """The channel's paid views by day - the scoreboard counts organic (#954)."""
    if not _analytics_enabled():
        return None
    service = get_youtube_analytics_service(resolve_channel_id(channel_id))
    if not service:
        return None
    result = _fetch_views_by_source_day(None, service, start, end)
    return result[0] if result is not None else None


def _by_source_and_type(
    service: Any, start_date: str, end_date: str, metric: str
) -> dict[tuple[str, str], float] | None:
    """{(traffic source, content type): metric} for the whole channel, or None."""
    try:
        resp = (
            service.reports()
            .query(
                ids="channel==MINE",
                startDate=start_date,
                endDate=end_date,
                metrics=metric,
                dimensions="insightTrafficSourceType,creatorContentType",
            )
            .execute()
        )
    except Exception as exc:
        logger.debug("%s by source and type failed: %s", metric, exc)
        return None
    out: dict[tuple[str, str], float] = {}
    for row in _named_rows(resp or {}):
        try:
            key = (str(row["insightTrafficSourceType"]), str(row["creatorContentType"]))
            out[key] = out.get(key, 0.0) + float(row[metric])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _subscriber_count(channel_id: str) -> int | None:
    """The channel's subscribers from `channels.list` statistics (1 unit), or None."""
    service = get_youtube_service(channel_id)
    if not service:
        return None
    try:
        resp = (
            service.channels()
            .list(part="statistics", mine=True, fields="items(statistics/subscriberCount)")
            .execute()
        )
        items = resp.get("items") or []
        count = (items[0].get("statistics") or {}).get("subscriberCount") if items else None
        return int(count) if count is not None else None
    except Exception as exc:
        logger.debug("subscriber count unavailable: %s", exc)
        return None


def fetch_ypp_numbers(
    *, channel_id: str | None = None, today: date | None = None
) -> dict[str, Any] | None:
    """YouTube's own YPP numbers with ads left out (#954), or None.

    Shorts views over the last 90 days and long-form watch hours over the last 365 - the two
    paths' measures - from two channel queries by traffic source and content type, plus the
    subscriber count. Paid views and paid watch time are excluded, as YouTube excludes them.
    """
    if not _analytics_enabled():
        return None
    cid = resolve_channel_id(channel_id)
    service = get_youtube_analytics_service(cid)
    if not service:
        return None
    end = today or date.today()
    views = _by_source_and_type(
        service, (end - timedelta(days=90)).isoformat(), end.isoformat(), "views"
    )
    minutes = _by_source_and_type(
        service, (end - timedelta(days=365)).isoformat(), end.isoformat(), "estimatedMinutesWatched"
    )
    if views is None and minutes is None:
        return None
    out: dict[str, Any] = {"as_of": end.isoformat()}
    if views is not None:
        shorts = {k: v for k, v in views.items() if k[1] == "SHORTS"}
        out["shorts_views_90d"] = int(sum(v for k, v in shorts.items() if k[0] not in PAID_SOURCES))
        out["shorts_paid_90d"] = int(sum(v for k, v in shorts.items() if k[0] in PAID_SOURCES))
    if minutes is not None:
        organic = sum(
            v for k, v in minutes.items() if k[1] in LONG_FORM_TYPES and k[0] not in PAID_SOURCES
        )
        out["long_hours_365d"] = round(organic / 60.0, 1)
    out["subscribers"] = _subscriber_count(cid)
    return out


def fetch_channel_uploads(
    *, channel_id: str | None = None, max_results: int = 50
) -> list[dict[str, str]] | None:
    """The channel's own uploads, newest first (#941: uploads made outside Content OS
    count toward the week). 2 Data API units; None when it cannot be read."""
    if not _analytics_enabled():
        return None
    service = get_youtube_service(resolve_channel_id(channel_id))
    if not service:
        return None
    try:
        from youtube.channel_uploads import uploads_playlist_items

        return uploads_playlist_items(service, max_results=max_results)
    except Exception as exc:
        logger.debug("channel uploads unavailable: %s", exc)
        return None


def fetch_lifetime_views(video_ids: list[str], *, channel_id: str | None = None) -> dict[str, int]:
    """{video_id: lifetime views} from `videos.list` statistics - 1 unit per 50 ids (#940).

    The headline sync asks Analytics for the last 28 days, so a stored `views` is a
    window, not what the video has to date.
    """
    if not _analytics_enabled() or not video_ids:
        return {}
    service = get_youtube_service(resolve_channel_id(channel_id))
    if not service:
        return {}
    out: dict[str, int] = {}
    ids = list(dict.fromkeys(v for v in video_ids if v))
    for start in range(0, len(ids), 50):
        chunk = ids[start : start + 50]
        try:
            resp = (
                service.videos()
                .list(
                    part="statistics", id=",".join(chunk), fields="items(id,statistics/viewCount)"
                )
                .execute()
            )
        except Exception as exc:
            logger.debug("lifetime views unavailable: %s", exc)
            break
        for item in resp.get("items") or []:
            try:
                out[str(item["id"])] = int((item.get("statistics") or {}).get("viewCount") or 0)
            except (KeyError, TypeError, ValueError):
                continue
    return out


def store_lifetime_views(rows: list[Any], counts: dict[str, int]) -> int:
    """Write each row's `lifetime_views` into its metrics; the rows updated."""
    repo = get_publish_log_repository()
    stamped = datetime.now(timezone.utc).isoformat()
    updated = 0
    for row in rows:
        views = counts.get(str(getattr(row, "youtube_video_id", "") or ""))
        if views is None:
            continue
        try:
            metrics = json.loads(row.metrics_json or "{}")
        except (TypeError, ValueError):
            metrics = {}
        if not isinstance(metrics, dict):
            metrics = {}
        metrics["lifetime_views"] = views
        metrics["lifetime_views_at"] = stamped
        repo.update(row.id, {"metrics_json": json.dumps(metrics)})
        updated += 1
    return updated


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
        "engaged_basis": "avg_view_pct",  # #920: average view % / 100, not likes/views
        "estimated_minutes_watched": float(parsed.get("estimatedMinutesWatched", 0) or 0),
        "period_start": start_date,
        "period_end": end_date,
    }
    curve = _fetch_retention_curve(youtube_video_id, service, start_date, end_date)
    if curve:
        result["retention_curve"] = curve
    engaged = _fetch_engaged_views(youtube_video_id, service, start_date, end_date)
    if engaged is not None:
        result["engaged_views"] = engaged  # #951
        if views > 0:
            result["stayed_share"] = round(min(1.0, engaged / views), 4)
    revenue = _fetch_estimated_revenue(youtube_video_id, service, start_date, end_date)
    if revenue is not None:
        result["estimated_revenue_usd"] = revenue
    daily = _fetch_views_by_day(youtube_video_id, service, start_date, end_date)
    if daily is not None:
        if daily:
            result["daily_views"] = daily  # #563
        result["views_since"], result["views_until"] = start_date, end_date
    sources = _fetch_views_by_source_day(youtube_video_id, service, start_date, end_date)
    if sources is not None:
        paid_daily, by_source = sources
        result["daily_paid_views"] = paid_daily  # #954: [] = asked, none paid
        result["paid_since"] = start_date
        paid_total = sum(int(v) for _day, v in paid_daily)
        result["paid_views"] = paid_total
        result["views_by_source"] = by_source
        if paid_total > 0:  # #957: an unboosted video's two rates are the same
            watch = _fetch_watch_by_source(youtube_video_id, service, start_date, end_date)
            organic = organic_engaged_rate(avg_pct, watch) if watch else None
            if organic is not None:
                result["organic_engaged_rate"] = organic
    return result


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _snapshot_bucket(published_at: datetime | None, now: datetime) -> str | None:
    if published_at is None:
        return None
    published = published_at if published_at.tzinfo else published_at.replace(tzinfo=timezone.utc)
    current = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    age = (current - published).total_seconds()
    if age <= 36 * 3600:
        return "24h"
    if age <= 8 * 24 * 3600:
        return "7d"
    return None


def merge_metric_snapshots(
    existing: dict[str, Any],
    metrics: dict[str, Any],
    *,
    published_at: datetime | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Keep the first 24h/7d snapshots; later syncs only update the live totals.

    #958: the stored metrics are the base - lifetime views (#940), reach (#951), the
    first-day verdict (#49) - and the fresh fetch overwrites only the keys it returned.
    """
    current = now or _now()
    old = existing if isinstance(existing, dict) else {}
    merged = {**old, **metrics}
    snaps: dict[str, Any] = {}
    prev = old.get("snapshots")
    if isinstance(prev, dict):
        snaps = dict(prev)
    bucket = _snapshot_bucket(published_at, current)
    if bucket and bucket not in snaps:
        snaps[bucket] = {
            "views": metrics.get("views"),
            "paid_views": metrics.get("paid_views"),  # #49: first-day views are organic
            "engaged_rate": metrics.get("engaged_rate"),
            "likes": metrics.get("likes"),
            "captured_at": current.isoformat(),
        }
    merged["snapshots"] = snaps
    from analytics.view_curve import merge_view_curve

    return merge_view_curve(existing, merged, published_at)  # #563


def _existing_publish_row(
    repo: Any, *, log_id: int | None, channel_id: str, content_run_id: int
) -> Any:
    if log_id:
        try:
            for candidate in repo.list_uploaded_for_channel(channel_id):
                if candidate.id == log_id:
                    return candidate
        except Exception as exc:
            logger.debug("existing publish row unavailable: %s", exc)
    try:
        return repo.find_by_idempotency(f"run:{channel_id}:{content_run_id}")
    except Exception as exc:
        logger.debug("publish idempotency lookup skipped: %s", exc)
        return None


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

    # #954: what the learning memory keeps is organic - a boosted video is not a winner.
    views = max(0, int(metrics.get("views", 0)) - int(metrics.get("paid_views", 0) or 0))
    engaged_rate = float(metrics.get("engaged_rate", 0.0))
    domain = infer_domain(topic or title, channel_id)

    repo = get_publish_log_repository()
    row = _existing_publish_row(
        repo,
        log_id=publish_log_id,
        channel_id=channel_id,
        content_run_id=content_run_id,
    )
    log_id = publish_log_id or (row.id if row is not None else None)
    existing: dict[str, Any] = {}
    published_at = None
    if row is not None:
        log_id = row.id
        try:
            loaded = json.loads(row.metrics_json or "{}")
            existing = loaded if isinstance(loaded, dict) else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            existing = {}
        published_at = row.published_at
    had_first_day = "24h" in (existing.get("snapshots") or {})
    metrics = merge_metric_snapshots(existing, metrics, published_at=published_at)
    if log_id and not had_first_day:  # #49: judged when this sync captures the 24h snapshot
        from analytics import first_day

        first_day.check(
            channel_id, metrics, log_id=log_id, run_id=content_run_id,
            video_id=youtube_video_id, title=title or topic,
        )  # fmt: skip
        try:
            from core.engagement_predictor import surprise_residual
            from core.predictions.ledger import frozen_engagement

            # #559: the prediction frozen at publish (fitted without this video), not a
            # refit that includes its own outcome and moves with every later video.
            pred = frozen_engagement(content_run_id, channel_id)
            if pred is not None and pred.get("rate") is not None:
                metrics["predicted_engaged_rate"] = float(pred["rate"])
                residual = surprise_residual(engaged_rate, float(pred["rate"]))
                if residual is not None:
                    metrics["surprise"] = residual
        except Exception as exc:
            logger.debug("engagement surprise skipped: %s", exc)
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
