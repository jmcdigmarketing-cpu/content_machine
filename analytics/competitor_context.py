"""
Load competitor snapshots for discovery, variants, and research brief (Phase I).
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from config.competitors import competitors_data_path, get_competitor_channels
from core.logging import get_logger

logger = get_logger("analytics.competitor_context")

DEFAULT_MAX_AGE_HOURS = 24


def load_competitor_snapshot(channel_id: str) -> dict[str, Any]:
    path = competitors_data_path(channel_id)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("Could not read competitor snapshot: %s", exc)
        return {}


def snapshot_age_hours(channel_id: str) -> float | None:
    snap = load_competitor_snapshot(channel_id)
    raw = snap.get("synced_at")
    if not raw:
        return None
    try:
        synced = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if synced.tzinfo is None:
            synced = synced.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - synced
        return delta.total_seconds() / 3600.0
    except ValueError:
        return None


def is_snapshot_stale(channel_id: str, *, max_age_hours: float = DEFAULT_MAX_AGE_HOURS) -> bool:
    age = snapshot_age_hours(channel_id)
    if age is None:
        return True
    return age > max_age_hours


def ensure_competitor_snapshot(
    channel_id: str,
    *,
    max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
    force: bool = False,
) -> dict[str, Any]:
    """Sync competitors if cache missing or stale (daily batch)."""
    if not get_competitor_channels(channel_id):
        return {"skipped": True, "reason": "no competitors configured"}

    if force or is_snapshot_stale(channel_id, max_age_hours=max_age_hours):
        from analytics.competitor_sync import sync_competitors

        logger.info("Refreshing competitor snapshot for %s", channel_id)
        return sync_competitors(channel_id)

    return load_competitor_snapshot(channel_id)


def _topic_tokens(topic: str) -> list[str]:
    words = re.findall(r"[a-z0-9]{3,}", topic.lower())
    stop = {"the", "and", "for", "will", "that", "this", "with", "from", "about", "how"}
    return [w for w in words if w not in stop]


def _parse_published_at(raw: object) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def topic_saturation(
    channel_id: str,
    topic: str,
    *,
    snapshot: dict[str, Any] | None = None,
    now: datetime | None = None,
    window_hours: float = 48.0,
) -> int:
    """How many tracked-competitor videos covered `topic` in the window."""
    snap = snapshot if snapshot is not None else load_competitor_snapshot(channel_id)
    tokens = _topic_tokens(topic)
    if not tokens:
        return 0
    current = now or datetime.now(timezone.utc)
    cutoff = current - timedelta(hours=float(window_hours))
    count = 0
    for comp in snap.get("competitors") or []:
        if not isinstance(comp, dict):
            continue
        for vid in comp.get("recent_videos") or []:
            if not isinstance(vid, dict):
                continue
            title = str(vid.get("title") or "")
            if not any(token in title.lower() for token in tokens):
                continue
            published = _parse_published_at(vid.get("published_at"))
            if published is None or published < cutoff:
                continue
            count += 1
    return count


def list_recent_competitor_titles(
    channel_id: str,
    *,
    topic: str = "",
    limit: int = 12,
) -> list[dict[str, str]]:
    snap = load_competitor_snapshot(channel_id)
    tokens = _topic_tokens(topic) if topic else []
    rows: list[dict[str, str]] = []

    for comp in snap.get("competitors") or []:
        if not isinstance(comp, dict):
            continue
        label = str(comp.get("label", ""))
        for vid in comp.get("recent_videos") or []:
            if not isinstance(vid, dict):
                continue
            title = str(vid.get("title", "")).strip()
            if not title:
                continue
            if tokens and not any(t in title.lower() for t in tokens):
                continue
            rows.append(
                {
                    "title": title,
                    "channel": label,
                    "published_at": str(vid.get("published_at", "")),
                }
            )

    if not rows and not tokens:
        for comp in snap.get("competitors") or []:
            if not isinstance(comp, dict):
                continue
            label = str(comp.get("label", ""))
            for vid in (comp.get("recent_videos") or [])[:4]:
                if isinstance(vid, dict) and vid.get("title"):
                    rows.append(
                        {
                            "title": str(vid["title"]),
                            "channel": label,
                            "published_at": str(vid.get("published_at", "")),
                        }
                    )

    return rows[:limit]


def get_competitor_prompt_block(channel_id: str, topic: str = "") -> str:
    snap = load_competitor_snapshot(channel_id)
    if not snap.get("competitors"):
        return ""

    lines = ["COMPETITOR CHANNEL PULSE (what is working in-niche now):"]
    age = snapshot_age_hours(channel_id)
    if age is not None:
        lines.append(f"(snapshot {age:.0f}h old)")

    titles = list_recent_competitor_titles(channel_id, topic=topic, limit=10)
    if not titles:
        titles = list_recent_competitor_titles(channel_id, topic="", limit=8)

    if topic:
        covered = topic_saturation(channel_id, topic, snapshot=snap)
        if covered:
            noun = "competitor" if covered == 1 else "competitors"
            lines.append(f"{covered} {noun} covered this in 48h")

    for row in titles:
        lines.append(f"- [{row.get('channel', '?')}] {row.get('title', '')}")

    lines.append(
        "Use for angle/title inspiration only — do not copy verbatim; differentiate TapIn take."
    )
    return "\n".join(lines)


def competitor_angle_hints(channel_id: str, topic: str) -> list[str]:
    """Short angle seeds from competitor titles related to topic."""
    hints = []
    for row in list_recent_competitor_titles(channel_id, topic=topic, limit=6):
        title = row.get("title", "")
        if len(title) > 20:
            hints.append(f"Competitor angle: {title[:90]}")
    return hints
