"""
TikTok trend signal via Apify (APIFY_BENABLE_BOT key).

Searches TikTok for videos matching the topic to surface:
  - What angles are trending (video titles/descriptions)
  - Engagement benchmarks (likes, views, shares)
  - Hashtag usage patterns

Actor: bebity/tiktok-scraper (APIFY_BENABLE_BOT key)
Fallback actor: clockworks/tiktok-scraper (APIFY_CONTENT_MACHINE_KEY)

Signal contract:
  connected = APIFY_BENABLE_BOT or APIFY_CONTENT_MACHINE_KEY is set
  active    = ≥1 gaming video found
  score     = normalised viral potential (0-100)
  data      = {videos: [...], top_hashtags: [...], avg_views: int}
"""

from __future__ import annotations

import os
import re
from typing import Any

from apis.apify_client import run_actor
from apis.signal_contract import STATUS_INACTIVE, STATUS_NO_KEY, STATUS_OK, make_signal
from core.logging import get_logger

logger = get_logger("apis.tiktok_signal")

# Primary actor (BENABLE_BOT key) — clockworks is the maintained TikTok scraper.
# (bebity/tiktok-scraper was retired and now 404s.)
_PRIMARY_ACTOR = "clockworks/tiktok-scraper"
# Fallback actor (CONTENT_MACHINE_KEY)
_FALLBACK_ACTOR = "clockworks/tiktok-scraper"

_TTL = 3600 * 3  # 3h — TikTok trends move fast


def _build_query(topic: str) -> str:
    try:
        from core.channel_context import extract_anchors

        anchors = extract_anchors(topic)
        return anchors[0] if anchors else topic
    except Exception:
        return topic[:80]


def _extract_hashtags(items: list[dict]) -> list[str]:
    counts: dict[str, int] = {}
    for item in items:
        desc = (item.get("text") or item.get("desc") or "").lower()
        tags = re.findall(r"#([a-z0-9_]+)", desc)
        for tag in tags:
            counts[tag] = counts.get(tag, 0) + 1
    return [t for t, _ in sorted(counts.items(), key=lambda x: -x[1])[:10]]


def _normalise_score(avg_views: float, item_count: int) -> float:
    if item_count == 0:
        return 0.0
    if avg_views >= 500_000:
        return 100.0
    if avg_views >= 100_000:
        return 90.0
    if avg_views >= 20_000:
        return 75.0
    if avg_views >= 5_000:
        return 60.0
    return 45.0


def get_tiktok_signal(topic: str, channel_id: str = "default") -> dict[str, Any]:
    from apis.apify_client import apify_disabled, apify_status

    if apify_disabled():
        return make_signal(
            connected=True,
            active=False,
            score=0,
            data=None,
            status_detail=f"TikTok/Apify: {apify_status()}",
            status=STATUS_INACTIVE,
        )
    benable_key = os.getenv("APIFY_BENABLE_BOT", "").strip()
    main_key = os.getenv("APIFY_CONTENT_MACHINE_KEY", "").strip()

    if not benable_key and not main_key:
        return make_signal(
            connected=False,
            active=False,
            score=0,
            data=None,
            status_detail="Set APIFY_BENABLE_BOT for TikTok trend discovery",
            status=STATUS_NO_KEY,
        )

    query = _build_query(topic)
    purpose = "tiktok" if benable_key else "main"
    actor = _PRIMARY_ACTOR if benable_key else _FALLBACK_ACTOR

    actor_input = {
        "searchQueries": [query],
        "maxItems": 20,
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
    }

    items = run_actor(actor, actor_input, purpose=purpose, timeout_secs=90, ttl=_TTL)

    # Try fallback if primary fails
    if items is None and benable_key and main_key:
        logger.info("TikTok: primary actor failed, trying fallback with main key")
        items = run_actor(_FALLBACK_ACTOR, actor_input, purpose="main", timeout_secs=90, ttl=_TTL)

    if items is None:
        return make_signal(
            connected=True,
            active=False,
            score=0,
            data=None,
            status_detail="TikTok: Apify actor failed or timed out",
            status=STATUS_INACTIVE,
        )

    if not items:
        return make_signal(
            connected=True,
            active=False,
            score=0,
            data=None,
            status_detail=f"TikTok: no videos found for '{query}'",
            status=STATUS_INACTIVE,
        )

    views_list = [
        int(
            item.get("playCount")
            or item.get("stats", {}).get("playCount")
            or item.get("views")
            or 0
        )
        for item in items
    ]
    avg_views = sum(views_list) / len(views_list) if views_list else 0
    top_hashtags = _extract_hashtags(items)
    score = _normalise_score(avg_views, len(items))

    videos = [
        {
            "title": (item.get("text") or item.get("desc") or item.get("title") or "")[:120],
            "views": int(
                item.get("playCount")
                or item.get("stats", {}).get("playCount")
                or item.get("views")
                or 0
            ),
            "likes": int(
                item.get("diggCount")
                or item.get("stats", {}).get("diggCount")
                or item.get("likes")
                or 0
            ),
            "author": item.get("authorMeta", {}).get("name") or item.get("author") or "",
        }
        for item in items[:10]
    ]

    return make_signal(
        connected=True,
        active=True,
        score=score,
        data={
            "videos": videos,
            "top_hashtags": top_hashtags,
            "avg_views": int(avg_views),
            "video_count": len(items),
        },
        status=STATUS_OK,
    )
