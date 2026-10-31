"""Clip index tags: team, player, and game (#1043).

Run 155 cut four untagged Madden clips for a Chargers video. A topic that names
a team or a known player uses only clips tagged with that subject. A topic that
names none keeps the folder.
"""

from __future__ import annotations

import json
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
    """`paths` for the topic's team or player. No subject: the list unchanged.

    Clips tagged with the subject when there are any; else the untagged ones - never a clip
    tagged with another team or player. Review of 2026-10-16: leaving untagged clips out made
    "Tennessee Titans at Indianapolis Colts" keep 0 of 13 Madden clips and "Cleveland
    Cavaliers at Orlando Magic" 0 of 72 2K clips, because the operator's files carry no team.
    """
    wanted = subjects_in(topic)
    if not wanted:
        return list(paths)
    clips = ((index if index is not None else load_index()) or {}).get("clips") or {}
    if not isinstance(clips, dict):
        clips = {}
    matched: list[str] = []
    untagged: list[str] = []
    for path in paths:
        tags = _tag_set(path, _meta_for(path, clips))
        if tags & wanted:
            matched.append(path)
        elif not tags:
            untagged.append(path)
    return matched or untagged


# L5 (look_and_feel.md, wave 135): an untagged FC Barcelona squad menu sat behind the Kane, Real
# Madrid and Man City Shorts. A menu or UI clip backs only a story about its own game: one tagged
# "ui" or "menu", named like one, or measured near still (mean frame change under MOTION_UI; the
# menu capture measured 4.5, gameplay 7.9-47 on 10-30).
MOTION_UI = 6.0
_UI_NAME = re.compile(
    r"\b(menu|menus|ui|lobby|loading|lineup|squad|roster|ratings|team select|select screen)\b",
    re.IGNORECASE,
)


def is_ui_clip(path: str, meta: dict[str, Any] | None = None) -> bool:
    meta = meta or {}
    tags = {str(t).casefold() for t in meta.get("tags") or []}
    if tags & {"ui", "menu"}:
        return True
    if _UI_NAME.search(_words(os.path.basename(path))):
        return True
    motion = meta.get("motion")
    return isinstance(motion, (int, float)) and float(motion) < MOTION_UI


def without_ui(paths: list[str], topic: str, index: dict[str, Any] | None = None) -> list[str]:
    """L5: `paths` less their menu/UI clips, unless the topic names that clip's game."""
    clips = ((index if index is not None else load_index()) or {}).get("clips") or {}
    if not isinstance(clips, dict):
        clips = {}
    from assets.local_provider import _keyword_choose_folder

    out: list[str] = []
    for path in paths:
        meta = _meta_for(path, clips)
        if is_ui_clip(path, meta) and not _keyword_choose_folder(topic, [os.path.dirname(path)]):
            continue
        out.append(path)
    return out


def measure_motion(path: str, *, frames: int = 8, size: tuple[int, int] = (64, 36)) -> float | None:
    """Mean change between frames a second apart (0-255) - a menu is near still. None when the
    file cannot be read."""
    import subprocess

    w, h = size
    try:
        proc = subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-ss", "2", "-i", path, "-frames:v", str(frames),
             "-vf", f"fps=1,scale={w}:{h},format=gray", "-f", "rawvideo", "-"],
            capture_output=True, stdin=subprocess.DEVNULL, timeout=60, check=False,
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError):
        return None
    data, cell = proc.stdout, w * h
    count = len(data) // cell
    if count < 2:
        return None
    total = sum(
        abs(data[i * cell + j] - data[(i - 1) * cell + j])
        for i in range(1, count)
        for j in range(cell)
    )
    return round(total / ((count - 1) * cell), 2)


def canonical_team(name: str) -> str:
    """A nickname or a full name, as the index stores it. Empty when it is neither."""
    raw = (name or "").strip()
    if not raw:
        return ""
    from apis.nba_teams import NBA_TEAM_NAMES
    from apis.nfl_entities import NFL_TEAM_NAMES

    key = raw.casefold()
    if key in NFL_TEAM_NAMES:
        return NFL_TEAM_NAMES[key]
    if key in NBA_TEAM_NAMES:
        return NBA_TEAM_NAMES[key]
    for full in (*NFL_TEAM_NAMES.values(), *NBA_TEAM_NAMES.values()):
        if full.casefold() == key:
            return full
    return ""


def _row_key(path: str, clips: dict[Any, Any]) -> str | None:
    if path in clips and isinstance(clips[path], dict):
        return path
    try:
        want = os.path.normcase(os.path.abspath(path))
    except (OSError, ValueError):
        return None
    for key, meta in clips.items():
        try:
            if os.path.normcase(os.path.abspath(str(key))) == want and isinstance(meta, dict):
                return str(key)
        except (OSError, ValueError):
            continue
    return None


def _write_index(path: str, data: dict[str, Any]) -> None:
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    temporary = os.path.join(directory, os.path.basename(path) + ".tmp")
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    os.replace(temporary, path)


def tag_clip(path: str, team: str, *, index_path: str, apply: bool) -> dict[str, Any]:
    """Write `teams` on a clip already in the index. A missing row is not created.

    Without `apply` the row is left as it is and the result says what would be written.
    """
    from core.owned_beats import load_clip_index

    full = canonical_team(team)
    if not full:
        return {"ok": False, "error": f"unknown team {team!r}", "applied": False, "path": path}
    data = load_clip_index(index_path)
    clips = data.get("clips") if isinstance(data, dict) else None
    if not isinstance(clips, dict):
        clips = {}
        data = {"clips": clips}
    key = _row_key(path, clips)
    if key is None:
        return {"ok": False, "error": "not in the library", "applied": False, "path": path}
    row = dict(clips[key])
    teams = [str(item).strip() for item in (row.get("teams") or []) if str(item).strip()]
    if full not in teams:
        teams.append(full)
    if apply:
        row["teams"] = teams
        clips[key] = row
        data["clips"] = clips
        _write_index(index_path, data)
    return {"ok": True, "team": full, "applied": bool(apply), "path": key, "error": ""}
