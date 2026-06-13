"""nflverse (nfl_data_py) + pybaseball — community-maintained NFL/MLB stats."""

from __future__ import annotations

import re
from typing import Any

from apis.cache_manager import build_key, get_cached, set_cache
from apis.signal_contract import make_signal

_TTL = 12 * 60 * 60


def _player_name(topic: str) -> str:
    words = re.findall(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?", topic)
    if words:
        return words[0]
    parts = re.findall(r"[A-Za-z]{3,}", topic)
    return " ".join(parts[:2]) if len(parts) >= 2 else (parts[0] if parts else "")


def _is_nfl_topic(topic: str) -> bool:
    t = topic.lower()
    return any(
        k in t
        for k in (
            "nfl",
            "quarterback",
            "touchdown",
            "super bowl",
            "chiefs",
            "cowboys",
            "eagles",
            "packers",
        )
    )


def _is_mlb_topic(topic: str) -> bool:
    t = topic.lower()
    return any(
        k in t for k in ("mlb", "baseball", "home run", "yankees", "dodgers", "ohtani", "pitcher")
    )


def gather_nflverse_context(topic: str) -> dict[str, Any]:
    cache_key = build_key("nflverse", topic)
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    if not _is_nfl_topic(topic):
        return {"connected": True, "lines": [], "source": "nflverse"}

    lines: list[str] = []
    try:
        import nfl_data_py as nfl  # type: ignore

        name = _player_name(topic).lower()
        players = nfl.import_players()
        if players is not None and not players.empty and name:
            hits = players[
                players["display_name"].str.lower().str.contains(name.split()[0], na=False)
            ].head(3)
            for _, row in hits.iterrows():
                lines.append(
                    f"{row.get('display_name', '')} — {row.get('position', '')} "
                    f"({row.get('latest_team', '')}) [nflverse]"
                )
    except ImportError:
        return {
            "connected": False,
            "lines": [],
            "source": "nflverse",
            "error": "nfl_data_py not installed",
        }
    except Exception as exc:
        return {"connected": False, "lines": [], "source": "nflverse", "error": str(exc)}

    result = {"connected": True, "lines": lines[:6], "source": "nflverse"}
    set_cache(cache_key, result, ttl_seconds=_TTL)
    return result


def gather_pybaseball_context(topic: str) -> dict[str, Any]:
    cache_key = build_key("pybaseball", topic)
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    if not _is_mlb_topic(topic):
        return {"connected": True, "lines": [], "source": "pybaseball"}

    lines: list[str] = []
    try:
        from pybaseball import playerid_lookup  # type: ignore

        name = _player_name(topic)
        parts = name.split()
        if len(parts) >= 2:
            ids = playerid_lookup(parts[-1], parts[0])
            if ids is not None and not ids.empty:
                row = ids.iloc[0]
                lines.append(
                    f"{parts[0]} {parts[-1]} — MLB ID {row.get('key_mlbam', '')} [pybaseball]"
                )
    except ImportError:
        return {
            "connected": False,
            "lines": [],
            "source": "pybaseball",
            "error": "pybaseball not installed",
        }
    except Exception as exc:
        return {"connected": False, "lines": [], "source": "pybaseball", "error": str(exc)}

    result = {"connected": True, "lines": lines[:6], "source": "pybaseball"}
    set_cache(cache_key, result, ttl_seconds=_TTL)
    return result


def _provider_from_context(ctx: dict[str, Any], label: str) -> dict:
    lines = ctx.get("lines") or []
    if not ctx.get("connected"):
        return make_signal(
            connected=False,
            active=False,
            status_detail=ctx.get("error") or f"{label} unavailable",
        )
    if not lines:
        return make_signal(
            connected=True,
            active=False,
            status_detail=f"{label}: no match",
        )
    score = min(55 + len(lines) * 15, 92)
    return make_signal(
        connected=True,
        active=True,
        score=float(score),
        confidence=0.82,
        status="ok",
        status_detail=f"{len(lines)} lines via {label}",
        data=ctx,
    )


def nflverse_provider(topic: str) -> dict:
    return _provider_from_context(gather_nflverse_context(topic), "nflverse")


def pybaseball_provider(topic: str) -> dict:
    return _provider_from_context(gather_pybaseball_context(topic), "pybaseball")
