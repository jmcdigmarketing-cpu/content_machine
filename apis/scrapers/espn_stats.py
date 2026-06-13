"""ESPN public JSON search + athlete stat snippets (no API key)."""

from __future__ import annotations

from typing import Any

import requests

from apis.scrapers.base import HEADERS, get_cached, search_query_from_topic, set_cached

SEARCH_URL = "https://site.api.espn.com/apis/common/v3/search"
TTL = 60 * 60 * 2


def _search_espn(query: str, *, sport_path: str) -> list[dict[str, Any]]:
    params = {
        "query": query,
        "limit": 5,
        "type": "player",
    }
    try:
        resp = requests.get(SEARCH_URL, params=params, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return []
        data = resp.json()
    except (requests.RequestException, ValueError):
        return []

    hits = []
    for block in data.get("results") or []:
        if block.get("type") not in ("player", None):
            continue
        for item in block.get("contents") or block.get("items") or []:
            athlete = item.get("athlete") or item
            hits.append(
                {
                    "name": athlete.get("displayName") or athlete.get("fullName"),
                    "id": athlete.get("id"),
                    "team": (athlete.get("team") or {}).get("displayName"),
                    "position": athlete.get("position", {}).get("abbreviation")
                    if isinstance(athlete.get("position"), dict)
                    else athlete.get("position"),
                }
            )
    return hits[:3]


def _athlete_stat_line(athlete_id: str, sport: str) -> str:
    if sport == "nba":
        url = f"https://site.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{athlete_id}/stats"
    else:
        url = f"https://site.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{athlete_id}/stats"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return ""
        data = resp.json()
    except (requests.RequestException, ValueError):
        return ""

    categories = data.get("categories") or data.get("splits") or []
    if not categories:
        stats = data.get("stats") or []
        if stats:
            row = stats[0] if isinstance(stats, list) else stats
            if isinstance(row, dict):
                return str(row.get("displayValue") or row.get("summary") or "")[:200]
        return ""

    for cat in categories[:2]:
        stats = cat.get("stats") or cat.get("statistics") or []
        if stats:
            s0 = stats[0]
            if isinstance(s0, dict):
                name = s0.get("name") or s0.get("displayName")
                val = s0.get("displayValue") or s0.get("value")
                if name and val is not None:
                    return f"{name}: {val}"
    return ""


def fetch_espn_stats(topic: str, *, domain: str) -> dict[str, Any]:
    sport_path = "basketball" if domain == "nba" else "football"
    cache_key = f"{domain}::{search_query_from_topic(topic)}"
    cached = get_cached("espn_stats", cache_key, ttl_seconds=TTL)
    if cached is not None:
        return cached

    query = search_query_from_topic(topic)
    players = _search_espn(query, sport_path=sport_path)
    lines: list[str] = []
    for p in players[:2]:
        name = p.get("name") or "Unknown"
        team = p.get("team") or ""
        line = f"{name}" + (f" ({team})" if team else "")
        stat = ""
        if p.get("id"):
            stat = _athlete_stat_line(str(p["id"]), domain)
        if stat:
            line += f" — {stat}"
        lines.append(line)

    result = {
        "query": query,
        "lines": lines,
        "source": "ESPN API",
        "domain": domain,
    }
    set_cached("espn_stats", cache_key, result)
    return result
