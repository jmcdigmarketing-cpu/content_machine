"""
Twitter/X breaking-news signal via Apify.

The highest-timeliness source available. UFC effectively breaks on Twitter —
fight bookings, results, injuries, fighter beef — and gaming controversy /
patch reactions spread there first. This signal grounds "just happened" topics
in real, attributable posts before slower news APIs catch up.

For each topic it searches recent top tweets AND, when the domain has known
authority accounts (Ariel Helwani, Schefter, Dexerto...), folds their handles
into the query so signal beats noise.

Actor: apidojo/tweet-scraper (catalog: twitter_breaking)

Signal contract:
  connected = APIFY_CONTENT_MACHINE_KEY set
  active    = >=1 relevant tweet found
  score     = normalised reach (0-100) from top engagement
  data      = {tweets, top_engagement, authority_hits}
"""

from __future__ import annotations

import os
import re
from typing import Any

from apis.apify_catalog import build_input, domain_targets, get_source
from apis.apify_client import run_actor
from apis.signal_contract import STATUS_INACTIVE, STATUS_NO_KEY, STATUS_OK, make_signal
from core.logging import get_logger

logger = get_logger("apis.twitter_signal")

_SOURCE = "twitter_breaking"


def _build_query(topic: str) -> str:
    try:
        from core.channel_context import extract_anchors

        anchors = extract_anchors(topic)
        if anchors:
            return anchors[0]
    except Exception:
        pass
    return topic[:80]


def _engagement(tweet: dict[str, Any]) -> int:
    likes = int(tweet.get("likeCount") or tweet.get("favoriteCount") or 0)
    rts = int(tweet.get("retweetCount") or 0)
    replies = int(tweet.get("replyCount") or 0)
    quotes = int(tweet.get("quoteCount") or 0)
    return likes + rts * 2 + replies + quotes * 2


def _normalise_score(top_engagement: int, authority_hits: int) -> float:
    base = 0.0
    if top_engagement >= 50_000:
        base = 95.0
    elif top_engagement >= 10_000:
        base = 85.0
    elif top_engagement >= 2_000:
        base = 70.0
    elif top_engagement >= 300:
        base = 55.0
    elif top_engagement > 0:
        base = 40.0
    # Authority accounts add confidence the topic is real and current
    return min(100.0, base + min(authority_hits, 3) * 3.0)


def get_twitter_signal(topic: str, channel_id: str = "default") -> dict[str, Any]:
    from apis.apify_client import apify_disabled, apify_status

    if apify_disabled():
        return make_signal(
            connected=True,
            active=False,
            score=0,
            data=None,
            status_detail=f"Twitter/Apify: {apify_status()}",
            status=STATUS_INACTIVE,
        )
    if not os.getenv("APIFY_CONTENT_MACHINE_KEY", "").strip():
        return make_signal(
            connected=False,
            active=False,
            score=0,
            data=None,
            status_detail="Set APIFY_CONTENT_MACHINE_KEY for Twitter/X breaking news",
            status=STATUS_NO_KEY,
        )

    src = get_source(_SOURCE)
    actor = src.get("actor")
    if not actor:
        return make_signal(
            connected=True,
            active=False,
            score=0,
            data=None,
            status_detail="twitter_breaking not configured in apify_sources.json",
            status=STATUS_INACTIVE,
        )

    try:
        from apis.topic_scorer import infer_domain

        domain = infer_domain(topic, channel_id)
    except Exception:
        domain = "neutral"

    query = _build_query(topic)
    authorities = domain_targets(domain).get("twitter_accounts", [])[:5]
    authority_set = {a.lower() for a in authorities}

    actor_input = build_input(_SOURCE, query)
    ttl = int(src.get("ttl_seconds", 5400))

    items = run_actor(actor, actor_input, purpose="main", timeout_secs=120, ttl=ttl)
    if items is None:
        return make_signal(
            connected=True,
            active=False,
            score=0,
            data=None,
            status_detail="Twitter/Apify: actor failed or timed out",
            status=STATUS_INACTIVE,
        )
    if not items:
        return make_signal(
            connected=True,
            active=False,
            score=0,
            data=None,
            status_detail=f"Twitter/Apify: no tweets for '{query}'",
            status=STATUS_INACTIVE,
        )

    query_words = set(re.findall(r"[a-z]{3,}", query.lower()))
    scored: list[dict[str, Any]] = []
    authority_hits = 0
    for tw in items:
        text = (tw.get("text") or tw.get("fullText") or "").strip()
        if not text:
            continue
        author = (
            tw.get("authorUsername")
            or (tw.get("author") or {}).get("userName")
            or tw.get("username")
            or ""
        )
        is_authority = author.lower() in authority_set
        if is_authority:
            authority_hits += 1
        eng = _engagement(tw)
        hits = sum(1 for w in query_words if w in text.lower())
        if hits == 0 and not is_authority and eng < 200:
            continue
        scored.append(
            {
                "text": text[:240],
                "author": author,
                "engagement": eng,
                "authority": is_authority,
                "url": tw.get("url") or tw.get("twitterUrl") or "",
            }
        )

    if not scored:
        return make_signal(
            connected=True,
            active=False,
            score=0,
            data=None,
            status_detail=f"Twitter/Apify: no relevant tweets for '{query}'",
            status=STATUS_INACTIVE,
        )

    # Authority tweets first, then by engagement
    scored.sort(key=lambda t: (not t["authority"], -t["engagement"]))
    top_engagement = max(t["engagement"] for t in scored)

    return make_signal(
        connected=True,
        active=True,
        score=_normalise_score(top_engagement, authority_hits),
        data={
            "tweets": scored[:8],
            "top_engagement": top_engagement,
            "authority_hits": authority_hits,
        },
        status=STATUS_OK,
    )
