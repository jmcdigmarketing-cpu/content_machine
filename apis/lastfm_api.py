"""Last.fm — charts, tags, similar artists (free API key)."""

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

_KEY = os.getenv("LASTFM_API_KEY", "").strip()
_BASE = "http://ws.audioscrobbler.com/2.0/"
_TTL = 6 * 60 * 60


def _search_query(topic: str) -> str:
    text = re.sub(r"\b(song|album|artist|music|lyrics|20\d{2})\b", "", topic, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()[:64] or topic[:64]


def get_lastfm_signal(topic: str) -> dict:
    if not _KEY:
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_NO_KEY,
            status_detail="Set LASTFM_API_KEY (free at last.fm/api)",
        )

    cache_key = build_key("lastfm", topic)
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    query = _search_query(topic)
    try:
        track_resp = requests.get(
            _BASE,
            params={
                "method": "track.search",
                "track": query,
                "api_key": _KEY,
                "format": "json",
                "limit": 6,
            },
            timeout=12,
        )
        if track_resp.status_code != 200:
            status, detail = classify_http(track_resp.status_code, track_resp.text)
            return make_signal(connected=False, active=False, status=status, status_detail=detail)

        tracks = (track_resp.json().get("results") or {}).get("trackmatches", {}).get("track") or []
        if isinstance(tracks, dict):
            tracks = [tracks]

        artist_resp = requests.get(
            _BASE,
            params={
                "method": "artist.search",
                "artist": query,
                "api_key": _KEY,
                "format": "json",
                "limit": 4,
            },
            timeout=12,
        )
        artists = []
        if artist_resp.status_code == 200:
            artists = (artist_resp.json().get("results") or {}).get("artistmatches", {}).get(
                "artist"
            ) or []
            if isinstance(artists, dict):
                artists = [artists]

        if not tracks and not artists:
            sig = make_signal(
                connected=True,
                active=False,
                status=STATUS_INACTIVE,
                status_detail="Last.fm: no music match",
            )
            set_cache(cache_key, sig, ttl_seconds=_TTL)
            return sig

        titles = [t.get("name", "") for t in tracks if t.get("name")]
        score = min(38 + len(tracks) * 8 + len(artists) * 6, 92)
        sig = make_signal(
            connected=True,
            active=True,
            score=float(score),
            confidence=0.84,
            status=STATUS_OK,
            status_detail=f"Last.fm: {len(tracks)} tracks, {len(artists)} artists",
            data={"tracks": tracks[:6], "artists": artists[:4], "titles": titles},
        )
        set_cache(cache_key, sig, ttl_seconds=_TTL)
        return sig
    except Exception as exc:
        status, detail = classify_exception(exc)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)
