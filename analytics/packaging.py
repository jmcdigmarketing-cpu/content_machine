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
        from storage.repositories.publish_log import get_publish_log_repository, is_seeded

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
        title = (row.detail or "").strip() or "(untitled)"
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
