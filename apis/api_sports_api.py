"""API-SPORTS — soccer, MMA, multi-league REST (generous free tier)."""

from __future__ import annotations

import os
import re
from typing import Any

import requests

from apis.cache_manager import build_key, get_cached, set_cache
from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_NO_KEY,
    STATUS_OK,
    classify_exception,
    make_signal,
)

_KEY = os.getenv("API_SPORTS_KEY", "").strip()
_BASE = os.getenv("API_SPORTS_BASE", "https://v3.football.api-sports.io")
_TTL = 3 * 60 * 60


def _headers() -> dict[str, str]:
    return {"x-apisports-key": _KEY}


def _detect_league(topic: str) -> str:
    t = topic.lower()
    if any(k in t for k in ("ufc", "mma", "fight", "boxing")):
        return "mma"
    if any(k in t for k in ("nba", "basketball", "nfl", "football", "mlb", "soccer", "premier")):
        return "sports"
    return "football"


def _search_query(topic: str) -> str:
    text = re.sub(r"\b(20\d{2}|vs|preview|analysis)\b", "", topic, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()[:48] or topic[:48]


def gather_api_sports_context(topic: str) -> dict[str, Any]:
    if not _KEY:
        return {"connected": False, "lines": [], "source": "api_sports"}

    cache_key = build_key("api_sports_ctx", topic)
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    query = _search_query(topic)
    lines: list[str] = []
    try:
        resp = requests.get(
            f"{_BASE}/teams",
            params={"search": query},
            headers=_headers(),
            timeout=12,
        )
        if resp.status_code == 200:
            teams = (resp.json().get("response") or [])[:4]
            for team in teams:
                name = (team.get("team") or {}).get("name", "")
                country = (team.get("team") or {}).get("country", "")
                if name:
                    lines.append(f"{name} ({country}) — API-SPORTS")

        result = {
            "connected": True,
            "lines": lines[:8],
            "source": "api_sports",
            "league_hint": _detect_league(topic),
        }
        set_cache(cache_key, result, ttl_seconds=_TTL)
        return result
    except Exception:
        return {"connected": False, "lines": [], "source": "api_sports"}


def get_api_sports_signal(topic: str) -> dict:
    if not _KEY:
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_NO_KEY,
            status_detail="Set API_SPORTS_KEY (api-sports.io)",
        )

    try:
        ctx = gather_api_sports_context(topic)
        lines = ctx.get("lines") or []
        if not lines:
            return make_signal(
                connected=True,
                active=False,
                status=STATUS_INACTIVE,
                status_detail="API-SPORTS: no team/league match",
            )
        score = min(50 + len(lines) * 12, 90)
        return make_signal(
            connected=True,
            active=True,
            score=float(score),
            confidence=0.86,
            status=STATUS_OK,
            status_detail=f"API-SPORTS: {len(lines)} matches",
            data=ctx,
        )
    except Exception as exc:
        status, detail = classify_exception(exc)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)
