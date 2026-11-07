"""#1691 (B04.20) + #1698 (B05.2), wave 154: which formats and frames earn - ranked weekly.

A run's format is what made it: its pick's source (a countdown, a game's preview, last night's
result, a dated moment, a long video, the fast lane, a "who wins?" debate) or, for a headline, its
angle's intent (news, an explainer, a comparison...). `features["format"]` holds the length preset
("Medium"), not this, so the format is read from what each run already records - every past run is
ranked too. Its frame is the angle it was written in (`features["angle"]`: analysis, news,
preview...). Each line ranks the last `DAYS` days' public Shorts by the median first-week organic
views (`success.target.views_7d`) and gives subscribers and (#1642, wave 155) comments per 1,000.
Printed by the weekly report; `measured_shorts` is what the lane numbers (`success.lanes`) read.
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
    "debate": "debate",
    "long": "long",
    "recap": "long",
    "season": "long",
    "moment": "dated moment",
    "worked": "more of what worked",
    "series": "series",
    "arc": "story arc",
    "analytics": "repeat of a winner",
    "profile": "who is",  # #1686 (wave 156)
    "patch": "patch winners and losers",  # #1688 (wave 157)
    "part2": "part 2",  # #1700 (wave 158)
}
# Wave 157: a run's shape - its story's, whatever menu it came from - is its format.
_SHAPES = {"ranking": "ranking", "stat_shock": "stat-shock", "patch": "patch winners and losers"}


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
    if (features.get("best_bet") or {}).get("part") == 1:  # #1700: a story's first half
        return "part 1"
    if str(features.get("shape") or "") in _SHAPES:
        return _SHAPES[str(features["shape"])]
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


def _number(metrics: dict[str, Any], *keys: str) -> int:
    for key in keys:
        try:
            if metrics.get(key) is not None:
                return int(float(metrics[key]))
        except (TypeError, ValueError):
            continue
    return 0


def measured_shorts(
    channel_id: str,
    *,
    today: date | None = None,
    rows: list[Any] | None = None,
    features: Callable[[int], dict[str, Any]] | None = None,
    days: int = DAYS,
) -> list[dict[str, Any]]:
    """{when, views7, organic, views, subs, comments, stayed, format, frame} for each public Short
    of the last `days` with its first week measured."""
    from core.success.target import views_7d

    day = today or date.today()
    read = features or _features
    if rows is None:
        from storage.repositories.publish_log import get_publish_log_repository, is_seeded

        rows = [r for r in get_publish_log_repository().list_uploaded_for_channel(channel_id)
                or [] if not is_seeded(r)]  # fmt: skip
    since = datetime.combine(day - timedelta(days=days), datetime.min.time(), tzinfo=timezone.utc)
    out: list[dict[str, Any]] = []
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
        total = _number(metrics, "lifetime_views", "views")
        stayed = metrics.get("stayed_share")
        out.append({
            "run_id": int(getattr(row, "content_run_id", 0) or 0),
            "when": when, "views7": int(week), "views": total,
            "organic": max(0, total - _number(metrics, "paid_views")),
            "subs": _number(metrics, "subscribers_gained"),
            "comments": _number(metrics, "comments"),
            "stayed": float(stayed) if isinstance(stayed, (int, float)) else None,
            "format": run_format(feats), "frame": str(feats.get("angle") or "unrecorded"),
        })  # fmt: skip
    return out


def _ranked(groups: dict[str, list[dict[str, Any]]]) -> list[str]:
    parts: list[tuple[float, str]] = []
    for name, rows in groups.items():
        median = statistics.median(r["views7"] for r in rows)
        organic = sum(r["organic"] for r in rows)
        views = sum(r["views"] for r in rows)
        rates = []
        if organic:
            rates.append(
                f"{sum(r['subs'] for r in rows) / organic * 1000:.1f} subscribers per 1,000"
            )
        if views:  # #1642: comments per 1,000 views - a debate's honest question measured
            rates.append(
                f"{sum(r['comments'] for r in rows) / views * 1000:.1f} comments per 1,000"
            )
        rate = "".join(f", {r}" for r in rates)
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
    try:
        shorts = measured_shorts(channel_id, today=today, rows=rows, features=features)
        by_format: dict[str, list[dict[str, Any]]] = {}
        by_frame: dict[str, list[dict[str, Any]]] = {}
        for short in shorts:
            by_format.setdefault(short["format"], []).append(short)
            by_frame.setdefault(short["frame"], []).append(short)
        if not by_format:
            return []
        head = f"the last {DAYS} days' Shorts, median first-week organic views"
        return [f"Formats (#1691, {head}): " + " · ".join(_ranked(by_format)),
                "By frame (#1698): " + " · ".join(_ranked(by_frame))]  # fmt: skip
    except Exception as exc:
        logger.debug("format lines skipped: %s", exc)
        return []


def length_trial_lines(
    channel_id: str,
    *,
    today: date | None = None,
    rows: list[Any] | None = None,
    features: Callable[[int], dict[str, Any]] | None = None,
    arms: dict[int, str] | None = None,
) -> list[str]:
    """#1637 (wave 157): the length-by-format trial's arms on first-week organic views and stayed
    share, or [] before a draft of each arm is measured. `arms` is run id -> arm."""
    try:
        if arms is None:
            from core.batch_generation import LENGTH_LEVER
            from core.experiments import _assignments

            arms = {int(a.get("run_id") or 0): str(a.get("arm") or "")
                    for a in _assignments(channel_id, LENGTH_LEVER)}  # fmt: skip
        if not arms:
            return []
        by_arm: dict[str, list[dict[str, Any]]] = {}
        for short in measured_shorts(channel_id, today=today, rows=rows, features=features):
            arm = arms.get(int(short.get("run_id") or 0))
            if arm:
                by_arm.setdefault(arm, []).append(short)
        if len(by_arm) < 2:
            return []
        parts = []
        for arm in sorted(by_arm):
            shorts = by_arm[arm]
            stayed = [s["stayed"] for s in shorts if s.get("stayed") is not None]
            share = f", stayed {statistics.median(stayed):.0%}" if stayed else ""
            parts.append(f"{arm} {statistics.median(s['views7'] for s in shorts):g} (n={len(shorts)}"
                         f"{share})")  # fmt: skip
        return ["Length by format (#1637, news 30-45 s, previews 45-60 s; median first-week organic "
                "views): " + " · ".join(parts)]  # fmt: skip
    except Exception as exc:
        logger.debug("length trial lines skipped: %s", exc)
        return []
