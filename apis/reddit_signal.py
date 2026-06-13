"""
Reddit community sentiment signal via Apify.

Scrapes relevant gaming/UFC subreddits for hot posts matching the topic.
Returns upvotes, comment counts, and top post titles as community sentiment data.

Actor: apify/reddit-scraper (public, free tier available)

Signal contract:
  connected = APIFY_CONTENT_MACHINE_KEY is set
  active    = ≥1 relevant post found
  score     = normalised engagement (0-100)
  data      = {posts: [...], subreddits_searched: [...]}
"""

from __future__ import annotations

import os
import re
from typing import Any

from apis.apify_client import run_actor
from apis.signal_contract import STATUS_INACTIVE, STATUS_NO_KEY, STATUS_OK, make_signal
from core.logging import get_logger

logger = get_logger("apis.reddit_signal")

# Actor ID for the Apify Reddit scraper
_ACTOR_ID = "trudax/reddit-scraper-lite"

# Domain → subreddits mapping
_DOMAIN_SUBREDDITS: dict[str, list[str]] = {
    "gaming": [
        "marvelrivals",
        "gaming",
        "pcgaming",
        "Games",
        "competitivegaming",
        "gamedev",
    ],
    "ufc": ["ufc", "MMA", "mmafighting", "boxing"],
    "nba": ["nba", "basketball", "nbadiscussion"],
    "nfl": ["nfl", "fantasyfootball", "nflstreams"],
    "neutral": ["gaming", "sports", "PopularOnReddit"],
}

_TTL = 3600 * 4  # 4h


def _pick_subreddits(topic: str, channel_id: str) -> list[str]:
    try:
        from apis.topic_scorer import infer_domain

        domain = infer_domain(topic, channel_id)
    except Exception:
        domain = "neutral"
    return _DOMAIN_SUBREDDITS.get(domain, _DOMAIN_SUBREDDITS["neutral"])


def _score_items(items: list[dict], query: str) -> list[dict]:
    """Filter and sort posts by relevance + engagement."""
    query_words = set(re.findall(r"[a-z]{3,}", query.lower()))
    scored = []
    for item in items:
        title = (item.get("title") or "").lower()
        ups = int(item.get("ups") or item.get("score") or 0)
        comments = int(item.get("numComments") or item.get("num_comments") or 0)
        # Basic relevance: how many query words appear in the title
        hits = sum(1 for w in query_words if w in title)
        if hits == 0 and ups < 500:
            continue
        engagement = ups + comments * 2
        scored.append({**item, "_relevance": hits, "_engagement": engagement})
    scored.sort(key=lambda x: (-x["_relevance"], -x["_engagement"]))
    return scored[:10]


def _normalise_score(items: list[dict]) -> float:
    if not items:
        return 0.0
    top_engagement = items[0].get("_engagement", 0)
    if top_engagement >= 5000:
        return 100.0
    if top_engagement >= 1000:
        return 80.0
    if top_engagement >= 200:
        return 65.0
    return 50.0


def get_reddit_signal(topic: str, channel_id: str = "default") -> dict[str, Any]:
    key_set = bool(os.getenv("APIFY_CONTENT_MACHINE_KEY", "").strip())
    if not key_set:
        return make_signal(
            connected=False,
            active=False,
            score=0,
            data=None,
            status_detail="Set APIFY_CONTENT_MACHINE_KEY for Reddit community sentiment",
            status=STATUS_NO_KEY,
        )

    subreddits = _pick_subreddits(topic, channel_id)

    # Build search query from topic (first anchor or cleaned topic)
    try:
        from core.channel_context import extract_anchors

        anchors = extract_anchors(topic)
        query = anchors[0] if anchors else topic
    except Exception:
        query = topic

    actor_input = {
        "searches": [{"query": query[:100], "sort": "hot"}],
        "subreddits": subreddits[:6],
        "maxItems": 20,
        "proxy": {"useApifyProxy": True},
    }

    items = run_actor(_ACTOR_ID, actor_input, purpose="main", timeout_secs=90, ttl=_TTL)
    if items is None:
        return make_signal(
            connected=True,
            active=False,
            score=0,
            data=None,
            status_detail="Reddit: Apify actor failed or timed out",
            status=STATUS_INACTIVE,
        )

    relevant = _score_items(items, query)
    if not relevant:
        return make_signal(
            connected=True,
            active=False,
            score=0,
            data=None,
            status_detail=f"Reddit: no matching posts in {', '.join(subreddits[:3])}",
            status=STATUS_INACTIVE,
        )

    score = _normalise_score(relevant)
    posts = [
        {
            "title": item.get("title") or "",
            "subreddit": item.get("subreddit") or "",
            "ups": item.get("ups") or item.get("score") or 0,
            "comments": item.get("numComments") or item.get("num_comments") or 0,
            "url": item.get("url") or "",
        }
        for item in relevant[:8]
    ]

    return make_signal(
        connected=True,
        active=True,
        score=score,
        data={"posts": posts, "subreddits_searched": subreddits},
        status=STATUS_OK,
    )
