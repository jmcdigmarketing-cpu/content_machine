"""TMDB — movies/TV trending and search (free API key)."""

from __future__ import annotations

import os
import re

import requests

from apis.cache_manager import build_key, get_cached, set_cache
from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_NO_KEY,
    STATUS_OK,
    classify_exception,
    classify_http,
    make_signal,
)

_KEY = os.getenv("TMDB_API_KEY", "").strip()
_BASE = "https://api.themoviedb.org/3"
_TTL = 6 * 60 * 60


def _search_query(topic: str) -> str:
    text = re.sub(r"\b(movie|film|trailer|review|20\d{2})\b", "", topic, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()[:64] or topic[:64]


def get_tmdb_signal(topic: str) -> dict:
    if not _KEY:
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_NO_KEY,
            status_detail="Set TMDB_API_KEY (free at themoviedb.org)",
        )

    cache_key = build_key("tmdb", topic)
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        search = requests.get(
            f"{_BASE}/search/multi",
            params={"api_key": _KEY, "query": _search_query(topic), "page": 1},
            timeout=12,
        )
        if search.status_code != 200:
            status, detail = classify_http(search.status_code, search.text)
            return make_signal(connected=False, active=False, status=status, status_detail=detail)

        results = (search.json().get("results") or [])[:6]
        trending = requests.get(
            f"{_BASE}/trending/all/week",
            params={"api_key": _KEY},
            timeout=12,
        )
        trend_titles = []
        if trending.status_code == 200:
            trend_titles = [
                (r.get("title") or r.get("name") or "")
                for r in (trending.json().get("results") or [])[:10]
            ]

        if not results:
            sig = make_signal(
                connected=True,
                active=False,
                status=STATUS_INACTIVE,
                status_detail="TMDB: no title match",
            )
            set_cache(cache_key, sig, ttl_seconds=_TTL)
            return sig

        titles = [(r.get("title") or r.get("name") or "") for r in results]
        topic_l = topic.lower()
        overlap = sum(1 for t in trend_titles if t and t.lower() in topic_l)
        score = min(40 + len(results) * 8 + overlap * 5, 95)
        sig = make_signal(
            connected=True,
            active=True,
            score=float(score),
            confidence=0.88,
            status=STATUS_OK,
            status_detail=f"TMDB: {len(results)} titles",
            data={"results": results, "titles": titles, "trending_week": trend_titles[:5]},
        )
        set_cache(cache_key, sig, ttl_seconds=_TTL)
        return sig
    except Exception as exc:
        status, detail = classify_exception(exc)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)
