"""Per-platform domain, length and post hour (#1196).

Samples are the measured rows in the platform metrics store. Under
``MODERATE_SAMPLES`` (4) the line names YouTube and the post time stays
YouTube's. At four, the hour with the best shrunk mean of views is the one
``send_due`` schedules.
"""

from __future__ import annotations

from typing import Any

from core.recommender_confidence import MODERATE_SAMPLES, shrunk_mean

_LABEL = {"tiktok": "TikTok", "instagram": "Instagram"}


def _measured(channel_id: str, platform: str) -> list[dict[str, Any]]:
    from publishing.platform_metrics import load

    rows = load(channel_id).get("rows") or {}
    if not isinstance(rows, dict):
        return []
    out: list[dict[str, Any]] = []
    for platforms in rows.values():
        if not isinstance(platforms, dict):
            continue
        row = platforms.get(platform)
        if isinstance(row, dict) and row.get("measured") and row.get("views") is not None:
            out.append(row)
    return out


def _best(rows: list[dict[str, Any]], field: str) -> Any:
    grouped: dict[Any, list[float]] = {}
    for row in rows:
        bucket = row.get(field)
        if bucket is None:
            continue
        grouped.setdefault(bucket, []).append(float(row["views"]))
    if not grouped:
        return None
    flat = [value for values in grouped.values() for value in values]
    prior = sum(flat) / len(flat)
    return max(grouped, key=lambda bucket: shrunk_mean(grouped[bucket], prior))


def hour_choice(channel_id: str, platform: str) -> tuple[int | None, str]:
    """(UTC hour, note). The hour is None while YouTube is the fallback."""
    rows = [row for row in _measured(channel_id, platform) if row.get("hour") is not None]
    label = _LABEL.get(platform, platform)
    if len(rows) < MODERATE_SAMPLES:
        return None, (f"{label} uses YouTube's hour ({len(rows)} samples, need {MODERATE_SAMPLES})")
    hour = int(_best(rows, "hour"))
    return hour, f"{label}'s hour {hour:02d}:00 ({len(rows)} samples)"


def learning_line(channel_id: str, platform: str) -> str:
    """Domain, length and hour for one feed. Empty when that feed has no rows."""
    rows = _measured(channel_id, platform)
    if not rows:
        return ""
    label = _LABEL.get(platform, platform)
    if len(rows) < MODERATE_SAMPLES:
        return (
            f"{label} uses YouTube's hour, domain and length "
            f"({len(rows)} samples, need {MODERATE_SAMPLES})"
        )
    return (
        f"{label}'s own picks ({len(rows)} samples): hour {_best(rows, 'hour')}, "
        f"domain {_best(rows, 'domain')}, length {_best(rows, 'length')}"
    )
