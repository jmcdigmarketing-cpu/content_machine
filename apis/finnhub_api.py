"""Finnhub — market news, symbol search, sentiment (free tier with key)."""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone

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

_KEY = os.getenv("FINNHUB_API_KEY", "").strip()
_BASE = "https://finnhub.io/api/v1"
_TTL = 3 * 60 * 60


def _ticker_guess(topic: str) -> str | None:
    m = re.search(r"\b([A-Z]{1,5})\b", topic)
    return m.group(1) if m else None


def get_finnhub_signal(topic: str) -> dict:
    if not _KEY:
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_NO_KEY,
            status_detail="Set FINNHUB_API_KEY (free tier at finnhub.io)",
        )

    cache_key = build_key("finnhub", topic)
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        ticker = _ticker_guess(topic)
        headlines = []
        symbol = None

        if ticker:
            search = requests.get(
                f"{_BASE}/search",
                params={"q": ticker, "token": _KEY},
                timeout=10,
            )
            if search.status_code == 200:
                results = (search.json().get("result") or [])[:3]
                if results:
                    symbol = results[0].get("symbol")

        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=14)
        if symbol:
            news_resp = requests.get(
                f"{_BASE}/company-news",
                params={
                    "symbol": symbol,
                    "from": start.isoformat(),
                    "to": end.isoformat(),
                    "token": _KEY,
                },
                timeout=10,
            )
            if news_resp.status_code == 200:
                headlines = [
                    {"title": n.get("headline", ""), "source": n.get("source", "")}
                    for n in (news_resp.json() or [])[:8]
                    if n.get("headline")
                ]

        if not headlines:
            gen = requests.get(
                f"{_BASE}/news",
                params={"category": "general", "token": _KEY},
                timeout=10,
            )
            if gen.status_code != 200:
                status, detail = classify_http(gen.status_code, gen.text)
                return make_signal(
                    connected=False, active=False, status=status, status_detail=detail
                )
            topic_l = topic.lower()
            for item in gen.json() or []:
                title = item.get("headline", "")
                if title and any(w in title.lower() for w in topic_l.split() if len(w) > 3):
                    headlines.append({"title": title, "source": item.get("source", "")})
            headlines = headlines[:8]

        if not headlines:
            sig = make_signal(
                connected=True,
                active=False,
                status=STATUS_INACTIVE,
                status_detail="Finnhub: no matching market news",
            )
            set_cache(cache_key, sig, ttl_seconds=_TTL)
            return sig

        score = min(45 + len(headlines) * 6, 95)
        sig = make_signal(
            connected=True,
            active=True,
            score=float(score),
            confidence=0.85,
            status=STATUS_OK,
            status_detail=f"Finnhub: {len(headlines)} headlines",
            data={"symbol": symbol, "headlines": headlines},
        )
        set_cache(cache_key, sig, ttl_seconds=_TTL)
        return sig
    except Exception as exc:
        status, detail = classify_exception(exc)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)
