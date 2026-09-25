"""#366 metrics-sync stall is a reliability incident, not silent flat performance."""

from __future__ import annotations


def metrics_sync_incident(
    *,
    uploads: int,
    last_metrics_age_days: float | None,
    stall_days: float = 7.0,
) -> str | None:
    """None when there are no uploads or the last metrics_json is fresh."""
    if uploads <= 0:
        return None
    if last_metrics_age_days is None:
        return f"metrics sync stalled: {uploads} upload(s) with no metrics_json"
    if last_metrics_age_days > stall_days:
        return (
            f"metrics sync stalled: last metrics_json {last_metrics_age_days:.0f}d ago "
            f"(>{stall_days:.0f}d) while {uploads} upload(s) exist"
        )
    return None
