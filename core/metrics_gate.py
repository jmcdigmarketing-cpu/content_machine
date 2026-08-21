"""Optional 'yesterday has metrics' gate (candidate 62).

Opt-in (``METRICS_BEFORE_NEXT`` empty/0/off = disabled) so a leftover env
cannot abort the unit suite. When on, a new unattended video does not start
until yesterday's uploads have views in ``publish_log.metrics_json`` — otherwise
the learning loop drafts another unmeasured video. No yesterday upload = pass.
Store read failures fail-open.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("core.metrics_gate")


def gate_enabled() -> bool:
    return os.getenv("METRICS_BEFORE_NEXT", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _has_metrics(metrics_json: str) -> bool:
    try:
        data = json.loads(metrics_json or "{}")
    except (TypeError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    views = data.get("views")
    try:
        if views is not None and float(views) > 0:
            return True
    except (TypeError, ValueError):
        pass
    rate = data.get("engaged_rate")
    try:
        if rate is not None and float(rate) > 0:
            return True
    except (TypeError, ValueError):
        pass
    return False


def _published_on(row: Any, day: date) -> bool:
    published = getattr(row, "published_at", None)
    if published is None:
        return False
    if isinstance(published, datetime):
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        return published.astimezone(timezone.utc).date() == day
    return False


def metrics_gate_reason(
    channel_id: str,
    *,
    today: date | None = None,
    rows: list[Any] | None = None,
) -> str | None:
    """Why the next video should wait, or None when the loop can proceed."""
    if not gate_enabled():
        return None
    day = (today or datetime.now(timezone.utc).date()) - timedelta(days=1)
    if rows is None:
        try:
            from storage.repositories.publish_log import get_publish_log_repository

            rows = get_publish_log_repository().list_uploaded_for_channel(channel_id)
        except Exception as exc:
            logger.debug("metrics-gate publish_log skipped: %s", exc)
            return None
    yesterday = [r for r in (rows or []) if _published_on(r, day)]
    if not yesterday:
        return None
    missing = [r for r in yesterday if not _has_metrics(getattr(r, "metrics_json", "") or "")]
    if not missing:
        return None
    n = len(missing)
    return (
        f"metrics gate: {n} yesterday upload(s) still have no views "
        f"({day.isoformat()}) — sync analytics before the next video"
    )
