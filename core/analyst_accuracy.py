"""
Self-measurement scaffold — flagged opportunities vs outcomes.

Volume-gated: needs published runs with analytics before hit-rate is meaningful.
"""

from __future__ import annotations

import json
from typing import Any

from config.channels import resolve_channel_id

_FLAG_THRESHOLD = float(__import__("os").getenv("ANALYST_FLAG_THRESHOLD", "60"))


def build_accuracy_report(channel_id: str | None = None) -> dict[str, Any]:
    """
    Compare high-score content_runs to publish_log metrics when available.
    """
    channel_id = resolve_channel_id(channel_id)
    from storage.repositories.content_runs import get_content_run_repository
    from storage.repositories.publish_log import get_publish_log_repository

    runs = get_content_run_repository().list_for_channel(channel_id)
    publish_repo = get_publish_log_repository()
    uploads = publish_repo.list_uploaded_for_channel(channel_id)
    metrics_by_run: dict[int, dict[str, Any]] = {}
    for log in uploads:
        metrics = _parse_metrics(log)
        views = metrics.get("views") or metrics.get("viewCount")
        if views is not None:
            metrics_by_run[int(log.content_run_id)] = {
                "views": int(views),
                "youtube_video_id": log.youtube_video_id,
            }

    flagged: list[dict] = []
    with_outcomes: list[dict] = []

    for run in runs:
        score = float(run.composite_score or 0)
        if score < _FLAG_THRESHOLD:
            continue
        flagged.append(
            {
                "run_id": run.id,
                "topic": run.selected_topic or run.input_topic,
                "composite_score": score,
                "status": run.status,
            }
        )

        outcome = metrics_by_run.get(run.id)
        if not outcome:
            continue
        with_outcomes.append(
            {
                "run_id": run.id,
                "topic": run.selected_topic,
                "composite_score": score,
                "views": outcome["views"],
                "youtube_video_id": outcome.get("youtube_video_id", ""),
            }
        )

    n_flagged = len(flagged)
    n_outcomes = len(with_outcomes)

    if n_outcomes < 5:
        return {
            "status": "volume_gated",
            "flagged_opportunities": n_flagged,
            "runs_with_metrics": n_outcomes,
            "min_runs_required": 5,
            "summary": (
                f"Hit-rate backtest needs ≥5 published runs with analytics "
                f"(have {n_outcomes}). Flagged {n_flagged} opportunities "
                f"at score ≥{_FLAG_THRESHOLD}."
            ),
            "top_flagged": flagged[:8],
        }

    avg_views = sum(r["views"] for r in with_outcomes) / n_outcomes
    hits = [r for r in with_outcomes if r["views"] >= avg_views]
    hit_rate = len(hits) / n_outcomes

    return {
        "status": "ok",
        "flagged_opportunities": n_flagged,
        "runs_with_metrics": n_outcomes,
        "hit_rate": round(hit_rate, 3),
        "avg_views": round(avg_views, 1),
        "score_threshold": _FLAG_THRESHOLD,
        "summary": (
            f"Of {n_outcomes} flagged publishes, {len(hits)} met or beat "
            f"channel average views ({avg_views:.0f}) — hit rate {hit_rate:.0%}."
        ),
        "sample_outcomes": with_outcomes[:10],
    }


def _parse_metrics(log: Any) -> dict[str, Any]:
    raw = getattr(log, "metrics_json", None) or "{}"
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}
