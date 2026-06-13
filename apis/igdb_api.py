"""IGDB — game metadata + popularity (Twitch OAuth, includes PopScore primitives)."""

from __future__ import annotations

import os
import re
import time

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

_CLIENT_ID = os.getenv("IGDB_CLIENT_ID", os.getenv("TWITCH_CLIENT_ID", "")).strip()
_CLIENT_SECRET = os.getenv("IGDB_CLIENT_SECRET", os.getenv("TWITCH_CLIENT_SECRET", "")).strip()
_BASE = "https://api.igdb.com/v4"
_TTL = 6 * 60 * 60
_TOKEN: tuple[str, float] | None = None


def _app_token() -> str | None:
    global _TOKEN
    if not _CLIENT_ID or not _CLIENT_SECRET:
        return None
    if _TOKEN and time.time() < _TOKEN[1]:
        return _TOKEN[0]
    try:
        resp = requests.post(
            "https://id.twitch.tv/oauth2/token",
            params={
                "client_id": _CLIENT_ID,
                "client_secret": _CLIENT_SECRET,
                "grant_type": "client_credentials",
            },
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        token = data.get("access_token")
        expires = int(data.get("expires_in", 3600))
        if token:
            _TOKEN = (token, time.time() + expires - 60)
            return token
    except Exception:
        return None
    return None


def _search_query(topic: str) -> str:
    text = re.sub(r"\b(game|gaming|meta|review|20\d{2})\b", "", topic, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()[:48] or topic[:48]


def get_igdb_signal(topic: str) -> dict:
    if not _CLIENT_ID or not _CLIENT_SECRET:
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_NO_KEY,
            status_detail="Set IGDB_CLIENT_ID + IGDB_CLIENT_SECRET (Twitch dev app)",
        )

    cache_key = build_key("igdb", topic)
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    token = _app_token()
    if not token:
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_NO_KEY,
            status_detail="IGDB OAuth token failed",
        )

    headers = {
        "Client-ID": _CLIENT_ID,
        "Authorization": f"Bearer {token}",
    }
    query = _search_query(topic).replace('"', "")

    try:
        body = (
            f'search "{query}"; '
            "fields name,popularity,total_rating,first_release_date; "
            "limit 6;"
        )
        resp = requests.post(f"{_BASE}/games", headers=headers, data=body, timeout=14)
        if resp.status_code != 200:
            status, detail = classify_http(resp.status_code, resp.text)
            return make_signal(connected=False, active=False, status=status, status_detail=detail)

        games = resp.json() or []
        if not games:
            sig = make_signal(
                connected=True,
                active=False,
                status=STATUS_INACTIVE,
                status_detail="IGDB: no game match",
            )
            set_cache(cache_key, sig, ttl_seconds=_TTL)
            return sig

        pop_sum = sum(float(g.get("popularity") or 0) for g in games)
        titles = [g.get("name", "") for g in games if g.get("name")]
        score = min(40 + pop_sum / 2 + len(games) * 6, 95)
        sig = make_signal(
            connected=True,
            active=True,
            score=float(score),
            confidence=0.88,
            status=STATUS_OK,
            status_detail=f"IGDB PopScore: {len(games)} games",
            data={"games": games, "titles": titles, "popularity_sum": pop_sum},
        )
        set_cache(cache_key, sig, ttl_seconds=_TTL)
        return sig
    except Exception as exc:
        status, detail = classify_exception(exc)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)
