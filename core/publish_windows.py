"""Quiet hours (#116) + UFC PPV blackout (#115).

Do not go *public* during operator sleep or a live PPV window (cannibalizes
the niche). Unlisted review holds are not "publishing". Nested try; never
writes quota stores. Suite sets UFC_PPV_BLACKOUT=false and QUIET_HOURS=false.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("core.publish_windows")

_UFC_TOPIC = re.compile(r"\b(ufc|mma|ppv|fight night)\b", re.IGNORECASE)
# EA UFC 1-5 / Undisputed — a TapIn *game* topic, not a live card. Must not
# inherit Saturday PPV blackout or the Pexels "ufc" -> "mma" rewrite.
_UFC_GAME = re.compile(
    r"\b(?:ea sports\s+)?ufc\s*[1-5]\b|\bufc undisputed\b|\bea sports ufc\b",
    re.IGNORECASE,
)

_DEFAULT_PPV = {
    "weekday": 5,  # Saturday (Mon=0)
    "start_hour": 21,
    "end_hour": 2,
    "timezone": "America/New_York",
}


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _tz(name: str):
    label = (name or "America/New_York").strip() or "America/New_York"
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(label)
    except Exception as exc:
        logger.debug("timezone %s unavailable: %s", label, exc)
        return timezone(timedelta(hours=-4))


def _as_utc(when: datetime | None) -> datetime:
    now = when or datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _channel_raw(channel_id: str | None) -> dict[str, Any]:
    if not channel_id:
        return {}
    try:
        from config.channels import _load_channels_file, resolve_channel_id

        raw = _load_channels_file()
        channels = raw.get("channels", raw) if isinstance(raw, dict) else {}
        cfg = channels.get(resolve_channel_id(channel_id)) or {}
        return cfg if isinstance(cfg, dict) else {}
    except Exception as exc:
        logger.debug("channel raw skipped: %s", exc)
        return {}


def _hour_window(
    local: datetime,
    start_hour: int,
    end_hour: int,
    weekday: int | None,
) -> bool:
    """True when `local` sits in [start, end) (end may wrap midnight)."""
    try:
        start_hour = int(start_hour)
        end_hour = int(end_hour)
    except (TypeError, ValueError):
        return False
    if start_hour == end_hour:
        return False
    h = local.hour
    wd = local.weekday()
    if start_hour < end_hour:
        in_hours = start_hour <= h < end_hour
        return in_hours if weekday is None else in_hours and wd == int(weekday)
    if h >= start_hour:
        return weekday is None or wd == int(weekday)
    if h < end_hour:
        prev = (int(weekday) + 1) % 7 if weekday is not None else None
        return prev is None or wd == prev
    return False


def _clear_after(
    local: datetime,
    start_hour: int,
    end_hour: int,
) -> datetime:
    start_hour = int(start_hour)
    end_hour = int(end_hour)
    if start_hour < end_hour:
        clear = local.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        if clear <= local:
            clear += timedelta(days=1)
        return clear
    if local.hour >= start_hour:
        nxt = local + timedelta(days=1)
        return nxt.replace(hour=end_hour, minute=0, second=0, microsecond=0)
    return local.replace(hour=end_hour, minute=0, second=0, microsecond=0)


def is_ufc_videogame_topic(topic: str = "") -> bool:
    """True for EA UFC / Undisputed titles — not a live-card topic."""
    return bool(_UFC_GAME.search(topic or ""))


def is_ufc_topic(topic: str = "", domain: str = "") -> bool:
    if is_ufc_videogame_topic(topic):
        return False
    if (domain or "").strip().lower() in ("ufc", "mma"):
        return True
    return bool(_UFC_TOPIC.search(topic or ""))


def quiet_hours_config(channel_id: str | None) -> dict[str, Any]:
    raw = _channel_raw(channel_id).get("quiet_hours") or {}
    return raw if isinstance(raw, dict) else {}


def ppv_config(channel_id: str | None) -> dict[str, Any]:
    raw = _channel_raw(channel_id).get("ufc_ppv_blackout") or {}
    if isinstance(raw, dict) and raw:
        merged = dict(_DEFAULT_PPV)
        merged.update(raw)
        return merged
    return dict(_DEFAULT_PPV)


def quiet_hours_reason(
    *,
    channel_id: str | None = None,
    when: datetime | None = None,
    config: dict[str, Any] | None = None,
) -> str | None:
    """Why going public now would hit quiet hours, or None."""
    if not _flag("QUIET_HOURS", True):
        return None
    cfg = config if config is not None else quiet_hours_config(channel_id)
    if not cfg:
        return None
    try:
        start = int(cfg.get("start_hour"))
        end = int(cfg.get("end_hour"))
    except (TypeError, ValueError):
        return None
    tz = _tz(str(cfg.get("timezone") or "America/New_York"))
    local = _as_utc(when).astimezone(tz)
    if not _hour_window(local, start, end, None):
        return None
    return f"quiet hours: {start:02d}:00-{end:02d}:00 {cfg.get('timezone') or 'local'}"


def ufc_ppv_reason(
    *,
    topic: str = "",
    domain: str = "",
    channel_id: str | None = None,
    when: datetime | None = None,
    config: dict[str, Any] | None = None,
) -> str | None:
    """Why a UFC topic should wait out the PPV window, or None."""
    if not _flag("UFC_PPV_BLACKOUT", True):
        return None
    if not is_ufc_topic(topic, domain):
        return None
    cfg = config if config is not None else ppv_config(channel_id)
    try:
        start = int(cfg.get("start_hour", 21))
        end = int(cfg.get("end_hour", 2))
        weekday = int(cfg.get("weekday", 5))
    except (TypeError, ValueError):
        return None
    tz = _tz(str(cfg.get("timezone") or "America/New_York"))
    local = _as_utc(when).astimezone(tz)
    if not _hour_window(local, start, end, weekday):
        return None
    return (
        f"UFC PPV window: Sat {start:02d}:00-{end:02d}:00 "
        f"{cfg.get('timezone') or 'ET'} (do not cannibalize the live card)"
    )


def window_reason(
    *,
    channel_id: str | None = None,
    topic: str = "",
    domain: str = "",
    when: datetime | None = None,
) -> str | None:
    why = ufc_ppv_reason(topic=topic, domain=domain, channel_id=channel_id, when=when)
    if why:
        return why
    return quiet_hours_reason(channel_id=channel_id, when=when)


def next_clear_utc(
    *,
    channel_id: str | None = None,
    topic: str = "",
    domain: str = "",
    when: datetime | None = None,
) -> datetime | None:
    """First UTC instant after the active window, or None when already clear."""
    when_utc = _as_utc(when)
    ppv = ufc_ppv_reason(topic=topic, domain=domain, channel_id=channel_id, when=when_utc)
    if ppv:
        cfg = ppv_config(channel_id)
        tz = _tz(str(cfg.get("timezone") or "America/New_York"))
        local = when_utc.astimezone(tz)
        clear = _clear_after(local, int(cfg["start_hour"]), int(cfg["end_hour"]))
        return clear.astimezone(timezone.utc)
    quiet = quiet_hours_reason(channel_id=channel_id, when=when_utc)
    if quiet:
        cfg = quiet_hours_config(channel_id)
        tz = _tz(str(cfg.get("timezone") or "America/New_York"))
        local = when_utc.astimezone(tz)
        clear = _clear_after(local, int(cfg["start_hour"]), int(cfg["end_hour"]))
        return clear.astimezone(timezone.utc)
    return None


def going_public_at(
    publish_at: datetime | None,
    *,
    privacy: str = "private",
    unlisted_review: bool | None = None,
    now: datetime | None = None,
) -> datetime | None:
    """When this upload would become public, or None if it stays non-public."""
    if publish_at:
        return _as_utc(publish_at)
    if (privacy or "").strip().lower() != "public":
        return None
    if unlisted_review is None:
        unlisted_review = os.getenv("YOUTUBE_UNLISTED_REVIEW", "true").strip().lower() not in (
            "0",
            "false",
            "no",
            "off",
        )
    if unlisted_review:
        return None
    return _as_utc(now)


def adjust_publish_at(
    publish_at: datetime | None,
    *,
    channel_id: str | None = None,
    topic: str = "",
    domain: str = "",
    privacy: str = "private",
    unlisted_review: bool | None = None,
    now: datetime | None = None,
) -> tuple[datetime | None, str | None]:
    """Bump a going-public time out of PPV / quiet hours. Returns (when, reason)."""
    target = going_public_at(publish_at, privacy=privacy, unlisted_review=unlisted_review, now=now)
    if target is None:
        return publish_at, None
    reasons: list[str] = []
    current = target
    for _ in range(4):
        why = window_reason(channel_id=channel_id, topic=topic, domain=domain, when=current)
        if not why:
            break
        if why not in reasons:
            reasons.append(why)
        clear = next_clear_utc(channel_id=channel_id, topic=topic, domain=domain, when=current)
        if clear is None or clear <= current:
            break
        current = clear
    if not reasons or current == target:
        return publish_at, None
    return current, "; ".join(reasons)


def resolve_relative_clock(
    phrase: str,
    *,
    now: datetime | None = None,
    tz_name: str = "America/New_York",
) -> datetime | None:
    """Resolve 'tonight' / 'this weekend' against TapIn ET at script time."""
    tz = _tz(tz_name)
    local = _as_utc(now).astimezone(tz)
    text = (phrase or "").strip().lower()
    if text == "tonight":
        target = local.replace(hour=21, minute=0, second=0, microsecond=0)
        if target <= local:
            target += timedelta(days=1)
        return target
    if text == "this weekend":
        days = (5 - local.weekday()) % 7
        return (local + timedelta(days=days)).replace(hour=12, minute=0, second=0, microsecond=0)
    return None
