"""
Shared helpers for analytics-driven recommenders.

`engaged_rate` and `safe_infer_domain` were duplicated verbatim across
`core/best_bet.py` and `core/length_recommender.py`; this is the single source
so they can't drift. Behaviour is unchanged from those copies.
"""

from __future__ import annotations

import json
import os
from typing import Any

_LOW_VIEWS_SHOWN = 50


def min_outcome_views() -> int:
    """`MIN_OUTCOME_VIEWS` (default 0 = off): a video with fewer views teaches nothing (#564).

    YouTube cannot tell the owner's views apart; on a near-empty video they decide the
    average view percentage the recommenders learn from.
    """
    try:
        return max(0, int(float(os.getenv("MIN_OUTCOME_VIEWS", "") or 0)))
    except ValueError:
        return 0


def under_view_floor(metrics: dict[str, Any], floor: int | None = None) -> bool:
    """True when the floor is on and the video's known views are below it (unknown: kept)."""
    limit = min_outcome_views() if floor is None else floor
    if limit <= 0 or not isinstance(metrics, dict) or metrics.get("views") is None:
        return False
    try:
        return float(metrics["views"]) < limit
    except (TypeError, ValueError):
        return False


def engaged_rate(metrics_json: str, *, floor: bool = True) -> float | None:
    """Engaged rate from a publish_log metrics blob; None when unknown.

    Prefers an explicit ``engaged_rate``; otherwise derives likes/views. None as well
    for a video under `MIN_OUTCOME_VIEWS` (#564) unless ``floor=False``.
    """
    try:
        m = json.loads(metrics_json or "{}")
        if floor and under_view_floor(m):
            return None
        if "engaged_rate" in m:
            return float(m["engaged_rate"])
        views = float(m.get("views", 0))
        likes = float(m.get("likes", 0))
        if views > 0:
            return likes / views
    except (ValueError, TypeError, json.JSONDecodeError):
        pass
    return None


def low_view_line(channel_id: str) -> str:
    """`ops predictions`: how many measured videos sit under the floor (or 50 when off)."""
    from storage.repositories.publish_log import get_publish_log_repository

    floor = min_outcome_views()
    limit = floor or _LOW_VIEWS_SHOWN
    measured = low = 0
    for log in get_publish_log_repository().list_timed_outcomes(channel_id) or []:
        if engaged_rate(log.metrics_json, floor=False) is None:
            continue
        measured += 1
        try:
            metrics = json.loads(log.metrics_json or "{}")
        except (TypeError, ValueError):
            metrics = {}
        low += int(under_view_floor(metrics, limit))
    head = f"  {low} of {measured} measured video(s) under {limit} views"
    if floor:
        return f"{head} - left out (MIN_OUTCOME_VIEWS={floor})"
    return f"{head} (MIN_OUTCOME_VIEWS off - they count; your own watches weigh most there)"


def subscribers_gained(metrics_json: str) -> int:
    """Subscribers gained from a publish_log metrics blob; 0 when unknown."""
    try:
        m = json.loads(metrics_json or "{}")
        return int(float(m.get("subscribers_gained") or 0))
    except (ValueError, TypeError, json.JSONDecodeError):
        return 0


def safe_infer_domain(topic: str, channel_id: str) -> str:
    """infer_domain with a 'neutral' fallback if topic scoring is unavailable."""
    try:
        from apis.topic_scorer import infer_domain

        return infer_domain(topic, channel_id)
    except Exception:
        return "neutral"
