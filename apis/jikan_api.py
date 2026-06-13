"""Jikan — unofficial MAL wrapper (fallback only, not load-bearing)."""

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

_BASE = "https://api.jikan.moe/v4"
_TTL = 6 * 60 * 60
_UA = {"User-Agent": "ContentMachine/1.0"}


def _search_query(topic: str) -> str:
    text = re.sub(r"\b(anime|manga|episode|season)\b", "", topic, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()[:64] or topic[:64]


def get_jikan_signal(topic: str) -> dict:
    cache_key = build_key("jikan", topic)
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        resp = requests.get(
            f"{_BASE}/anime",
            params={"q": _search_query(topic), "limit": 6},
            headers=_UA,
            timeout=14,
        )
        if resp.status_code != 200:
            status, detail = classify_http(resp.status_code, resp.text)
            return make_signal(connected=False, active=False, status=status, status_detail=detail)

        items = (resp.json().get("data") or [])[:6]
        if not items:
            sig = make_signal(
                connected=True,
                active=False,
                status=STATUS_INACTIVE,
                status_detail="Jikan: no anime match",
            )
            set_cache(cache_key, sig, ttl_seconds=_TTL)
            return sig

        titles = [i.get("title", "") for i in items if i.get("title")]
        score = min(35 + len(items) * 10, 85)
        sig = make_signal(
            connected=True,
            active=True,
            score=float(score),
            confidence=0.65,
            status=STATUS_OK,
            status_detail=f"Jikan (fallback): {len(items)} titles",
            data={"anime": items, "titles": titles},
        )
        set_cache(cache_key, sig, ttl_seconds=_TTL)
        return sig
    except Exception as exc:
        status, detail = classify_exception(exc)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)
