"""Local $0 seasonal seeds for best-bet — no HTTP, not a second cache.

Dated items (UFC cards, earnings weeks, game launches) live in
``config/seasonal_calendar.json``. Past dates are expired. Fail-open: missing
or corrupt file yields no seeds.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("core.seasonal_calendar")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today(now: datetime | None = None) -> date:
    stamp = now or _now()
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.date()


def _path() -> str:
    from config.paths import SEASONAL_CALENDAR_FILE

    return SEASONAL_CALENDAR_FILE


def _load() -> dict[str, Any]:
    path = _path()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception as exc:
        logger.debug("seasonal calendar read failed: %s", exc)
        return {}


def due_topics(channel_id: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    """Items whose ``date`` is today for ``channel_id``. Expired dates omitted."""
    today = _today(now)
    payload = _load()
    rows = payload.get(channel_id) or payload.get("channels", {}).get(channel_id) or []
    if not isinstance(rows, list):
        return []
    due: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        day = str(raw.get("date") or "").strip()
        topic = str(raw.get("topic") or "").strip()
        if not day or not topic:
            continue
        try:
            item_day = date.fromisoformat(day)
        except ValueError:
            logger.debug("seasonal calendar skipped bad date %r", day)
            continue
        if item_day < today:
            continue
        if item_day != today:
            continue
        due.append(
            {
                "date": day,
                "topic": topic,
                "domain": str(raw.get("domain") or "").strip(),
            }
        )
    return due
