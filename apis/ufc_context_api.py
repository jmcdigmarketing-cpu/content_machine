"""
UFC/MMA research signal — RSS + news API + API-SPORTS fighter stats.

Reddit removed; MMA RSS feeds (Sherdog, MMA Fighting, etc.) via blog_rss path.
Tapology is retired (Cloudflare 403) but still consulted when its flag is set —
structured fighter facts now come from `apis/mma_stats_api.py`.
"""

from __future__ import annotations

import os
import re
from typing import Any

import requests

from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_OK,
    classify_exception,
    make_signal,
)

NEWS_API_KEY = os.getenv("NEWS_API_KEY")


def _is_ufc_topic(topic: str) -> bool:
    t = topic.lower()
    return any(
        k in t
        for k in (
            "ufc",
            "mma",
            "topuria",
            "gaethje",
            "oliveira",
            "poirier",
            "boxing",
            "fight night",
            "ppv",
        )
    )


def _fetch_news_headlines(query: str, *, limit: int = 8) -> list[dict[str, str]]:
    if not NEWS_API_KEY:
        return []
    q = f"{query} MMA UFC (fight card OR weigh-in)"
    url = "https://newsapi.org/v2/everything"
    try:
        response = requests.get(
            url,
            params={
                "q": q,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": limit,
                "apiKey": NEWS_API_KEY,
            },
            timeout=8,
        )
        if response.status_code != 200:
            return []
        articles = response.json().get("articles") or []
        out = []
        for article in articles[:limit]:
            title = (article.get("title") or "").strip()
            if not title or title == "[Removed]":
                continue
            out.append(
                {
                    "title": title,
                    "source": (article.get("source") or {}).get("name", ""),
                    "description": (article.get("description") or "")[:240],
                }
            )
        return out
    except Exception:
        return []


def _fetch_mma_rss(topic: str, *, limit: int = 8) -> list[dict[str, str]]:
    try:
        from apis.rss_feeds import fetch_rss_context

        ctx = fetch_rss_context(topic, "tapin")
        headlines = []
        for h in ctx.get("headlines") or []:
            source = str(h.get("source", "")).lower()
            title = str(h.get("title", "")).lower()
            if any(
                k in source or k in title
                for k in ("sherdog", "mma", "ufc", "fight", "espn mma", "mmafighting")
            ) or any(k in topic.lower() for k in ("ufc", "mma", "fight")):
                headlines.append(h)
            if len(headlines) >= limit:
                break
        return headlines[:limit]
    except Exception:
        return []


def get_ufc_context(topic: str):
    if not _is_ufc_topic(topic):
        return make_signal(
            connected=True,
            active=False,
            status=STATUS_INACTIVE,
            status_detail="Not a UFC/MMA topic",
        )

    try:
        event_match = re.search(r"\bUFC\s*(\d{2,4})\b", topic, re.I)
        search_topic = topic
        if event_match:
            search_topic = f"UFC {event_match.group(1)} {topic}"

        # Structured fighter facts. Replaces the Tapology scrape, which has been
        # Cloudflare-blocked (403) since ~2026-07 and returned nothing for a month.
        # Tapology stays behind its flag for revival; see apis/tapology_api.py.
        fighter_stats: dict[str, Any] = {}
        try:
            from apis.mma_stats_api import gather_mma_stats

            fighter_stats = gather_mma_stats(topic)
        except Exception:
            fighter_stats = {}

        tapology: dict[str, Any] = {}
        from apis.tapology_api import scrape_enabled as tapology_enabled

        if tapology_enabled():
            try:
                from apis.tapology_api import scrape_tapology

                tapology = scrape_tapology(topic)
            except Exception:
                tapology = {}

        headlines = _fetch_news_headlines(search_topic) if NEWS_API_KEY else []
        rss_headlines = _fetch_mma_rss(topic)
        stat_lines = fighter_stats.get("lines") or []

        active = bool(
            headlines
            or rss_headlines
            or stat_lines
            or tapology.get("bouts")
            or tapology.get("events_found")
        )
        score = min(
            20
            + len(headlines) * 8
            + len(rss_headlines) * 6
            + len(stat_lines) * 10
            + len(tapology.get("bouts") or []) * 12,
            100,
        )

        return make_signal(
            connected=True,
            active=active,
            score=score,
            confidence=0.9
            if (stat_lines or tapology.get("bouts"))
            else (0.85 if headlines else 0.7),
            data={
                "fighter_stats": fighter_stats,
                "tapology": tapology,
                "headlines": headlines,
                "rss_headlines": rss_headlines,
                "research_note": (
                    "RSS + news headlines are source of truth for event context. "
                    "Fighter records/physicals come from API-SPORTS. "
                    "Do not invent retired fighters as active contenders."
                ),
            },
            status=STATUS_OK if active else STATUS_INACTIVE,
            status_detail=None if active else "No UFC research (RSS/news/fighter stats)",
        )
    except Exception as e:
        status, detail = classify_exception(e)
        return make_signal(
            connected=False,
            active=False,
            status=status,
            status_detail=detail,
        )
