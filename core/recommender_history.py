"""Week-to-week memory for length and post-time picks (#568).

A recommendation that flips is information; one that silently replaces last
week's pick looks like a stable default. The stamp is fail-open: a missing or
corrupt file is printed as 'could not compare', never treated as agreement.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("core.recommender_history")

STAMP_PATH_TEMPLATE = os.path.join(DATA_DIR, "recommend_pick_{channel}.json")


def stamp_path(channel_id: str) -> str:
    safe = "".join(ch for ch in str(channel_id) if ch.isalnum() or ch in ("-", "_"))
    return STAMP_PATH_TEMPLATE.format(channel=safe or "default")


def _iso_week(now: datetime) -> str:
    iso = now.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _load(path: str) -> tuple[dict, str]:
    """Return (data, error_note). error_note is set when the guarantee is lost."""
    if not os.path.isfile(path):
        return {}, ""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data, ""
        logger.warning("recommender pick stamp is not an object: %s", path)
        return {}, "could not compare to last week's pick"
    except Exception as exc:
        logger.warning("recommender pick stamp unreadable (%s): %s", path, exc)
        return {}, "could not compare to last week's pick"


def note_week_flip(
    channel_id: str,
    kind: str,
    pick: str,
    *,
    now: datetime | None = None,
    stamp_file: str | None = None,
) -> str:
    """Stamp this week's pick. Return a note when it disagrees with last week's."""
    when = now or datetime.now(timezone.utc)
    path = stamp_file or stamp_path(channel_id)
    data, error = _load(path)
    iso = _iso_week(when)
    prev = data.get(kind) if isinstance(data.get(kind), dict) else None
    note = error
    if not note and prev:
        prev_week = str(prev.get("week") or "")
        prev_pick = str(prev.get("pick") or "")
        if prev_week and prev_week != iso and prev_pick and prev_pick != str(pick):
            note = f"last week recommended {prev_pick}; this week {pick}"
    data[kind] = {"week": iso, "pick": str(pick)}
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    except Exception as exc:
        logger.warning("recommender pick stamp not written (%s): %s", path, exc)
        if not note:
            note = "could not compare to last week's pick"
    return note
