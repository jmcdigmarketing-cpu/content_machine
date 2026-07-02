"""
Free, keyless signal backends — an alternative to paid Apify actors for signals
where a public/keyless source carries the same fields the signal scores on.

Currently: YouTube (`youtube_competitors`) via yt-dlp, hybrid flat-search +
full-extract-top-N. See docs/agent_reach_evaluation.md for the spike that
validated field parity, and spikes/yt_backend_poc.py for the reference proof
(this module is the productionized version of that POC).

Every fetcher here returns items in the exact schema the corresponding Apify
signal already parses, and NEVER raises — callers get [] on any failure so a
free-backend outage degrades to "no results," not a crash.
"""

from __future__ import annotations

import os
from typing import Any

from core.logging import get_logger

logger = get_logger("apis.free_backends")


def youtube_available() -> bool:
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        return False
    return True


def _yt_top_n() -> int:
    try:
        return int(os.getenv("YT_FREE_TOP_N", "5"))
    except ValueError:
        return 5


def _yt_search_n() -> int:
    try:
        return int(os.getenv("YT_FREE_SEARCH_N", "15"))
    except ValueError:
        return 15


def _iso_date(upload_date: str | None) -> str | None:
    """yt-dlp gives 'YYYYMMDD'; emit full ISO datetime (the signal's _days_since
    only parses dates with a 'T' time component — see docs/agent_reach_evaluation.md)."""
    if upload_date and len(upload_date) == 8 and upload_date.isdigit():
        return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}T12:00:00"
    return None


def _flat_search(query: str, n: int) -> list[dict]:
    from yt_dlp import YoutubeDL

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": 15,
        "extract_flat": "in_playlist",
    }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
    return [e for e in (info.get("entries") or []) if e and e.get("url")]


def _full_one(url: str) -> dict | None:
    from yt_dlp import YoutubeDL

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": 15,
    }
    with YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def fetch_youtube_free(
    query: str, top_n: int | None = None, search_n: int | None = None
) -> list[dict]:
    """Hybrid free YouTube fetch: flat search ranks candidates by view count
    cheaply, then full-extracts only the top N to get upload_date for velocity.

    Returns items in the schema apis.youtube_apify_signal already parses:
    title, viewCount, date, channelName, duration, url. Returns [] on any
    failure (unavailable, network error, empty results) — never raises.
    """
    if not youtube_available():
        return []
    top_n = top_n if top_n is not None else _yt_top_n()
    search_n = search_n if search_n is not None else _yt_search_n()

    try:
        flat = _flat_search(query, search_n)
    except Exception as exc:
        logger.warning("yt-dlp flat search failed for %r: %s", query, exc)
        return []

    flat.sort(key=lambda e: -(e.get("view_count") or 0))

    items: list[dict[str, Any]] = []
    for entry in flat[:top_n]:
        full: dict[str, Any] = {}
        try:
            full = _full_one(entry["url"]) or {}
        except Exception as exc:
            logger.debug("yt-dlp full extract failed for %s: %s", entry.get("url"), exc)
        items.append(
            {
                "title": full.get("title") or entry.get("title") or "",
                "viewCount": full.get("view_count") or entry.get("view_count") or 0,
                "date": _iso_date(full.get("upload_date")),
                "channelName": full.get("channel") or entry.get("channel") or "",
                "duration": full.get("duration") or entry.get("duration") or 0,
                "url": full.get("webpage_url") or entry.get("url") or "",
            }
        )
    return items
