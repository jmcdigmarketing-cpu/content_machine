"""Clip index tags: team, player, and game (#1043).

Run 155 cut four untagged Madden clips for a Chargers video. A topic that names
a team or a known player uses only clips tagged with that subject. A topic that
names none keeps the folder.
"""

from __future__ import annotations

import os
import re
from typing import Any

_GENERIC_FOLDERS = frozenset({"gaming", "sports", "general", "video", "backgrounds", ""})


def load_index() -> dict[str, Any]:
    from core.owned_beats import load_clip_index

    return load_clip_index()


def _words(text: str) -> str:
    return os.path.splitext(text or "")[0].replace("_", " ").replace("-", " ")


def _hits(text: str, names: dict[str, str]) -> list[str]:
    found: list[str] = []
    for nick, full in names.items():
        if re.search(rf"\b{re.escape(nick)}\b", text, re.I) and full not in found:
            found.append(full)
    return found


def _players(text: str) -> list[str]:
    from apis.nfl_entities import PLAYER_TO_TEAM

    found: list[str] = []
    for player in sorted(PLAYER_TO_TEAM, key=len, reverse=True):
        if re.search(rf"\b{re.escape(player)}\b", text, re.I) and player not in found:
            found.append(player)
    return found


def describe_clip(path: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Teams, players, and game for one clip. Stored tags win; the file name fills gaps."""
    from apis.nba_teams import NBA_TEAM_NAMES
    from apis.nfl_entities import NFL_TEAM_NAMES, PLAYER_TO_TEAM

    meta = meta or {}
    teams = [str(t).strip() for t in (meta.get("teams") or []) if str(t).strip()]
    players = [str(p).strip() for p in (meta.get("players") or []) if str(p).strip()]
    game = str(meta.get("game") or "").strip()
    blob = " ".join(
        _words(part) for part in (os.path.basename(path), os.path.basename(os.path.dirname(path)))
    )
    for team in _hits(blob, NFL_TEAM_NAMES) + _hits(blob, NBA_TEAM_NAMES):
        if team not in teams:
            teams.append(team)
    for player in _players(blob):
        if player not in players:
            players.append(player)
        side = NFL_TEAM_NAMES.get(PLAYER_TO_TEAM.get(player, ""))
        if side and side not in teams:
            teams.append(side)
    if not game:
        folder = os.path.basename(os.path.dirname(path))
        if folder.casefold() not in _GENERIC_FOLDERS:
            game = folder
    return {"teams": teams, "players": players, "game": game}


def subjects_in(topic: str) -> set[str]:
    """Team and player names the topic actually names, lower case.

    Uses the sport-cue gate in `team_names_in`, so "phone chargers" names no team.
    """
    from apis.nba_teams import team_names_in as nba_teams
    from apis.nfl_entities import NFL_TEAM_NAMES, PLAYER_TO_TEAM
    from apis.nfl_entities import team_names_in as nfl_teams

    names = {team.casefold() for team in nfl_teams(topic)}
    names.update(team.casefold() for team in nba_teams(topic))
    for player in _players(topic):
        names.add(player.casefold())
        team = NFL_TEAM_NAMES.get(PLAYER_TO_TEAM.get(player, ""))
        if team:
            names.add(team.casefold())
    return names


def _meta_for(path: str, clips: dict[Any, Any]) -> dict[str, Any]:
    if path in clips and isinstance(clips[path], dict):
        return clips[path]
    try:
        want = os.path.normcase(os.path.abspath(path))
    except (OSError, ValueError):
        return {}
    for key, meta in clips.items():
        try:
            if os.path.normcase(os.path.abspath(str(key))) == want and isinstance(meta, dict):
                return meta
        except (OSError, ValueError):
            continue
    return {}


def _tag_set(path: str, meta: dict[str, Any]) -> set[str]:
    described = describe_clip(path, meta)
    tags = {str(team).casefold() for team in described["teams"]}
    tags.update(str(player).casefold() for player in described["players"])
    return tags


def clips_for_topic(paths: list[str], topic: str, index: dict[str, Any] | None = None) -> list[str]:
    """`paths` limited to the topic's team or player. No subject: the list unchanged.

    Untagged clips are left out when the topic names a team. Run 155's four
    Madden files named no team, so a Chargers video does not cut them.
    """
    wanted = subjects_in(topic)
    if not wanted:
        return list(paths)
    clips = ((index if index is not None else load_index()) or {}).get("clips") or {}
    if not isinstance(clips, dict):
        clips = {}
    return [path for path in paths if _tag_set(path, _meta_for(path, clips)) & wanted]
