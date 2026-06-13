"""CoinGecko — crypto search and trending (free tier, no key for basic)."""

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

_BASE = "https://api.coingecko.com/api/v3"
_TTL = 3 * 60 * 60
_UA = {"User-Agent": "ContentMachine/1.0"}


def _search_query(topic: str) -> str:
    text = re.sub(r"\b(20\d{2}|crypto|cryptocurrency|coin|token)\b", "", topic, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()[:48] or topic[:48]


def get_coingecko_signal(topic: str) -> dict:
    cache_key = build_key("coingecko", topic)
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    query = _search_query(topic)
    try:
        resp = requests.get(
            f"{_BASE}/search",
            params={"query": query},
            headers=_UA,
            timeout=12,
        )
        if resp.status_code != 200:
            status, detail = classify_http(resp.status_code, resp.text)
            return make_signal(connected=False, active=False, status=status, status_detail=detail)

        coins = (resp.json().get("coins") or [])[:6]
        if not coins:
            sig = make_signal(
                connected=True,
                active=False,
                status=STATUS_INACTIVE,
                status_detail="CoinGecko: no crypto match",
            )
            set_cache(cache_key, sig, ttl_seconds=_TTL)
            return sig

        names = [c.get("name", "") for c in coins if c.get("name")]
        score = min(40 + len(coins) * 10, 92)
        sig = make_signal(
            connected=True,
            active=True,
            score=float(score),
            confidence=0.82,
            status=STATUS_OK,
            status_detail=f"CoinGecko: {len(coins)} assets",
            data={"coins": coins, "names": names},
        )
        set_cache(cache_key, sig, ttl_seconds=_TTL)
        return sig
    except Exception as exc:
        status, detail = classify_exception(exc)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)
