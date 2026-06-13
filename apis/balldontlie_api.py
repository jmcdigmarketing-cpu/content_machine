"""
BALLDONTLIE official API — NBA/NFL/MMA stats (replaces fragile HTML scrapes when keyed).

https://www.balldontlie.io/openapi.yml
"""

from __future__ import annotations

import os
import re
from typing import Any

import requests

from apis.cache_manager import build_key, get_cached, set_cache
from apis.scrapers.base import detect_stat_domains
from apis.signal_contract import STATUS_NO_KEY, STATUS_OK, classify_exception, make_signal

BASE_URL = "https://api.balldontlie.io"
_API_KEY = os.getenv("BALLDONTLIE_API_KEY", "").strip()
_TTL = 6 * 60 * 60
_ENABLED = os.getenv("BALLDONTLIE_ENABLED", "true").lower() not in ("0", "false", "no")


def _headers() -> dict[str, str]:
    return {"Authorization": _API_KEY}


def _get(path: str, params: dict | None = None) -> dict | None:
    if not _API_KEY:
        return None
    try:
        resp = requests.get(
            f"{BASE_URL}{path}",
            headers=_headers(),
            params=params or {},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception:
        return None


def _search_term(topic: str) -> str:
    words = re.findall(r"[A-Za-z][a-z]+", topic)
    if len(words) >= 2:
        return " ".join(words[:3])
    return topic.strip()[:48]


def fetch_nba_player_stats(topic: str) -> list[str]:
    search = _search_term(topic)
    data = _get("/nba/v1/players", {"search": search, "per_page": 3})
    if not data:
        return []
    players = data.get("data") or []
    if not players:
        return []
    player = players[0]
    pid = player.get("id")
    name = f"{player.get('first_name', '')} {player.get('last_name', '')}".strip()
    stats = _get("/nba/v1/stats", {"player_ids[]": pid, "per_page": 5})
    if not stats:
        return [f"{name} (BALLDONTLIE player match)"]
    lines: list[str] = []
    for row in (stats.get("data") or [])[:3]:
        game = row.get("game") or {}
        pts = row.get("pts")
        reb = row.get("reb")
        ast = row.get("ast")
        when = game.get("date", "")
        lines.append(f"{name} {when}: {pts} PTS / {reb} REB / {ast} AST")
    return lines or [f"{name} (BALLDONTLIE)"]


def fetch_nfl_player_stats(topic: str) -> list[str]:
    search = _search_term(topic)
    data = _get("/nfl/v1/players", {"search": search, "per_page": 3})
    if not data:
        return []
    players = data.get("data") or []
    if not players:
        return []
    player = players[0]
    name = f"{player.get('first_name', '')} {player.get('last_name', '')}".strip()
    return [f"{name} (BALLDONTLIE NFL player match)"]


def fetch_mma_context(topic: str) -> list[str]:
    search = _search_term(topic)
    data = _get("/mma/v1/fighters", {"search": search, "per_page": 2})
    if not data:
        return []
    fighters = data.get("data") or []
    lines = []
    for f in fighters[:2]:
        name = f.get("full_name") or f.get("name") or ""
        weight = f.get("weight_class", "")
        if name:
            lines.append(f"{name} {weight}".strip())
    return lines


def gather_balldontlie_context(topic: str) -> dict[str, Any]:
    if not _ENABLED or not _API_KEY:
        return {"connected": False, "lines": [], "source": "balldontlie"}

    cache_key = build_key("balldontlie_ctx", topic)
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    domains = detect_stat_domains(topic)
    lines: list[str] = []
    if "nba" in domains:
        lines.extend(fetch_nba_player_stats(topic))
    if "nfl" in domains:
        lines.extend(fetch_nfl_player_stats(topic))
    if "mma" in domains or any(k in topic.lower() for k in ("ufc", "mma", "fight")):
        lines.extend(fetch_mma_context(topic))

    result = {
        "connected": True,
        "lines": lines[:10],
        "source": "balldontlie",
        "domains": domains,
    }
    set_cache(cache_key, result, ttl_seconds=_TTL)
    return result


def get_balldontlie_stats_signal(topic: str) -> dict:
    if not _ENABLED:
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_NO_KEY,
            status_detail="BALLDONTLIE_ENABLED=false",
        )
    if not _API_KEY:
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_NO_KEY,
            status_detail="Set BALLDONTLIE_API_KEY in .env",
        )

    try:
        ctx = gather_balldontlie_context(topic)
        lines = ctx.get("lines") or []
        if not lines:
            return make_signal(
                connected=True,
                active=False,
                score=0,
                confidence=0.5,
                data=ctx,
                status_detail="No BALLDONTLIE match for topic",
            )
        score = min(55 + len(lines) * 12, 95)
        return make_signal(
            connected=True,
            active=True,
            score=float(score),
            confidence=0.88,
            data=ctx,
            status=STATUS_OK,
            status_detail=f"{len(lines)} lines from BALLDONTLIE API",
        )
    except Exception as exc:
        status, detail = classify_exception(exc)
        return make_signal(
            connected=False,
            active=False,
            status=status,
            status_detail=detail,
        )
