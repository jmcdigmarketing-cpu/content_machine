"""FRED — Federal Reserve economic data (official, free with API key)."""

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

_KEY = os.getenv("FRED_API_KEY", "").strip()
_BASE = "https://api.stlouisfed.org/fred"
_TTL = 12 * 60 * 60
_UA = {"User-Agent": "ContentMachine/1.0"}


def _search_query(topic: str) -> str:
    text = re.sub(r"\b(20\d{2}|analysis|why|how|stock|stocks)\b", "", topic, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:64] or topic[:64]


def get_fred_signal(topic: str) -> dict:
    if not _KEY:
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_NO_KEY,
            status_detail="Set FRED_API_KEY (free at fred.stlouisfed.org)",
        )

    cache_key = build_key("fred", topic)
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    query = _search_query(topic)
    try:
        resp = requests.get(
            f"{_BASE}/series/search",
            params={
                "search_text": query,
                "api_key": _KEY,
                "file_type": "json",
                "limit": 8,
            },
            headers=_UA,
            timeout=12,
        )
        if resp.status_code != 200:
            status, detail = classify_http(resp.status_code, resp.text)
            return make_signal(connected=False, active=False, status=status, status_detail=detail)

        series = (resp.json().get("seriess") or [])[:5]
        if not series:
            sig = make_signal(
                connected=True,
                active=False,
                status=STATUS_INACTIVE,
                status_detail="FRED: no macro series match",
            )
            set_cache(cache_key, sig, ttl_seconds=_TTL)
            return sig

        titles: list[str] = [s.get("title", "") for s in series if s.get("title")]
        score = min(35 + len(series) * 12, 92)
        sig = make_signal(
            connected=True,
            active=True,
            score=float(score),
            confidence=0.92,
            status=STATUS_OK,
            status_detail=f"FRED: {len(series)} macro series",
            data={"series": series, "titles": titles},
        )
        set_cache(cache_key, sig, ttl_seconds=_TTL)
        return sig
    except Exception as exc:
        status, detail = classify_exception(exc)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)
