"""Packaging: what YouTube reports about a video's title and thumbnail (#951, with #948).

A title and thumbnail decide whether a video is watched once shown. What the sync now keeps:

- Shorts: `stayed` - engaged views / views. Since 2025-03-31 a Shorts view counts every start
  or replay and `engagedViews` keeps the old counting, so this is the share of starts that were
  not swiped away (YouTube Studio's "viewed vs swiped away" is the same idea; the API does not
  expose that figure itself). `feed` - the share of organic views that came from the Shorts
  feed, from the traffic sources (#954).
- Long-form: thumbnail impressions and click-through, from the Reporting API reach report
  (`analytics/reach_report.py`) - the Analytics API has no such metric.
- Both: `search` - the share of organic views from YouTube search.

`ops packaging` lists the recent videos with these, and the thumbnail or title arm a run was
assigned when an experiment was running (`core/experiments`).
"""

from __future__ import annotations

import json
from typing import Any

from core.logging import get_logger

logger = get_logger("analytics.packaging")

_LIMIT = 20


def packaging_figures(metrics: dict[str, Any]) -> dict[str, Any]:
    """{short, stayed?, feed?, search?, impressions?, ctr?} from one video's stored metrics."""
    from analytics.youtube_metrics import PAID_SOURCES

    sources = metrics.get("views_by_source") if isinstance(metrics, dict) else None
    organic: dict[str, int] = {}
    for source, value in (sources or {}).items():
        if source in PAID_SOURCES:
            continue
        try:
            organic[str(source)] = int(float(value))
        except (TypeError, ValueError):
            continue
    total = sum(organic.values())
    out: dict[str, Any] = {"short": organic.get("SHORTS", 0) > 0}
    try:
        views = int(float(metrics.get("views") or 0))
    except (TypeError, ValueError):
        views = 0
    engaged = metrics.get("engaged_views")
    stayed = metrics.get("stayed_share")
    if not isinstance(stayed, (int, float)) and isinstance(engaged, (int, float)) and views > 0:
        stayed = min(1.0, engaged / views)
    # A long-form view was never a bare start, so its engaged share says nothing.
    if isinstance(stayed, (int, float)) and (out["short"] or float(stayed) < 0.995):
        out["stayed"] = round(float(stayed), 4)
        out["short"] = True
    if total > 0:
        out["feed"] = round(organic.get("SHORTS", 0) / total, 4)
        out["search"] = round(organic.get("YT_SEARCH", 0) / total, 4)
    impressions = metrics.get("thumbnail_impressions")
    if isinstance(impressions, (int, float)) and impressions > 0:
        out["impressions"] = int(impressions)
        ctr = metrics.get("thumbnail_ctr")
        if isinstance(ctr, (int, float)):
            out["ctr"] = float(ctr)
    return out


def figure_text(figures: dict[str, Any]) -> str:
    """ "stayed 62% · feed 93%" / "CTR 3.5% of 4,000 impressions" - "" when there is none."""
    parts = []
    if "stayed" in figures:
        parts.append(f"stayed {figures['stayed']:.0%}")
    if figures.get("short") and "feed" in figures:
        parts.append(f"feed {figures['feed']:.0%}")
    if "ctr" in figures:
        parts.append(f"CTR {figures['ctr']:.1%} of {figures['impressions']:,} impressions")
    if figures.get("search"):
        parts.append(f"search {figures['search']:.0%}")
    return " · ".join(parts)


def _arm(run_id: int | None) -> str:
    try:
        from core.experiments import assignment_for_run

        assignment = assignment_for_run(run_id)
    except Exception as exc:
        logger.debug("experiment arm unavailable for %s: %s", run_id, exc)
        return ""
    if not assignment or not assignment.get("arm"):
        return ""
    return f" [{assignment.get('lever')}: {assignment.get('arm')}]"


def packaging_lines(channel_id: str, *, limit: int = _LIMIT) -> list[str]:
    """`ops packaging`: the recent videos with their packaging numbers."""
    try:
        from storage.repositories.publish_log import (
            get_publish_log_repository,
            is_seeded,
            video_title,
        )

        rows = [
            r
            for r in get_publish_log_repository().list_uploaded_for_channel(channel_id)
            if r.youtube_video_id and not is_seeded(r)
        ]
    except Exception as exc:
        logger.debug("publish log unavailable: %s", exc)
        rows = []
    rows.sort(key=lambda r: (str(getattr(r, "published_at", "") or ""), r.id or 0), reverse=True)
    shorts: list[tuple[str, dict[str, Any], str]] = []
    longs: list[tuple[str, dict[str, Any], str]] = []
    for row in rows[:limit]:
        try:
            metrics = json.loads(row.metrics_json or "{}")
        except (TypeError, ValueError):
            continue
        figures = packaging_figures(metrics if isinstance(metrics, dict) else {})
        if not figure_text(figures):
            continue
        title = video_title(row)
        entry = (title, figures, _arm(row.content_run_id))
        (shorts if figures.get("short") else longs).append(entry)
    if not shorts and not longs:
        return [
            f"Packaging - {channel_id}: no packaging numbers yet. Run py -m scripts.ops "
            "sync-metrics; click-through also needs the YouTube Reporting API enabled in "
            "Google Cloud Console (same sign-in)."
        ]
    lines = [f"Packaging - {channel_id} (the last {min(limit, len(rows))} videos)"]
    if shorts:
        lines.append(
            "  Shorts - stayed: starts not swiped away (engaged views / views); feed: organic "
            "views from the Shorts feed"
        )
        lines += [f'    "{t}" {figure_text(f)}{arm}' for t, f, arm in shorts]
        ranked = sorted((e for e in shorts if "stayed" in e[1]), key=lambda e: e[1]["stayed"])
        if len(ranked) >= 2:
            lines.append(
                f'    best stayed: "{ranked[-1][0]}" {ranked[-1][1]["stayed"]:.0%} · '
                f'weakest: "{ranked[0][0]}" {ranked[0][1]["stayed"]:.0%}'
            )
    if longs:
        lines.append(
            "  Long-form - thumbnail impressions and click-through (YouTube Reporting API, "
            "from the day its job exists)"
        )
        lines += [f'    "{t}" {figure_text(f)}{arm}' for t, f, arm in longs]
    return lines


# ---- #1124: the stayed share for videos synced before it existed --------------------------


def _stored(row: Any) -> dict[str, Any]:
    try:
        metrics = json.loads(getattr(row, "metrics_json", None) or "{}")
    except (TypeError, ValueError):
        return {}
    return metrics if isinstance(metrics, dict) else {}


def _views(metrics: dict[str, Any]) -> int:
    try:
        return int(float(metrics.get("views") or 0))
    except (TypeError, ValueError):
        return 0


def needs_stayed(row: Any) -> bool:
    """A real video with views for a stored period and no engaged views beside them.

    Measured 2026-10-10: 5 of 43 videos carried a stayed share. The sync has asked for
    engaged views since #951, but it only revisits young videos (#918), so the 38 synced
    before then were never asked - and every reader of "who stayed" ran on five.
    """
    if not str(getattr(row, "youtube_video_id", "") or "").strip():
        return False
    from storage.repositories.publish_log import is_seeded

    if is_seeded(row):
        return False
    metrics = _stored(row)
    if "engaged_views" in metrics:
        return False
    return (
        _views(metrics) > 0
        and bool(metrics.get("period_start"))
        and bool(metrics.get("period_end"))
    )


def stayed_stale(run: Any) -> bool:
    """A content run whose live video has views and no stayed share."""
    try:
        from publishing.idempotency import idempotency_key
        from storage.repositories.publish_log import get_publish_log_repository

        row = get_publish_log_repository().find_by_idempotency(
            idempotency_key(int(run.id), str(getattr(run, "channel_id", "") or ""))
        )
    except Exception as exc:
        logger.debug("stayed stale check skipped: %s", exc)
        return False
    return row is not None and needs_stayed(row)


def backfill_stayed(channel_id: str, apply: bool, force: bool) -> dict[str, int]:
    """Ask for engaged views over the period each video's stored views cover, so the share
    is of the same starts. Network only with `apply`; `force` is accepted and changes
    nothing - a video that has the number is never asked twice."""
    from analytics import youtube_metrics
    from storage.repositories.publish_log import get_publish_log_repository

    repo = get_publish_log_repository()
    rows = list(repo.list_uploaded_for_channel(channel_id) or [])
    todo = [r for r in rows if needs_stayed(r)]
    updated = 0
    if apply:
        for row in todo:
            metrics = _stored(row)
            engaged = youtube_metrics.fetch_engaged_views(
                row.youtube_video_id,
                channel_id=channel_id,
                start=str(metrics["period_start"]),
                end=str(metrics["period_end"]),
            )
            if engaged is None:
                from youtube.oauth import sign_in_problem

                if sign_in_problem(channel_id):
                    break  # every other video would be refused the same way (#961)
                continue
            metrics["engaged_views"] = int(engaged)
            metrics["stayed_share"] = round(min(1.0, int(engaged) / _views(metrics)), 4)
            repo.update(row.id, {"metrics_json": json.dumps(metrics)})
            updated += 1
    return {"runs": len(rows), "stale": len(todo), "would_update": len(todo), "updated": updated}


# #1413 (S11.7, wave 145): click-through is stored since 11-02 (86 videos). A long video YouTube
# showed 1,000 times that drew under 2% of clicks gets its second cover - a frame 60% into its own
# render instead of 30% - once. The Weeks in Review drew 1.08% and 0% on 279 and 137 impressions.
SWAP_IMPRESSIONS = 1000
SWAP_CTR = 0.02


def cover_swap_candidates(channel_id: str) -> list[dict[str, Any]]:
    """{run_id, video_id, impressions, ctr, title, mp4} for each public long video past
    `SWAP_IMPRESSIONS` under `SWAP_CTR` whose cover was not swapped yet."""
    from publishing.prepublish import _features, _is_long, _run
    from storage.repositories.publish_log import get_publish_log_repository

    out: list[dict[str, Any]] = []
    for row in get_publish_log_repository().list_uploaded_for_channel(channel_id) or []:
        run_id = getattr(row, "content_run_id", None)
        video_id = str(getattr(row, "youtube_video_id", "") or "")
        if not run_id or not video_id or str(row.privacy_status or "").lower() != "public":
            continue
        metrics = _stored(row)
        shown = int(metrics.get("thumbnail_impressions") or 0)
        ctr = metrics.get("thumbnail_ctr")
        if shown < SWAP_IMPRESSIONS or not isinstance(ctr, int | float) or ctr >= SWAP_CTR:
            continue
        run = _run(run_id)
        if not _is_long(run_id) or _features(run).get("cover_swapped_at"):
            continue
        out.append({"run_id": int(run_id), "video_id": video_id, "impressions": shown,
                    "ctr": float(ctr), "title": str(getattr(run, "title", "") or ""),
                    "mp4": str(getattr(run, "mp4_path", "") or "")})  # fmt: skip
    return out


def _second_cover(candidate: dict[str, Any], channel_id: str) -> str:
    import os

    from core.output_paths import channel_output_root
    from core.series.long_form import long_thumbnail

    if not candidate.get("mp4") or not os.path.isfile(candidate["mp4"]):
        return ""
    dest = os.path.join(
        channel_output_root(channel_id), "thumbnails", f"run{candidate['run_id']}-cover2.jpg"
    )
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    return long_thumbnail(candidate["mp4"], candidate["title"], dest, channel_id=channel_id, at=0.6)


def swap_low_ctr_covers(
    channel_id: str,
    *,
    apply: bool = False,
    cover: Any = None,
    upload: Any = None,
) -> list[str]:
    """#1413: one line per long video whose cover is (or would be) swapped. `apply` sets the
    second cover on YouTube (50 units) and records it on the run; COVER_SWAP=false stops it."""
    import os
    from datetime import datetime, timezone

    if os.getenv("COVER_SWAP", "true").strip().lower() in ("0", "false", "no", "off"):
        return []
    lines: list[str] = []
    for found in cover_swap_candidates(channel_id):
        head = (f"Cover swap: run {found['run_id']} - {found['impressions']:,} impressions at "
                f"{found['ctr']:.1%}")  # fmt: skip
        if not apply:
            lines.append(f"{head}; the next metrics sync puts up its second cover")
            continue
        path = (cover or _second_cover)(found, channel_id)
        if not path:
            lines.append(f"{head}; no second cover could be cut")
            continue
        try:
            if upload is None:
                from youtube.oauth import get_youtube_service
                from youtube.thumbnails import set_video_thumbnail

                service = get_youtube_service(channel_id)
                result = set_video_thumbnail(service, found["video_id"], path) if service else None
                ok = getattr(result, "status", "") == "set"
            else:
                ok = bool(upload(found["video_id"], path))
        except Exception as exc:
            logger.warning("cover swap for run %s failed: %s", found["run_id"], exc)
            ok = False
        if not ok:
            lines.append(f"{head}; YouTube did not take the second cover")
            continue
        from core.run_features import merge_features

        merge_features(found["run_id"], {
            "cover_swapped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "cover_swap": {"impressions": found["impressions"], "ctr": found["ctr"],
                           "path": path},
        })  # fmt: skip
        lines.append(f"{head}; its second cover is up")
    return lines
