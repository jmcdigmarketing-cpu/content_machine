"""
Shared helpers for analytics-driven recommenders.

`engaged_rate` and `safe_infer_domain` were duplicated verbatim across
`core/best_bet.py` and `core/length_recommender.py`; this is the single source
so they can't drift. Behaviour is unchanged from those copies.
"""

from __future__ import annotations

import json


def engaged_rate(metrics_json: str) -> float | None:
    """Engaged rate from a publish_log metrics blob; None when unknown.

    Prefers an explicit ``engaged_rate``; otherwise derives likes/views.
    """
    try:
        m = json.loads(metrics_json or "{}")
        if "engaged_rate" in m:
            return float(m["engaged_rate"])
        views = float(m.get("views", 0))
        likes = float(m.get("likes", 0))
        if views > 0:
            return likes / views
    except (ValueError, TypeError, json.JSONDecodeError):
        pass
    return None


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
