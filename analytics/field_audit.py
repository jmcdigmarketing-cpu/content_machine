"""#1480 (S18): each week, the fields health and the learning read, against what was written.

Health read RED on 10-16 on a number nobody stored, and the metrics sync froze every video's
numbers at its first day from 10-05 to 10-22 (#1542) while every test passed - `test_health_writers`
(#1473) now proves each writer and reader agree on synthetic stores. This reads the real ones:
for the week's runs and the videos under 28 days, how many carry each field a reader needs, and
whether a video's numbers were synced in the last three days.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("analytics.field_audit")

# (store, field - dotted inside the JSON, the module that reads it, what reads it); "rendered" is
# the features of a run with a video. A test holds
# each field's last key in its reader's source, so a reader that stops reading it fails CI.
FIELDS: tuple[tuple[str, str, str, str], ...] = (
    ("metrics", "views", "analytics/growth.py", "growth and the YPP pace"),
    ("metrics", "engaged_rate", "core/engagement.py", "engagement health and the best bet"),
    ("metrics", "retention_curve", "core/retention.py", "drop-off and the first 3 seconds"),
    ("metrics", "stayed_share", "analytics/packaging.py", "the share who stayed"),
    ("metrics", "subscribers_gained", "core/engagement.py", "follow-ups for a video that brought subscribers"),
    ("features", "domain", "analytics/weekly_report.py", "the weekly winners"),
    ("features", "angle", "analytics/weekly_report.py", "the weekly winners"),
    ("features", "title_structure", "analytics/weekly_report.py", "the weekly winners"),
    ("features", "cost", "core/channel_health.py", "cost health"),
    ("rendered", "technical_qc.video_duration", "core/channel_health.py", "the length band"),
    ("features", "claim_verification", "analytics/weekly_report.py", "the weekly claim holds"),
    ("features", "entity_research", "video/week_compile.py", "the compilation's title"),
    ("quality", "hook_score", "core/channel_health.py", "engagement's hook read"),
)  # fmt: skip

_THIN = 0.8  # a field on fewer than 80% of the rows that should carry it is named
_STALE_DAYS = 3
_RECENT_DAYS = 28


def _load(raw: Any) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _has(data: dict[str, Any], dotted: str) -> bool:
    value: Any = data
    for key in dotted.split("."):
        if not isinstance(value, dict) or value.get(key) in (None, "", [], {}):
            return False
        value = value[key]
    return True


def _synced(metrics: dict[str, Any]) -> bool:
    """The Analytics sync read this video - it stores the period it read. The Data API's
    `lifetime_views` alone is not a sync: 8 of 23 rows held only that on 10-23 and were counted
    as videos missing every field."""
    return bool(metrics.get("views_until") or metrics.get("period_end"))


def _aware(when: Any) -> datetime | None:
    if not isinstance(when, datetime):
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def audit_lines(
    runs: list[Any], rows: list[Any], *, now: datetime | None = None, days: int = 7
) -> list[str]:
    """What the weekly report prints: the thin fields, then stale metrics - or that all were
    written. [] when there is nothing of the week to read."""
    moment = now or datetime.now(timezone.utc)
    cutoff = moment - timedelta(days=days)
    week = [r for r in runs if (_aware(getattr(r, "created_at", None)) or cutoff) > cutoff]
    stores: dict[str, list[dict[str, Any]]] = {
        "features": [d for d in (_load(getattr(r, "features_json", None)) for r in week) if d],
        "quality": [d for d in (_load(getattr(r, "quality_json", None)) for r in week) if d],
        "rendered": [
            d
            for d in (
                _load(getattr(r, "features_json", None))
                for r in week
                if getattr(r, "mp4_path", None)
            )
            if d
        ],
    }
    recent: list[tuple[Any, dict[str, Any]]] = []
    never: list[int] = []
    for row in rows:
        when = _aware(getattr(row, "published_at", None))
        metrics = _load(getattr(row, "metrics_json", None))
        # YouTube's numbers lag 2-3 days: a video younger than that has none yet
        lagged = moment - timedelta(days=_STALE_DAYS)
        if when is None or not moment - timedelta(days=_RECENT_DAYS) < when <= lagged:
            continue
        if str(getattr(row, "privacy_status", "") or "").lower() != "public":
            continue
        if _synced(metrics):
            recent.append((row, metrics))
        else:  # #1546: 9 public videos from 10-17 on had never synced - the sign-in had lapsed
            never.append(int(getattr(row, "content_run_id", 0) or 0))
    stores["metrics"] = [m for _row, m in recent]
    if not any(stores.values()) and not never:
        return []
    thin: list[str] = []
    for store, field, _reader, why in FIELDS:
        have = stores[store]
        if not have:
            continue
        n = sum(1 for d in have if _has(d, field))
        if n < _THIN * len(have):
            noun = {"metrics": "videos", "rendered": "rendered runs"}.get(store, "runs")
            thin.append(f"{field} on {n} of {len(have)} {noun} ({why})")
    lines = [
        "Fields read but thinly written this week: " + "; ".join(thin)
        if thin
        else f"Fields health and the learning read: all {len(FIELDS)} written this week"
    ]
    why = curve_gaps(recent)
    if why:
        lines.append(why)
    if never:
        listed = ", ".join(str(r) for r in sorted(never)[:6]) + (", ..." if len(never) > 6 else "")
        noun = "video" if len(never) == 1 else "videos"
        lines.append(
            f"Metrics: {len(never)} public {noun} under {_RECENT_DAYS} days never synced "
            f"(run{'s' if len(never) > 1 else ''} {listed}) - the sync needs the YouTube sign-in"
        )
    stale: list[tuple[int, date]] = []
    for row, metrics in recent:
        try:
            until = date.fromisoformat(str(metrics.get("views_until") or "")[:10])
        except ValueError:
            continue
        if (moment.date() - until).days >= _STALE_DAYS:
            stale.append((int(getattr(row, "content_run_id", 0) or 0), until))
    if stale:
        stale.sort(key=lambda s: s[1])
        run_id, until = stale[0]
        lines.append(
            f"Metrics: {len(stale)} of {len(recent)} videos under {_RECENT_DAYS} days last synced "
            f"{_STALE_DAYS}+ days ago (run {run_id}: {until:%b} {until.day}) - is the sync "
            "running? (#1542)"
        )
    return lines


def _curve_gap(row: Any, metrics: dict[str, Any]) -> str:
    """Why one synced video has no retention curve (#1546)."""
    state = metrics.get("retention_curve_state")
    if isinstance(state, dict) and state.get("error"):
        return "failed"
    if isinstance(state, dict) and state.get("rows") == 0:
        return "YouTube gave no curve"
    when = _aware(getattr(row, "published_at", None))
    try:
        until = date.fromisoformat(str(metrics.get("views_until") or "")[:10])
    except ValueError:
        until = None
    if when is not None and until is not None and (until - when.date()).days <= _STALE_DAYS:
        return f"synced only in its first {_STALE_DAYS} days"  # YouTube's curve lags its views
    return "unknown (synced before the sync said why)"


def curve_gaps(recent: list[tuple[Any, dict[str, Any]]]) -> str:
    """#1546: the videos without a retention curve, by why - "" when every one has one. On
    10-22 it was 8 of 20, and the drop-off and 3-second lines read only the other 12."""
    missing = [(row, m) for row, m in recent if not _has(m, "retention_curve")]
    if not missing:
        return ""
    counts: dict[str, int] = {}
    for row, metrics in missing:
        reason = _curve_gap(row, metrics)
        counts[reason] = counts.get(reason, 0) + 1
    parts = ", ".join(
        f"{n} {reason}" for reason, n in sorted(counts.items(), key=lambda kv: -kv[1])
    )
    return f"retention_curve missing on {len(missing)} of {len(recent)} videos: {parts}"


def field_audit_lines(channel_id: str) -> list[str]:
    """The weekly report's lines from the real stores. Fail-open."""
    try:
        from storage.repositories.content_runs import get_content_run_repository
        from storage.repositories.publish_log import get_publish_log_repository

        runs = get_content_run_repository().list_for_channel(channel_id) or []
        rows = get_publish_log_repository().list_uploaded_for_channel(channel_id) or []
    except Exception as exc:
        logger.debug("field audit skipped: %s", exc)
        return []
    return audit_lines(runs, rows)
