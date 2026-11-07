"""#1691 (B04.20) + #1698 (B05.2), wave 154: which formats and frames earn - ranked weekly.

A run's format is what made it: its pick's source (a countdown, a game's preview, last night's
result, a dated moment, a long video, the fast lane) or, for a headline, its angle's intent (news,
an explainer, a comparison...). `features["format"]` holds the length preset ("Medium"), not this,
so the format is read from what each run already records - every past run is ranked too. Its frame
is the angle it was written in (`features["angle"]`: analysis, news, preview...). Each line ranks
the last `DAYS` days' public Shorts by the median first-week organic views
(`success.target.views_7d`) and gives subscribers per 1,000 organic views. Printed by the weekly
report.
"""

from __future__ import annotations

import json
import statistics
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("core.success.formats")

DAYS = 90
_SOURCES = {
    "countdown": "countdown",
    "schedule": "preview",
    "result": "result",
    "long": "long",
    "recap": "long",
    "season": "long",
    "moment": "dated moment",
    "worked": "more of what worked",
    "series": "series",
    "arc": "story arc",
    "analytics": "repeat of a winner",
}


def _picked_source(features: dict[str, Any]) -> str | None:
    """The pick's menu source, "" for a pick with no source, None when nothing was picked."""
    pick = features.get("best_bet") or {}
    rank = pick.get("picked")
    offered = pick.get("offered") or []
    if not isinstance(rank, int) or not 1 <= rank <= len(offered):
        return None
    return str((offered[rank - 1] or {}).get("source") or "")


def run_format(features: dict[str, Any]) -> str:
    """The run's format: "countdown", "preview", "result", "news", "explainer", "own idea"..."""
    if features.get("compilation"):
        return "compilation"
    if features.get("long_form"):
        return "long"
    source = _picked_source(features)
    if source is None:
        return "own idea"
    if source.startswith("fast_"):
        return "fast lane"
    if source in _SOURCES:
        return _SOURCES[source]
    intent = str(features.get("angle_intent") or "")
    return intent if intent and intent != "default" else "headline"


def _features(run_id: int) -> dict[str, Any]:
    try:
        from storage.repositories.content_runs import get_content_run_repository

        run = get_content_run_repository().get(int(run_id))
        data = json.loads(getattr(run, "features_json", "") or "{}") if run else {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _organic_total(metrics: dict[str, Any]) -> int:
    """Lifetime views less paid ones."""
    try:
        total = int(float(metrics.get("lifetime_views") or metrics.get("views") or 0))
        paid = int(float(metrics.get("paid_views") or 0))
    except (TypeError, ValueError):
        return 0
    return max(0, total - paid)


def _ranked(groups: dict[str, list[tuple[int, int, int]]]) -> list[str]:
    parts: list[tuple[float, str]] = []
    for name, rows in groups.items():
        median = statistics.median(r[0] for r in rows)
        organic = sum(r[1] for r in rows)
        subs = sum(r[2] for r in rows)
        rate = f", {subs / organic * 1000:.1f} subscribers per 1,000" if organic else ""
        parts.append((median, f"{name} n={len(rows)} median {median:,.0f}{rate}"))
    return [text for _m, text in sorted(parts, key=lambda p: (-p[0], p[1]))]


def format_lines(
    channel_id: str,
    *,
    today: date | None = None,
    rows: list[Any] | None = None,
    features: Callable[[int], dict[str, Any]] | None = None,
) -> list[str]:
    """Two lines - by format (#1691), by frame (#1698) - or [] with nothing measured."""
    from core.success.target import views_7d

    day = today or date.today()
    read = features or _features
    try:
        if rows is None:
            from storage.repositories.publish_log import get_publish_log_repository, is_seeded

            rows = [r for r in get_publish_log_repository().list_uploaded_for_channel(channel_id)
                    or [] if not is_seeded(r)]  # fmt: skip
        since = datetime.combine(
            day - timedelta(days=DAYS), datetime.min.time(), tzinfo=timezone.utc
        )
        by_format: dict[str, list[tuple[int, int, int]]] = {}
        by_frame: dict[str, list[tuple[int, int, int]]] = {}
        for row in rows:
            when = getattr(row, "published_at", None)
            if not isinstance(when, datetime):
                continue
            when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
            if when < since or str(getattr(row, "privacy_status", "") or "").lower() != "public":
                continue
            try:
                metrics = json.loads(getattr(row, "metrics_json", "") or "{}")
            except (TypeError, ValueError):
                continue
            week = views_7d(metrics, when) if isinstance(metrics, dict) else None
            if week is None:
                continue
            feats = read(int(getattr(row, "content_run_id", 0) or 0))
            if feats.get("long_form") or feats.get("compilation"):
                continue  # Shorts only
            try:
                subs = int(float(metrics.get("subscribers_gained") or 0))
            except (TypeError, ValueError):
                subs = 0
            entry = (int(week), _organic_total(metrics), subs)
            by_format.setdefault(run_format(feats), []).append(entry)
            by_frame.setdefault(str(feats.get("angle") or "unrecorded"), []).append(entry)
        if not by_format:
            return []
        head = f"the last {DAYS} days' Shorts, median first-week organic views"
        return [f"Formats (#1691, {head}): " + " · ".join(_ranked(by_format)),
                "By frame (#1698): " + " · ".join(_ranked(by_frame))]  # fmt: skip
    except Exception as exc:
        logger.debug("format lines skipped: %s", exc)
        return []
