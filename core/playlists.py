"""Franchise playlists (#601): every upload lands in its franchise playlist automatically.

Operator, 2026-09-18: football, NFL, basketball, gaming, Marvel Rivals, GTA, UFC/MMA, AI
development, Twitch, plus the two most popular related niches (Minecraft, Roblox - Google
Trends). The map lives in `config/playlists.json`, most specific first; a video joins the
first playlist that matches and that playlist's parent (GTA -> GTA + Gaming), so at most two.

Creating playlists and adding videos needs the `youtube` (manage) OAuth scope. Tokens made
before #601 only have upload/read/analytics, so nothing here calls the API until the
operator re-consents once:

    py -m youtube.oauth_setup --channel tapin
    py -m scripts.ops playlists --channel tapin          # show the map and what exists
    py -m scripts.ops playlists --channel tapin --apply  # create the missing playlists

Each insert is 50 quota units. Adding is idempotent - the store records what was added, so
a healed or re-tried upload never adds the same video twice. Never raises into an upload.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from apis.youtube_quota import record_call
from core.logging import get_logger

logger = get_logger("core.playlists")

SCOPE_YOUTUBE_MANAGE = "https://www.googleapis.com/auth/youtube"
_CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "playlists.json"
)


def playlist_map(channel_id: str) -> list[dict[str, Any]]:
    try:
        with open(_CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        logger.debug("playlists.json unreadable: %s", exc)
        return []
    rows = data.get(channel_id) if isinstance(data, dict) else None
    return [r for r in rows or [] if isinstance(r, dict) and r.get("name")]


def _matches(text: str, keys: list[str]) -> bool:
    for key in keys:
        if re.search(rf"(?<![a-z0-9]){re.escape(key.lower())}(?![a-z0-9])", text):
            return True
    return False


def playlists_for(
    channel_id: str, title: str, *, topic: str = "", tags: list[str] | None = None
) -> list[str]:
    """[specific, parent] for the first matching playlist, else []."""
    text = " ".join([title or "", topic or "", " ".join(tags or [])]).lower()
    for row in playlist_map(channel_id):
        if _matches(text, [str(k) for k in row.get("keys") or []]):
            names = [str(row["name"])]
            parent = str(row.get("parent") or "")
            if parent and parent not in names:
                names.append(parent)
            return names
    return []


def missing_line(channel_id: str) -> str:
    """#1240: the playlists the map names that do not exist on YouTube, or "". None of TapIn's
    11 had been made; each upload only logged "no playlist yet"."""
    rows = playlist_map(channel_id)
    if not rows:
        return ""
    ids = _load(store_path_for(channel_id)).get("ids") or {}
    missing = [row["name"] for row in rows if not ids.get(row["name"])]
    if not missing:
        return ""
    return (
        f"Playlists: {len(missing)} of {len(rows)} not made on YouTube - "
        f"py -m scripts.ops playlists --apply --channel {channel_id} "
        f"({len(missing) * 50} quota units)"
    )


def store_path_for(channel_id: str) -> str:
    from config.paths import DATA_DIR

    return os.path.join(DATA_DIR, f"playlists_{channel_id}.json")


def _load(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(path: str, data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def _reauth_note(channel_id: str) -> str:
    return (
        "playlists need the YouTube manage permission - run "
        f"py -m youtube.oauth_setup --channel {channel_id} once"
    )


def sync_playlists(service, channel_id: str, *, store_path: str | None = None) -> list[str]:
    """Create every mapped playlist that has no id yet. Returns the names created."""
    path = store_path or store_path_for(channel_id)
    data = _load(path)
    ids: dict[str, str] = dict(data.get("ids") or {})
    wanted: list[str] = []
    for row in playlist_map(channel_id):
        for name in (row.get("name"), row.get("parent")):
            if name and name not in wanted:
                wanted.append(str(name))
    created: list[str] = []
    for name in wanted:
        if ids.get(name):
            continue
        record_call("playlists.insert")  # wave 113: it booked nothing
        try:
            resp = (
                service.playlists()
                .insert(
                    part="snippet,status",
                    body={
                        "snippet": {"title": name, "description": f"{name} Shorts."},
                        "status": {"privacyStatus": "public"},
                    },
                )
                .execute()
            )
        except Exception as exc:
            # #1584, 2026-10-25: YouTube made 9 of 11 and refused the 10th with a 429
            # (RATE_LIMIT_EXCEEDED); the command died in a traceback. The rest wait for the
            # next try (`finish_playlists`, once a day from the upload worker).
            logger.warning("playlist %s not created: %s", name, str(exc)[:160])
            break
        if resp and resp.get("id"):
            ids[name] = str(resp["id"])
            created.append(name)
            data["ids"] = ids
            _save(path, data)
    return created


def auto_create_enabled() -> bool:
    """`PLAYLISTS_AUTO_CREATE` (default on; the suite turns it off)."""
    raw = (os.getenv("PLAYLISTS_AUTO_CREATE", "true") or "true").strip().lower()
    return raw not in ("0", "false", "off", "no")


def finish_playlists(
    channel_id: str, *, service_factory=None, today: str | None = None
) -> list[str]:
    """#1584 (decision 80): create the mapped playlists still missing, one try a day - YouTube's
    insert limit refused 2 of 11 on 2026-10-25. Needs the manage scope. Returns the names
    created. Never raises."""
    from datetime import date

    try:
        if not auto_create_enabled():
            return []
        path = store_path_for(channel_id)
        data = _load(path)
        ids = data.get("ids") or {}
        names = {str(n) for row in playlist_map(channel_id)
                 for n in (row.get("name"), row.get("parent")) if n}  # fmt: skip
        day = today or date.today().isoformat()
        if not names - set(ids) or data.get("tried") == day:
            return []
        from youtube.oauth import token_has_scope

        if not token_has_scope(channel_id, SCOPE_YOUTUBE_MANAGE):
            return []
        data["tried"] = day
        _save(path, data)
        if service_factory is None:
            from youtube.oauth import get_youtube_service

            service_factory = get_youtube_service
        service = service_factory(channel_id)
        return sync_playlists(service, channel_id, store_path=path) if service else []
    except Exception as exc:
        logger.debug("playlists not finished for %s: %s", channel_id, exc)
        return []


def add_to_playlists(
    service,
    channel_id: str,
    video_id: str | None,
    *,
    title: str,
    topic: str = "",
    tags: list[str] | None = None,
    store_path: str | None = None,
) -> str:
    """Add an uploaded video to its franchise playlists. Returns a one-line note. Never raises."""
    if not service or not video_id:
        return ""
    names = playlists_for(channel_id, title, topic=topic, tags=tags)
    if not names:
        return "no franchise playlist matched"
    try:
        from youtube.oauth import token_has_scope

        if not token_has_scope(channel_id, SCOPE_YOUTUBE_MANAGE):
            return _reauth_note(channel_id)
    except Exception as exc:
        logger.debug("playlist scope check skipped: %s", exc)
        return _reauth_note(channel_id)
    path = store_path or store_path_for(channel_id)
    data = _load(path)
    ids: dict[str, str] = dict(data.get("ids") or {})
    added: dict[str, list[str]] = dict(data.get("added") or {})
    done = set(added.get(video_id) or [])
    notes: list[str] = []
    for name in names:
        playlist_id = ids.get(name)
        if not playlist_id:
            notes.append(f"{name}: no playlist yet (ops playlists --apply)")
            continue
        if name in done:
            continue
        try:
            record_call("playlistItems.insert")  # wave 113: it booked nothing
            service.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": video_id},
                    }
                },
            ).execute()
        except Exception as exc:
            logger.warning("playlist add failed (%s -> %s): %s", video_id, name, exc)
            notes.append(f"{name}: {exc}")
            continue
        done.add(name)
        notes.append(f"added to {name}")
    added[video_id] = sorted(done)
    data["added"] = added
    try:
        _save(path, data)
    except OSError as exc:
        logger.debug("playlist store not saved: %s", exc)
    return "; ".join(notes)
