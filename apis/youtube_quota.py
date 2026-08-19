"""
Local estimate of YouTube Data API quota usage.

Google does not return remaining quota on successful calls; this tracker
uses documented unit costs and a configurable daily cap (default 10,000).
"""

import json
import os
import time
from datetime import date

from config.paths import (
    ROOT_DIR,
    YOUTUBE_QUOTA_FILE,
    ensure_data_dir,
    migrate_file_if_needed,
    resolve_existing_path,
)
from core.logging import get_logger

logger = get_logger("apis.youtube_quota")

_LEGACY_QUOTA = os.path.join(ROOT_DIR, "youtube_quota.json")
UNITS_SEARCH_LIST = 100
UNITS_VIDEOS_LIST = 1
UNITS_VIDEO_INSERT = 1600
UNITS_THUMBNAIL_SET = 50


def daily_limit():
    try:
        return int(os.getenv("YOUTUBE_DAILY_QUOTA", "10000"))
    except ValueError:
        return 10000


def units_per_search_call():
    return UNITS_SEARCH_LIST + UNITS_VIDEOS_LIST


def _quota_path() -> str:
    ensure_data_dir()
    migrate_file_if_needed(YOUTUBE_QUOTA_FILE, _LEGACY_QUOTA)
    return resolve_existing_path(YOUTUBE_QUOTA_FILE, _LEGACY_QUOTA)


def _load():
    path = _quota_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data):
    with open(_quota_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def record_usage(units=None):
    units = units or units_per_search_call()
    today = date.today().isoformat()
    data = _load()
    entry = data.get(today, {"used": 0, "updated": time.time()})
    entry["used"] = entry.get("used", 0) + units
    entry["updated"] = time.time()
    data[today] = entry
    _save(data)
    return get_usage_summary()


def get_usage_summary():
    today = date.today().isoformat()
    data = _load()
    used = data.get(today, {}).get("used", 0)
    limit = daily_limit()
    remaining = max(limit - used, 0)
    return {
        "day": today,
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "per_call": units_per_search_call(),
    }


def format_quota_detail():
    s = get_usage_summary()
    return (
        f"~{s['remaining']:,} units remaining today "
        f"({s['used']:,}/{s['limit']:,} used; ~{s['per_call']} per search)"
    )


def has_quota_for_search() -> bool:
    return get_usage_summary()["remaining"] >= units_per_search_call()


def units_for_lightweight_search():
    return UNITS_SEARCH_LIST


def units_per_upload():
    return UNITS_VIDEO_INSERT


def has_quota_for_upload() -> bool:
    return get_usage_summary()["remaining"] >= units_per_upload()


def record_upload_usage():
    return record_usage(units=UNITS_VIDEO_INSERT)


def units_per_thumbnail():
    return UNITS_THUMBNAIL_SET


def has_quota_for_thumbnail() -> bool:
    return get_usage_summary()["remaining"] >= units_per_thumbnail()


def record_thumbnail_usage():
    return record_usage(units=UNITS_THUMBNAIL_SET)


def next_quota_retry_at():
    """When local tracker says upload is blocked, suggest next retry (UTC).

    O10: uses the documented Data API daily reset (midnight Pacific) via
    core.reset_window so a blocked upload retries right after the real reset
    instead of a heuristic +1 day. Falls back to the old heuristic when the
    reset-window layer is disabled or unavailable.
    """
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    if has_quota_for_upload():
        return now
    try:
        from core.reset_window import next_reset, reset_window_enabled

        if reset_window_enabled():
            nxt = next_reset("youtube", now=now)
            if nxt is not None:
                # Small buffer so the worker doesn't race the reset boundary.
                return nxt + timedelta(minutes=5)
    except Exception as exc:
        logger.debug("YouTube quota reset time unavailable: %s", exc)
    retry = (now + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
    if retry <= now:
        retry = now + timedelta(hours=6)
    return retry
