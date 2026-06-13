"""AniList GraphQL — anime trending, popularity, airing (official-grade, free)."""

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

_GQL = "https://graphql.anilist.co"
_TTL = 6 * 60 * 60

_QUERY = """
query ($search: String) {
  Page(page: 1, perPage: 6) {
    media(search: $search, type: ANIME, sort: [POPULARITY_DESC]) {
      id
      title { romaji english }
      popularity
      trending
      status
      season
      seasonYear
    }
  }
}
"""


def _search_query(topic: str) -> str:
    text = re.sub(r"\b(anime|manga|episode|season|review)\b", "", topic, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()[:64] or topic[:64]


def _anilist_fetch(topic: str) -> dict:
    resp = requests.post(
        _GQL,
        json={"query": _QUERY, "variables": {"search": _search_query(topic)}},
        timeout=12,
    )
    if resp.status_code != 200:
        status, detail = classify_http(resp.status_code, resp.text)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)

    media = (resp.json().get("data") or {}).get("Page", {}).get("media") or []
    if not media:
        return make_signal(
            connected=True,
            active=False,
            status=STATUS_INACTIVE,
            status_detail="AniList: no anime match",
        )

    titles = []
    for m in media:
        t = m.get("title") or {}
        titles.append(t.get("english") or t.get("romaji") or "")
    trending = sum(int(m.get("trending") or 0) for m in media)
    score = min(40 + trending * 2 + len(media) * 8, 95)
    return make_signal(
        connected=True,
        active=True,
        score=float(score),
        confidence=0.9,
        status=STATUS_OK,
        status_detail=f"AniList: {len(media)} titles",
        data={"media": media, "titles": titles},
    )


def get_anilist_signal(topic: str) -> dict:
    cache_key = build_key("anilist", topic)
    cached = get_cached(cache_key)
    if cached is not None:
        return cached
    try:
        sig = _anilist_fetch(topic)
        set_cache(cache_key, sig, ttl_seconds=_TTL)
        return sig
    except Exception as exc:
        status, detail = classify_exception(exc)
        return make_signal(connected=False, active=False, status=status, status_detail=detail)
