"""MusicBrainz — open music metadata (free, User-Agent required)."""

from __future__ import annotations

import os
import re
import time

import requests

from apis.cache_manager import build_key, get_cached, set_cache
from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_OK,
    classify_exception,
    classify_http,
    make_signal,
)

_BASE = "https://musicbrainz.org/ws/2"
_TTL = 12 * 60 * 60
_UA = os.getenv(
    "MUSICBRAINZ_USER_AGENT",
    "ContentMachine/1.0 (https://github.com/content-machine)",
)


def _search_query(topic: str) -> str:
    text = re.sub(r"\b(song|album|artist|music|20\d{2})\b", "", topic, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()[:64] or topic[:64]


def get_musicbrainz_signal(topic: str) -> dict:
    cache_key = build_key("musicbrainz", topic)
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    query = _search_query(topic)
    try:
        time.sleep(1.05)
        resp = requests.get(
            f"{_BASE}/release/",
            params={"query": query, "fmt": "json", "limit": 6},
            headers={"User-Agent": _UA, "Accept": "application/json"},
            timeout=14,
        )
        if resp.status_code != 200:
            status, detail = classify_http(resp.status_code, resp.text)
            return make_signal(connected=False, active=False, status=status, status_detail=detail)

        releases = (resp.json().get("releases") or [])[:6]
        if not releases:
            sig = make_signal(
                connected=True,
                active=False,
                status=STATUS_INACTIVE,
                status_detail="MusicBrainz: no release match",
            )
            set_cache(cache_key, sig, ttl_seconds=_TTL)
            return sig

        titles = [r.get("title", "") for r in releases if r.get("title")]
        score = min(35 + len(releases) * 9, 85)
        sig = make_signal(
            connected=True,
            active=True,
            score=float(score),
            confidence=0.78,
            status=STATUS_OK,
            status_detail=f"MusicBrainz: {len(releases)} releases",
            data={"releases": releases, "titles": titles},
        )
        set_cache(cache_key, sig, ttl_seconds=_TTL)
        return sig
    except Exception as exc:
        status, detail = classify_exception(exc)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)
