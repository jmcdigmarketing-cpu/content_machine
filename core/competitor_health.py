"""Competitor-channel health (morning candidate / audit C7).

Dead or unverified YouTube UC ids in ``config/competitors/*.json`` still get
synced. This checker flags empty RSS / empty snapshots. Reliability uses a
snapshot (no extra HTTP). ``ops competitor-health`` may probe RSS; tests pass
a fake ``fetch``. Never writes quota_state.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from config.competitors import (
    competitors_config_path,
    competitors_data_path,
    get_competitor_channels,
)
from core.logging import get_logger

logger = get_logger("core.competitor_health")

_UC = re.compile(r"^UC[\w-]{22}$")
Fetch = Callable[[str], list[dict[str, Any]]]


@dataclass
class CompetitorCheck:
    youtube_channel_id: str
    label: str
    ok: bool
    detail: str = ""


@dataclass
class CompetitorHealth:
    channel_id: str
    checks: list[CompetitorCheck] = field(default_factory=list)
    coverage: list[str] = field(default_factory=list)  # #1063: what the watch is missing

    @property
    def ok(self) -> bool:
        return bool(self.checks) and all(c.ok for c in self.checks)


def _load_snapshot(channel_id: str) -> dict[str, Any]:
    path = competitors_data_path(channel_id)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _videos_by_id(snapshot: dict[str, Any]) -> dict[str, list]:
    out: dict[str, list] = {}
    for row in snapshot.get("competitors") or []:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("youtube_channel_id") or "")
        videos = row.get("recent_videos") or []
        if cid:
            out[cid] = videos if isinstance(videos, list) else []
    return out


WATCH_MIN_COMPETITORS = 3


def watch_coverage_lines(snapshot: dict[str, Any] | None) -> list[str]:
    """#1063: why a competitor outlier watch cannot run on the stored list, or [].

    An outlier is a video ahead of its own channel's median views. That needs several
    channels in the niche and a view count per video; the RSS sync stores neither.
    """
    rows = [r for r in (snapshot or {}).get("competitors") or [] if isinstance(r, dict)]
    if not rows:
        return ["outlier watch: competitors never synced (py -m scripts.ops competitor-sync)"]
    lines: list[str] = []
    if len(rows) < WATCH_MIN_COMPETITORS:
        plural = "s" if len(rows) != 1 else ""
        lines.append(
            f"outlier watch: {len(rows)} competitor{plural} on the list - it needs "
            f"{WATCH_MIN_COMPETITORS} or more in the channel's own niche "
            "(py -m scripts.ops competitors suggest)"
        )
    videos = [v for r in rows for v in r.get("recent_videos") or [] if isinstance(v, dict)]
    if videos and not any(v.get("views") is not None for v in videos):
        lines.append(
            f"outlier watch: no view counts on {len(videos)} stored video(s) - sync again "
            "(py -m scripts.ops competitor-sync --force); the feed carries them since #1120"
        )
    return lines


def inspect_competitors(
    channel_id: str,
    *,
    channels: list[dict[str, str]] | None = None,
    snapshot: dict[str, Any] | None = None,
    fetch: Fetch | None = None,
    missing_snapshot_ok: bool = False,
) -> CompetitorHealth:
    """Flag bad UC ids and empty feeds. ``fetch`` is RSS in ops; omit to use snapshot."""
    comps = channels if channels is not None else get_competitor_channels(channel_id)
    snap = (
        snapshot
        if snapshot is not None
        else ({} if fetch is not None else _load_snapshot(channel_id))
    )
    by_id = _videos_by_id(snap)
    report = CompetitorHealth(channel_id=channel_id)
    if not comps:
        report.checks.append(
            CompetitorCheck(
                "", "(none)", False, f"no config at {competitors_config_path(channel_id)}"
            )
        )
        return report
    for comp in comps:
        cid = str(comp.get("id") or "")
        label = str(comp.get("label") or cid)
        note = str(comp.get("note") or "")
        if not _UC.match(cid):
            report.checks.append(
                CompetitorCheck(cid, label, False, "id is not a UC + 22-char YouTube channel id")
            )
            continue
        videos: list = []
        source = "snapshot"
        if fetch is not None:
            try:
                videos = list(fetch(cid) or [])
                source = "rss"
            except Exception as exc:
                logger.debug("competitor RSS probe skipped for %s: %s", cid, exc)
                report.checks.append(CompetitorCheck(cid, label, False, f"rss probe failed: {exc}"))
                continue
        elif cid in by_id:
            videos = by_id[cid]
        else:
            if missing_snapshot_ok:
                continue
            detail = "no snapshot yet (run competitor-sync or competitor-health)"
            if note:
                detail = f"{detail}; {note}"
            report.checks.append(CompetitorCheck(cid, label, False, detail))
            continue
        if videos:
            report.checks.append(
                CompetitorCheck(cid, label, True, f"{len(videos)} recent via {source}")
            )
            continue
        detail = f"empty {source} (dead or wrong UC id)"
        if note:
            detail = f"{detail}; {note}"
        report.checks.append(CompetitorCheck(cid, label, False, detail))
    return report


def render_report(report: CompetitorHealth) -> str:
    status = "OK" if report.ok else "ISSUES"
    lines = [f"Competitor health — {report.channel_id} [{status}]", "=" * 44]
    for check in report.checks:
        mark = "ok" if check.ok else "FAIL"
        who = check.label or check.youtube_channel_id or "?"
        detail = f" — {check.detail}" if check.detail else ""
        lines.append(f"  [{mark}] {who}{detail}")
    lines.extend(f"  {line}" for line in report.coverage)
    return "\n".join(lines)


def warning_lines(report: CompetitorHealth) -> list[str]:
    return [
        f"competitor '{c.label or c.youtube_channel_id}' {c.detail}"
        for c in report.checks
        if not c.ok
    ]
