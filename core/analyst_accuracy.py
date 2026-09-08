"""
Self-measurement scaffold — flagged opportunities vs outcomes.

Volume-gated: needs published runs with analytics before hit-rate is meaningful.
"""

from __future__ import annotations

import json
from typing import Any

from config.channels import resolve_channel_id

_FLAG_THRESHOLD = float(__import__("os").getenv("ANALYST_FLAG_THRESHOLD", "60"))


def drift_line(*, recent_hit_rate: float, older_hit_rate: float) -> str:
    if recent_hit_rate < older_hit_rate - 0.05:
        return f"calibration drift: hit-rate fell {older_hit_rate:.0%} -> {recent_hit_rate:.0%}"
    return ""


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
        # Engaged-rate is the loop's objective (Pillar 2 realignment) — views
        # stay as the fallback outcome for pre-analytics-sync history.
        engaged = metrics.get("engaged_rate")
        if views is not None or engaged is not None:
            metrics_by_run[int(log.content_run_id)] = {
                "views": int(views or 0),
                "engaged_rate": float(engaged) if engaged is not None else None,
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
                "engaged_rate": outcome.get("engaged_rate"),
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

    # Backtest against engaged-rate when enough runs carry it — the metric the
    # learning loop optimizes. Views remain the fallback for legacy history.
    engaged_outcomes = [r for r in with_outcomes if r.get("engaged_rate") is not None]
    if len(engaged_outcomes) >= 5:
        avg_rate = sum(r["engaged_rate"] for r in engaged_outcomes) / len(engaged_outcomes)
        hits = [r for r in engaged_outcomes if r["engaged_rate"] >= avg_rate]
        hit_rate = len(hits) / len(engaged_outcomes)
        result = {
            "status": "ok",
            "metric": "engaged_rate",
            "flagged_opportunities": n_flagged,
            "runs_with_metrics": len(engaged_outcomes),
            "hit_rate": round(hit_rate, 3),
            "avg_engaged_rate": round(avg_rate, 4),
            "score_threshold": _FLAG_THRESHOLD,
            "summary": (
                f"Of {len(engaged_outcomes)} flagged publishes, {len(hits)} met or beat "
                f"channel average engaged-rate ({avg_rate:.1%}) — hit rate {hit_rate:.0%}."
            ),
            "sample_outcomes": engaged_outcomes[:10],
        }
        return _with_drift(result, engaged_outcomes)

    avg_views = sum(r["views"] for r in with_outcomes) / n_outcomes
    hits = [r for r in with_outcomes if r["views"] >= avg_views]
    hit_rate = len(hits) / n_outcomes

    result = {
        "status": "ok",
        "metric": "views",
        "flagged_opportunities": n_flagged,
        "runs_with_metrics": n_outcomes,
        "hit_rate": round(hit_rate, 3),
        "avg_views": round(avg_views, 1),
        "score_threshold": _FLAG_THRESHOLD,
        "summary": (
            f"Of {n_outcomes} flagged publishes, {len(hits)} met or beat "
            f"channel average views ({avg_views:.0f}) — hit rate {hit_rate:.0%}. "
            "(views fallback — engaged-rate not yet synced on 5+ runs)"
        ),
        "sample_outcomes": with_outcomes[:10],
    }
    return _with_drift(result, with_outcomes)


def _window_hit_rate(rows: list[dict], metric: str) -> float:
    if not rows:
        return 0.0
    if metric == "engaged_rate":
        vals = [float(r["engaged_rate"]) for r in rows if r.get("engaged_rate") is not None]
        if not vals:
            return 0.0
        avg = sum(vals) / len(vals)
        return sum(1 for v in vals if v >= avg) / len(vals)
    vals = [float(r.get("views") or 0) for r in rows]
    avg = sum(vals) / len(vals)
    return sum(1 for v in vals if v >= avg) / len(vals)


def _with_drift(result: dict[str, Any], rows: list[dict]) -> dict[str, Any]:
    if len(rows) < 6:
        return result
    mid = len(rows) // 2
    metric = str(result.get("metric") or "views")
    line = drift_line(
        recent_hit_rate=_window_hit_rate(rows[:mid], metric),
        older_hit_rate=_window_hit_rate(rows[mid:], metric),
    )
    if line:
        result["drift"] = line
        result["summary"] = str(result.get("summary") or "") + " " + line
    return result


def _parse_metrics(log: Any) -> dict[str, Any]:
    raw = getattr(log, "metrics_json", None) or "{}"
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}
