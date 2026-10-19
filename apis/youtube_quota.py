"""
Local estimate of YouTube Data API quota usage.

Google does not return remaining quota on successful calls; this tracker
uses documented unit costs and a configurable daily cap (default 10,000).
"""

import json
import os
import threading
import time
from datetime import datetime, timezone

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


def _now() -> datetime:
    return datetime.now(timezone.utc)


def quota_day(now=None) -> str:
    """#1288: the quota day is YouTube's - midnight Pacific (`core.reset_window`), not this PC's.
    The 00:03 CDT uploads of 2026-10-18 were booked to Oct 18 while YouTube counted them on Oct 17,
    so the morning said 3 uploads left where YouTube allowed 6. ``now`` may be an ISO string."""
    from zoneinfo import ZoneInfo

    from core.reset_window import _YOUTUBE_TZ

    moment = now if now is not None else _now()
    if isinstance(moment, str):
        moment = datetime.fromisoformat(moment.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(ZoneInfo(_YOUTUBE_TZ)).date().isoformat()


_LOCK = threading.Lock()  # signals record from a thread pool; the read-modify-write must not race


def record_usage(units=None, caller: str = "search"):
    """Add `units` to today's total, under `caller` - wave 113: 9,485 units went on 2026-10-17
    and the ledger could not say on what."""
    units = units or units_per_search_call()
    today = quota_day()
    with _LOCK:
        data = _load()
        entry = data.get(today, {"used": 0, "updated": time.time()})
        entry["used"] = entry.get("used", 0) + units
        by = entry.get("by") if isinstance(entry.get("by"), dict) else {}
        by[caller] = int(by.get(caller, 0)) + int(units)
        entry["by"] = by
        entry["updated"] = time.time()
        data[today] = entry
        _save(data)
    return get_usage_summary()


# Wave 113: YouTube's documented unit costs for the calls that booked nothing - a captions insert
# alone is 400, each status or snippet update 50 - so "uploads left" read high.
API_UNITS = {
    "videos.update": 50,
    "captions.insert": 400,
    "commentThreads.insert": 50,
    "playlists.insert": 50,
    "playlistItems.insert": 50,
    "videos.list": 1,
    "channels.list": 1,
    "playlistItems.list": 1,
}


def record_call(kind: str) -> None:
    """Book one Data API call by its documented cost, under its own name. Never raises: a ledger
    write must not fail an upload, a go-public or a caption."""
    try:
        record_usage(units=API_UNITS.get(kind, 1), caller=kind)
    except Exception as exc:
        logger.debug("quota not recorded for %s: %s", kind, exc)


def usage_by_caller(day: str | None = None) -> dict[str, int]:
    """{caller: units} for a quota day (today by default); {} before wave 113 recorded it."""
    entry = _load().get(day or quota_day(), {})
    by = entry.get("by") if isinstance(entry, dict) else None
    return {str(k): int(v) for k, v in (by or {}).items()}


def format_usage_split(day: str | None = None) -> str:
    """'upload 3,200 · search 2,424 · ...', biggest first; what was not broken down says so."""
    entry = _load().get(day or quota_day(), {})
    used = int(entry.get("used", 0)) if isinstance(entry, dict) else 0
    by = usage_by_caller(day)
    if not by:
        return "not broken down yet (recorded from 2026-10-18)" if used else ""
    parts = [f"{name} {units:,}" for name, units in sorted(by.items(), key=lambda kv: -kv[1])]
    rest = used - sum(by.values())
    if rest > 0:
        parts.append(f"before the breakdown {rest:,}")
    return ", ".join(parts)  # cp1252-safe: a "·" printed as "?" in `ops status`


def upload_reserve() -> int:
    """Units searches leave for one upload (wave 113, the operator: an upload is worth more than a
    late search). `YOUTUBE_UPLOAD_RESERVE`, default one upload; 0 turns it off. Competitor sync
    keeps its own (`COMPETITOR_SYNC_RESERVE_UNITS`)."""
    raw = os.getenv("YOUTUBE_UPLOAD_RESERVE", "").strip()
    try:
        return max(0, int(raw)) if raw else UNITS_VIDEO_INSERT
    except ValueError:
        return UNITS_VIDEO_INSERT


def get_usage_summary():
    today = quota_day()
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
        f"({s['used']:,}/{s['limit']:,} used; ~{s['per_call']} per search; "
        f"~{uploads_remaining(s)} uploads left this reset)"
    )


def has_quota_for_search() -> bool:
    """A search leaves `upload_reserve()` units, so a finished video can still upload today."""
    return get_usage_summary()["remaining"] >= units_per_search_call() + upload_reserve()


def units_for_lightweight_search():
    return UNITS_SEARCH_LIST


def units_per_upload():
    return UNITS_VIDEO_INSERT


def uploads_remaining(summary: dict | None = None) -> int:
    """How many ~1,600-unit uploads fit in today's remaining quota."""
    s = summary if summary is not None else get_usage_summary()
    remaining = int(s.get("remaining") or 0)
    need = units_per_upload()
    if need <= 0:
        return 0
    return max(0, remaining // need)


def quota_increase_advice(summary: dict | None = None) -> str:
    """Uploads-left line; attach the in-repo request checklist when one upload cannot fit."""
    s = summary if summary is not None else get_usage_summary()
    n = uploads_remaining(s)
    line = f"~{n} upload(s) left this reset"
    if n >= 1:
        return line
    from config.paths import ROOT_DIR

    playbook = os.path.join(ROOT_DIR, "docs", "youtube_quota_increase.md")
    return (
        f"{line}\n"
        "YouTube quota increase checklist (do not invent numbers):\n"
        "- Confirm remaining units cannot cover one upload (~1,600).\n"
        "- Request an increase in Google Cloud Console for YouTube Data API v3.\n"
        f"- Follow {playbook}"
    )


def format_uploads_left(summary: dict | None = None) -> str:
    """Operator line: remaining units as a hard upload ceiling."""
    s = summary if summary is not None else get_usage_summary()
    n = uploads_remaining(s)
    line = (
        f"~{n} upload(s) left this reset "
        f"(~{s.get('remaining', 0):,} units; upload needs ~{units_per_upload():,})"
    )
    if n < 1:
        extra = quota_increase_advice(s)
        if "quota increase" in extra.lower():
            line = f"{line}\n{extra}"
    return line


def has_quota_for_upload() -> bool:
    return get_usage_summary()["remaining"] >= units_per_upload()


def record_upload_usage():
    return record_usage(units=UNITS_VIDEO_INSERT, caller="upload")


def units_per_thumbnail():
    return UNITS_THUMBNAIL_SET


def has_quota_for_thumbnail() -> bool:
    return get_usage_summary()["remaining"] >= units_per_thumbnail()


def record_thumbnail_usage():
    return record_usage(units=UNITS_THUMBNAIL_SET, caller="thumbnail")


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
