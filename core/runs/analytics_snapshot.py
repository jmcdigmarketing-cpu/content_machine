"""What the recommenders read at each run, kept so history cannot be rewritten (#570).

A sync overwrites a video's live totals and a code change re-derives every stored
number (wave 50 changed what `engaged_rate` means for some rows), so nothing showed
what a run's recommendations were made from. `save` (called by
`core/run_trace.write_run_trace`, beside the signal snapshot) writes
`data/traces/<run>.analytics.json`: each timed outcome's raw metrics and the engaged
rate the code of the day derived from them. `diff_lines` compares it with now and
says, per video, whether the data moved ("data changed") or only the reader ("code
changed"). `RUN_ANALYTICS_SNAPSHOT=false` turns the write off.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from core.logging import get_logger

logger = get_logger("core.runs.analytics_snapshot")

_RAW_KEYS = (
    "views",
    "likes",
    "comments",
    "engaged_rate",
    "engaged_basis",
    "average_view_percentage",
    "avg_view_pct",
    "subscribers_gained",
    "domain",
)
_TOLERANCE = 1e-6


def enabled() -> bool:
    raw = (os.getenv("RUN_ANALYTICS_SNAPSHOT") or "").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _path(run_id: int) -> str:
    from core import run_trace

    return os.path.join(run_trace.TRACES_DIR, f"{int(run_id)}.analytics.json")


def _rows(channel_id: str) -> list[dict[str, Any]]:
    """Every timed outcome as the recommenders read it today."""
    from core import engagement
    from storage.repositories.publish_log import get_publish_log_repository, is_seeded

    out = []
    for log in get_publish_log_repository().list_timed_outcomes(channel_id) or []:
        try:
            metrics = json.loads(log.metrics_json or "{}")
        except (TypeError, ValueError):
            metrics = {}
        if not isinstance(metrics, dict):
            metrics = {}
        out.append(
            {
                "video_id": log.youtube_video_id or f"log{log.id}",
                "run_id": log.content_run_id,
                "published_at": log.published_at.isoformat() if log.published_at else None,
                "seeded": is_seeded(log),
                "raw": {k: metrics[k] for k in _RAW_KEYS if k in metrics},
                "engaged_rate": engagement.engaged_rate(log.metrics_json),
            }
        )
    return out


def save(run_id: int | None, channel_id: str) -> str | None:
    """Write the run's analytics snapshot; its path, or None. Never raises."""
    if not run_id or not enabled():
        return None
    try:
        path = _path(run_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        body = {"run_id": int(run_id), "channel_id": channel_id, "at": time.time()}
        # #938: which outcome the recommenders ranked on when this run was made.
        from core.success.target import target

        body["target"] = target()
        body["rows"] = _rows(channel_id)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(body, handle, indent=1, default=str)
        return path
    except Exception as exc:
        logger.debug("analytics snapshot skipped for run %s: %s", run_id, exc)
        return None


def load(run_id: int) -> dict[str, Any] | None:
    try:
        with open(_path(run_id), encoding="utf-8") as handle:
            body = json.load(handle)
    except (OSError, ValueError):
        return None
    return body if isinstance(body, dict) else None


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def _moved(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is not b
    return abs(float(a) - float(b)) > _TOLERANCE


def diff_lines(run_id: int) -> list[str]:
    """`ops analytics-diff <run>`: what moved between the run and now, and why."""
    then = load(run_id)
    if then is None:
        return [f"No analytics snapshot for run {run_id} (written from wave 52 on)."]
    channel = str(then.get("channel_id") or "")
    before = {r["video_id"]: r for r in then.get("rows") or [] if isinstance(r, dict)}
    now = {r["video_id"]: r for r in _rows(channel)}
    lines = [f"Analytics since run {run_id} ({channel}, {len(before)} measured video(s) then):"]
    from core.success.target import label, target

    then_target, now_target = str(then.get("target") or "engaged"), target()
    if then_target != now_target:
        lines.append(
            f"  recommenders' target: {label(then_target)} -> {label(now_target)} "
            "(RECOMMEND_TARGET) - every recommendation can move"
        )
    changed = 0
    for vid in sorted(set(before) & set(now)):
        old, new = before[vid], now[vid]
        if not _moved(old.get("engaged_rate"), new.get("engaged_rate")):
            continue
        changed += 1
        why = "data changed" if old.get("raw") != new.get("raw") else "code changed"
        lines.append(
            f"  {vid}: {why} - engaged {_pct(old.get('engaged_rate'))} -> "
            f"{_pct(new.get('engaged_rate'))}"
        )
    added = sorted(set(now) - set(before))
    gone = sorted(set(before) - set(now))
    if added:
        lines.append(f"  {len(added)} video(s) measured since: {', '.join(added[:8])}")
    if gone:
        lines.append(f"  {len(gone)} video(s) no longer read: {', '.join(gone[:8])}")
    if not (changed or added or gone):
        lines.append(f"  unchanged since run {run_id}: the recommenders read the same history.")
    return lines
