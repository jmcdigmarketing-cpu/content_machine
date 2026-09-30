"""Tag and hashtag performance (#428): which ones move with engagement.

Every upload carries YouTube tags (`content_runs.tags_json`) and #hashtags in its
description; nothing ever joined them to outcomes. This ranks them the way title
patterns are ranked (#566): each tag's engaged rate shrunk toward the channel mean
(`core/recommender_confidence.shrunk_mean`), by lift over the channel, three videos
minimum. A tag on nearly every video cannot be told apart from the channel average, so
it is named, not ranked. Report-only: nothing chooses tags from this yet.
"""

from __future__ import annotations

import json
import re
from typing import Any

from core.logging import get_logger

logger = get_logger("analytics.tag_performance")

_HASHTAG = re.compile(r"#[A-Za-z0-9_]+")
_MIN_VIDEOS = 3
_UNIVERSAL_SHARE = 0.8


def run_tags(run: Any) -> set[str]:
    """A run's YouTube tags and description hashtags, lowercased ("#tag" keeps its #)."""
    tags: set[str] = set()
    try:
        raw = json.loads(getattr(run, "tags_json", None) or "[]")
    except (TypeError, ValueError):
        raw = []
    for tag in raw if isinstance(raw, list) else []:
        text = str(tag).strip().lower()
        if text:
            tags.add(text)
    for tag in _HASHTAG.findall(getattr(run, "description", "") or ""):
        tags.add(tag.lower())
    return tags


def _measured(channel_id: str) -> list[tuple[set[str], float]]:
    from core.engagement import engaged_rate
    from storage.repositories.content_runs import get_content_run_repository
    from storage.repositories.publish_log import get_publish_log_repository

    rates: dict[int, float] = {}
    for log in get_publish_log_repository().list_timed_outcomes(channel_id) or []:
        rate = engaged_rate(log.metrics_json)
        if rate is not None and log.content_run_id:
            rates[int(log.content_run_id)] = float(rate)
    out = []
    for run in get_content_run_repository().list_for_channel(channel_id) or []:
        rate = rates.get(int(run.id))
        tags = run_tags(run)
        if rate is not None and tags:
            out.append((tags, rate))
    return out


def universal_tags(channel_id: str) -> set[str]:
    """Tags on at least 80% of measured videos - no contrast to measure against."""
    measured = _measured(channel_id)
    if not measured:
        return set()
    counts: dict[str, int] = {}
    for tags, _rate in measured:
        for tag in tags:
            counts[tag] = counts.get(tag, 0) + 1
    return {t for t, n in counts.items() if n >= _UNIVERSAL_SHARE * len(measured)}


def tag_lifts(channel_id: str, *, min_videos: int = _MIN_VIDEOS) -> list[dict[str, Any]]:
    """[{tag, avg, n, lift, baseline}] best-first by shrunk lift over the channel."""
    from core.recommender_confidence import shrunk_mean

    measured = _measured(channel_id)
    if not measured:
        return []
    baseline = sum(rate for _tags, rate in measured) / len(measured)
    skip = universal_tags(channel_id)
    by_tag: dict[str, list[float]] = {}
    for tags, rate in measured:
        for tag in tags - skip:
            by_tag.setdefault(tag, []).append(rate)
    rows = [
        {
            "tag": tag,
            "avg": sum(v) / len(v),
            "n": len(v),
            "lift": shrunk_mean(v, baseline) - baseline,
            "baseline": baseline,
        }
        for tag, v in by_tag.items()
        if len(v) >= min_videos
    ]
    rows.sort(key=lambda r: (r["lift"], r["tag"]), reverse=True)
    return rows


def report_lines(channel_id: str, *, limit: int = 12) -> list[str]:
    """`ops tag-report`."""
    rows = tag_lifts(channel_id)
    lines = [f"Tag performance (#428) - {channel_id}"]
    if not rows:
        lines.append(f"  collecting: no tag on {_MIN_VIDEOS}+ measured videos yet")
    else:
        lines.append(f"  channel average {rows[0]['baseline']:.0%}; best and worst by lift:")
        shown = rows if len(rows) <= limit else rows[: limit // 2] + rows[-(limit // 2) :]
        for r in shown:
            lines.append(
                f"    {r['lift'] * 100:+5.1f}pp vs channel  {r['tag']:<24} "
                f"(raw {r['avg']:.0%}, n={r['n']})"
            )
    universal = sorted(universal_tags(channel_id))
    if universal:
        lines.append("  on nearly every video (no signal): " + ", ".join(universal))
    return lines
