"""
YouTube competitor-performance signal via Apify.

The YouTube Data API gives titles cheaply but not deep performance data. This
Apify signal pulls the top videos actually ranking for a topic, then computes
*view velocity* (views per day since upload) to reveal what is hot RIGHT NOW —
not just what has accumulated views over years.

Highest-value output for a YouTube channel:
  - Working titles (proven hooks ranking today)
  - View velocity (views/day) → which angle has momentum
  - Optimal duration band (median length of the winners)
  - Verified facts: real titles reference real, current events

Actor: streamers/youtube-scraper (catalog: youtube_competitors)

Signal contract:
  connected = APIFY_CONTENT_MACHINE_KEY set
  active    = >=1 ranking video found
  score     = normalised momentum (0-100) from top view velocity
  data      = {videos, top_velocity, median_duration_secs, hot_titles}
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any

from apis.apify_catalog import build_input, get_source
from apis.apify_client import run_actor
from apis.free_backends import fetch_youtube_free, signal_backend, youtube_available
from apis.signal_contract import STATUS_INACTIVE, STATUS_NO_KEY, STATUS_OK, make_signal
from core.logging import get_logger

logger = get_logger("apis.youtube_apify_signal")

_SOURCE = "youtube_competitors"


def _fetch_items(backend: str, query: str) -> tuple[list[dict] | None, str]:
    """Fetch raw items for `query` using the selected backend.

    Returns (items, source):
      items  -- raw item list (possibly empty), or None on a hard failure the
                caller must surface as "no_key"/"not_configured"/apify-timeout.
      source -- "free" | "apify" | "no_key" | "not_configured"
    """
    if backend in ("free", "auto"):
        if youtube_available():
            free_items = fetch_youtube_free(query)
            if free_items:
                return free_items, "free"
        if backend == "free":
            return [], "free"
        # auto: free unavailable/empty -> fall through to Apify below

    try:
        from apis.apify_client import apify_disabled

        if apify_disabled():
            if youtube_available():
                free_items = fetch_youtube_free(query)
                if free_items:
                    return free_items, "free"
            return [], "apify_off"
    except Exception as exc:
        logger.debug("apify_disabled skipped: %s", exc)

    if not os.getenv("APIFY_CONTENT_MACHINE_KEY", "").strip():
        return None, "no_key"

    src = get_source(_SOURCE)
    actor = src.get("actor")
    if not actor:
        return None, "not_configured"

    actor_input = build_input(_SOURCE, query)
    ttl = int(src.get("ttl_seconds", 10800))
    items = run_actor(actor, actor_input, purpose="main", timeout_secs=120, ttl=ttl)
    if items is None:
        return None, "apify"
    return items, "apify"


def _build_query(topic: str) -> str:
    try:
        from core.channel_context import extract_anchors

        anchors = extract_anchors(topic)
        if anchors:
            return f"{anchors[0]} {topic}"[:90]
    except Exception as exc:
        logger.debug("extract_anchors skipped: %s", exc)
    return topic[:90]


def _parse_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, int | float):
        return int(value)
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else 0


def _days_since(date_str: Any) -> float:
    """Approximate age in days from an ISO date or 'date' field. Floors at 1."""
    if not date_str:
        return 30.0
    text = str(date_str)
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text[: len(fmt) + 2 if "T" in fmt else len(fmt)], fmt)
            dt = dt.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0
            return max(age, 1.0)
        except (ValueError, TypeError):
            continue
    return 30.0


def _duration_secs(value: Any) -> int:
    """Accept seconds-int or 'MM:SS' / 'HH:MM:SS' strings."""
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str) and ":" in value:
        parts = [int(p) for p in value.split(":") if p.isdigit()]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
    return _parse_int(value)


def _normalise_score(top_velocity: float) -> float:
    if top_velocity >= 100_000:
        return 100.0
    if top_velocity >= 25_000:
        return 90.0
    if top_velocity >= 5_000:
        return 75.0
    if top_velocity >= 1_000:
        return 60.0
    if top_velocity > 0:
        return 45.0
    return 0.0


def get_youtube_apify_signal(topic: str, channel_id: str = "default") -> dict[str, Any]:
    query = _build_query(topic)
    backend = signal_backend()
    items, source = _fetch_items(backend, query)

    if source == "no_key":
        return make_signal(
            connected=False,
            active=False,
            score=0,
            data=None,
            status_detail="Set APIFY_CONTENT_MACHINE_KEY for YouTube competitor performance",
            status=STATUS_NO_KEY,
        )
    if source == "not_configured":
        return make_signal(
            connected=True,
            active=False,
            score=0,
            data=None,
            status_detail="youtube_competitors not configured in apify_sources.json",
            status=STATUS_INACTIVE,
        )
    if items is None:
        return make_signal(
            connected=True,
            active=False,
            score=0,
            data=None,
            status_detail="YouTube/Apify: actor failed or timed out",
            status=STATUS_INACTIVE,
        )
    if not items:
        label = "YouTube (free/yt-dlp)" if source == "free" else "YouTube/Apify"
        return make_signal(
            connected=True,
            active=False,
            score=0,
            data=None,
            status_detail=f"{label}: no videos for '{query}'",
            status=STATUS_INACTIVE,
        )

    enriched: list[dict[str, Any]] = []
    for it in items:
        title = (it.get("title") or "").strip()
        if not title:
            continue
        views = _parse_int(it.get("viewCount") or it.get("views") or it.get("numberOfViews"))
        age_days = _days_since(it.get("date") or it.get("uploadedAt") or it.get("publishedAt"))
        velocity = round(views / age_days, 1) if views else 0.0
        enriched.append(
            {
                "title": title[:140],
                "channel": (it.get("channelName") or it.get("channel") or "")[:60],
                "views": views,
                "age_days": round(age_days, 1),
                "velocity": velocity,
                "duration_secs": _duration_secs(it.get("duration") or it.get("lengthSeconds")),
                "url": it.get("url") or it.get("videoUrl") or "",
            }
        )

    if not enriched:
        return make_signal(
            connected=True,
            active=False,
            score=0,
            data=None,
            status_detail="YouTube/Apify: results had no usable titles",
            status=STATUS_INACTIVE,
        )

    enriched.sort(key=lambda v: -v["velocity"])
    top_velocity = enriched[0]["velocity"]
    durations = sorted(v["duration_secs"] for v in enriched if v["duration_secs"] > 0)
    median_duration = durations[len(durations) // 2] if durations else 0
    hot_titles = [v["title"] for v in enriched[:8]]

    return make_signal(
        connected=True,
        active=True,
        score=_normalise_score(top_velocity),
        data={
            "videos": enriched[:12],
            "top_velocity": top_velocity,
            "median_duration_secs": median_duration,
            "hot_titles": hot_titles,
            "backend": source,
        },
        status=STATUS_OK,
    )
