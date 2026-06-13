"""TrendingNow.games — hourly Steam trend feed (free JSON, no auth)."""

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

_FEED = "https://trendingnow.games/api/public/feeds/trending"
_TTL = 60 * 60
_UA = {"User-Agent": "ContentMachine/1.0"}


def _topic_hint(topic: str) -> str:
    text = re.sub(r"\b(game|gaming|steam|20\d{2})\b", "", topic, flags=re.I)
    return re.sub(r"\s+", " ", text).strip().lower()


def get_trendingnow_signal(topic: str) -> dict:
    cache_key = build_key("trendingnow", topic)
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    hint = _topic_hint(topic)
    try:
        resp = requests.get(_FEED, headers=_UA, timeout=12)
        if resp.status_code != 200:
            status, detail = classify_http(resp.status_code, resp.text)
            return make_signal(connected=False, active=False, status=status, status_detail=detail)

        payload = resp.json()
        games = (
            payload
            if isinstance(payload, list)
            else payload.get("games") or payload.get("data") or []
        )
        if not games:
            sig = make_signal(
                connected=True,
                active=False,
                status=STATUS_INACTIVE,
                status_detail="TrendingNow: empty feed",
            )
            set_cache(cache_key, sig, ttl_seconds=_TTL)
            return sig

        matched = []
        for i, g in enumerate(games[:20]):
            if not isinstance(g, dict):
                continue
            name = (g.get("name") or g.get("title") or "").lower()
            if hint and (hint in name or any(w in name for w in hint.split() if len(w) > 3)):
                matched.append({**g, "rank": i + 1})

        top_names = [
            (g.get("name") or g.get("title") or "") for g in games[:10] if isinstance(g, dict)
        ]
        if matched:
            score = min(55 + sum(20 - min(m.get("rank", 20), 19) for m in matched), 95)
            detail = f"TrendingNow: rank {[m.get('rank') for m in matched[:3]]}"
        elif hint:
            score = 25
            detail = "TrendingNow: feed ok, topic not in top 20"
        else:
            score = min(40 + len(games), 70)
            detail = f"TrendingNow: {len(games)} trending games"

        sig = make_signal(
            connected=True,
            active=score >= 30,
            score=float(score),
            confidence=0.8,
            status=STATUS_OK if score >= 30 else STATUS_INACTIVE,
            status_detail=detail,
            data={"matched": matched, "top": top_names[:10]},
        )
        set_cache(cache_key, sig, ttl_seconds=_TTL)
        return sig
    except Exception as exc:
        status, detail = classify_exception(exc)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)
