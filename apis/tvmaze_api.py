"""TVmaze — TV show search and schedules (free, no key)."""

from __future__ import annotations

import re

import requests

from apis.cache_manager import build_key, get_cached, set_cache
from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_OK,
    classify_exception,
    classify_http,
    make_signal,
)

_BASE = "https://api.tvmaze.com"
_TTL = 6 * 60 * 60
_UA = {"User-Agent": "ContentMachine/1.0"}


def _search_query(topic: str) -> str:
    text = re.sub(r"\b(tv|show|series|season|episode|20\d{2})\b", "", topic, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()[:64] or topic[:64]


def get_tvmaze_signal(topic: str) -> dict:
    cache_key = build_key("tvmaze", topic)
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        resp = requests.get(
            f"{_BASE}/search/shows",
            params={"q": _search_query(topic)},
            headers=_UA,
            timeout=12,
        )
        if resp.status_code != 200:
            status, detail = classify_http(resp.status_code, resp.text)
            return make_signal(connected=False, active=False, status=status, status_detail=detail)

        items = (resp.json() or [])[:6]
        if not items:
            sig = make_signal(
                connected=True,
                active=False,
                status=STATUS_INACTIVE,
                status_detail="TVmaze: no show match",
            )
            set_cache(cache_key, sig, ttl_seconds=_TTL)
            return sig

        shows = [entry.get("show") or {} for entry in items]
        titles = [s.get("name", "") for s in shows if s.get("name")]
        score = min(38 + len(shows) * 10, 88)
        sig = make_signal(
            connected=True,
            active=True,
            score=float(score),
            confidence=0.8,
            status=STATUS_OK,
            status_detail=f"TVmaze: {len(shows)} shows",
            data={"shows": shows, "titles": titles},
        )
        set_cache(cache_key, sig, ttl_seconds=_TTL)
        return sig
    except Exception as exc:
        status, detail = classify_exception(exc)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)
