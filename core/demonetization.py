"""#131 estimatedRevenue cliff vs channel baseline. Missing is not $0."""

from __future__ import annotations

import json

from core.logging import get_logger

logger = get_logger("core.demonetization")


def _revenue(metrics_json: str) -> float | None:
    try:
        data = json.loads(metrics_json or "{}")
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    raw = data.get("estimated_revenue_usd")
    if raw is None:
        raw = data.get("estimatedRevenue")
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def detect_revenue_cliff(channel_id: str) -> str | None:
    """One-liner when the latest measured video is a cliff vs the channel baseline.

    Returns None when revenue is missing (unmeasured — never treat as zero).
    """
    try:
        from storage.repositories.publish_log import get_publish_log_repository

        rows = list(get_publish_log_repository().list_timed_outcomes(channel_id) or [])
    except Exception as exc:
        logger.debug("demonetization skipped: %s", exc)
        return None
    measured: list[tuple[int, float]] = []
    for row in rows:
        value = _revenue(getattr(row, "metrics_json", "") or "")
        if value is None:
            continue
        rid = int(getattr(row, "id", 0) or getattr(row, "content_run_id", 0) or 0)
        measured.append((rid, value))
    if len(measured) < 2:
        return None
    measured.sort(key=lambda item: item[0])
    _latest_id, latest = measured[-1]
    prior = [v for _i, v in measured[:-1]]
    if not prior:
        return None
    baseline = sum(prior) / len(prior)
    if baseline <= 0:
        return None
    if latest >= baseline * 0.35:
        return None
    return (
        "Revenue cliff: latest measured estimatedRevenue is well below "
        f"the channel baseline ({len(prior)} prior video(s))."
    )
