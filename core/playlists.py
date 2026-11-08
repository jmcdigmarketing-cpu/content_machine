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

#1736 (B06.15, wave 147): a playlist plays newest first - a new video goes in at the top, where
the playlist page and its autoplay start - except the countdown, which plays in day order. A long
video (over three minutes) also joins the `long_form` row's playlist ("Full Videos"), so a long
video's autoplay goes on to the next long one, not to a Short.

#1989 (wave 148): a playlist that carries a series (the GTA countdown) keeps the series on top in
day order - every other new video goes in just after it, not above it. #1987: the videos added
before #1736 are moved into that order a little each day (`reorder_playlists`, from the worker,
`PLAYLIST_ORDER_UNITS` a day - each move is 50 units).
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


LONG_SECONDS = 185.0  # #1736: a Short is at most three minutes (`week_compile` reads it so)


def is_long_video(path: str) -> bool:
    """#1736: the file runs past three minutes - a long video, not a Short. False unread."""
    try:
        from video.channel_intro import _probe_duration

        seconds = _probe_duration(path) if path and os.path.isfile(path) else None
    except Exception as exc:
        logger.debug("playlist length unread: %s", exc)
        return False
    return bool(seconds and seconds > LONG_SECONDS)


def long_playlists(channel_id: str) -> list[str]:
    """#1736: the playlists every long video joins (`"long_form": true` rows)."""
    return [str(row["name"]) for row in playlist_map(channel_id) if row.get("long_form")]


def playlists_for(
    channel_id: str, title: str, *, topic: str = "", tags: list[str] | None = None
) -> list[str]:
    """[specific, parent] for the first matching playlist, else []."""
    text = " ".join([title or "", topic or "", " ".join(tags or [])]).lower()
    for row in playlist_map(channel_id):
        if row.get("long_form"):
            continue
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


def order_units() -> int:
    """#1987: `PLAYLIST_ORDER_UNITS` (default 1000 - twenty moves a day); 0 turns it off."""
    try:
        return max(0, int(os.getenv("PLAYLIST_ORDER_UNITS", "") or 1000))
    except ValueError:
        return 1000


ORDER_KEEP_UPLOADS = 2  # #1987: the day's units always leave two uploads


def order_budget() -> int:
    """#1987: the units a reorder may spend now - `order_units()`, less what two uploads need."""
    try:
        from apis.youtube_quota import UNITS_VIDEO_INSERT, get_usage_summary

        left = int(get_usage_summary().get("remaining") or 0)
    except Exception as exc:
        logger.debug("quota unread for the playlist order: %s", exc)
        return 0
    return max(0, min(order_units(), left - ORDER_KEEP_UPLOADS * UNITS_VIDEO_INSERT))


def desired_order(items: list[dict[str, Any]], series: list[str]) -> list[str]:
    """#1987: the playlist's item ids in binge order - its series videos first in day order, then
    the rest newest first by the video's publish time (ties keep their place)."""
    rank = {video: i for i, video in enumerate(series)}
    block = sorted((i for i in items if i["video_id"] in rank), key=lambda i: rank[i["video_id"]])
    rest = sorted(
        (i for i in items if i["video_id"] not in rank),
        key=lambda i: (str(i.get("published_at") or ""), -int(i.get("position") or 0)),
        reverse=True,
    )
    return [str(i["id"]) for i in [*block, *rest]]


def order_moves(current: list[str], desired: list[str]) -> list[tuple[str, int]]:
    """#1987: the (item id, position) moves, top first, that turn `current` into `desired` -
    each takes the item that belongs at a position to it. A reversed list of n takes n - 1."""
    now = list(current)
    moves: list[tuple[str, int]] = []
    for position, item in enumerate(desired):
        if position < len(now) and now[position] == item:
            continue
        if item in now:
            now.remove(item)
        now.insert(position, item)
        moves.append((item, position))
    return moves


def _playlist_items(service, playlist_id: str) -> list[dict[str, Any]]:
    """The playlist's items by position: {id, video_id, published_at, position}. 1 unit a page."""
    out: list[dict[str, Any]] = []
    token = None
    for _page in range(10):
        record_call("playlistItems.list")
        page = (
            service.playlistItems()
            .list(
                part="snippet,contentDetails",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=token,
            )
            .execute()
        )
        for item in page.get("items") or []:
            details = item.get("contentDetails") or {}
            out.append({
                "id": str(item.get("id") or ""),
                "video_id": str(details.get("videoId") or ""),
                "published_at": str(details.get("videoPublishedAt") or ""),
                "position": int((item.get("snippet") or {}).get("position") or 0),
            })  # fmt: skip
        token = page.get("nextPageToken")
        if not token:
            break
    return sorted((i for i in out if i["id"] and i["video_id"]), key=lambda i: i["position"])


def reorder_playlists(
    channel_id: str,
    service,
    *,
    budget: int,
    store_path: str | None = None,
    today: str | None = None,
) -> list[str]:
    """#1987 (B06.15, wave 148): move each playlist's items toward `desired_order`, the series
    playlists first, then the biggest, within `budget` units - once a day. Records how many moves
    each playlist still needs. Returns what was done, for the worker's log. Never raises."""
    from datetime import date

    lines: list[str] = []
    try:
        if budget < 50 or not service:
            return []
        path = store_path or store_path_for(channel_id)
        data = _load(path)
        day = today or date.today().isoformat()
        if (data.get("order") or {}).get("day") == day:
            return []
        ids: dict[str, str] = dict(data.get("ids") or {})
        series: dict[str, list[str]] = dict(data.get("series") or {})
        sizes: dict[str, int] = {}
        for names in (data.get("added") or {}).values():
            for name in names or []:
                sizes[name] = sizes.get(name, 0) + 1
        names = sorted(ids, key=lambda n: (not series.get(n), -sizes.get(n, 0), n))
        spent, moved, left = 0, 0, {}
        for name in names:
            items = _playlist_items(service, ids[name])
            spent += 1 + len(items) // 50
            moves = order_moves(
                [i["id"] for i in items], desired_order(items, series.get(name) or [])
            )
            by_id = {i["id"]: i for i in items}
            done = 0
            for item_id, position in moves:
                if spent + 50 > budget:
                    break
                record_call("playlistItems.update")
                service.playlistItems().update(part="snippet", body={"id": item_id, "snippet": {
                    "playlistId": ids[name], "position": position,
                    "resourceId": {"kind": "youtube#video", "videoId": by_id[item_id]["video_id"]},
                }}).execute()  # fmt: skip
                spent += 50
                done += 1
            moved += done
            left[name] = len(moves) - done
            if done:
                lines.append(f"{name}: {done} moved, {left[name]} to go")
        data["order"] = {"day": day, "moved": moved, "left": left}
        _save(path, data)
    except Exception as exc:
        logger.warning("playlist order stopped for %s: %s", channel_id, exc)
    return lines


def order_line(channel_id: str) -> str:
    """#1987: what the playlists' order still needs, from the last day's run - "" before one."""
    order = _load(store_path_for(channel_id)).get("order") or {}
    left = {k: int(v) for k, v in (order.get("left") or {}).items() if int(v or 0) > 0}
    if not order:
        return ""
    if not left:
        return f"Playlist order (#1987): every playlist newest first (checked {order.get('day')})."
    parts = ", ".join(f"{name} {n}" for name, n in sorted(left.items(), key=lambda kv: -kv[1]))
    return (f"Playlist order (#1987): {sum(left.values())} moves to go - {parts} "
            f"({order.get('moved', 0)} moved on {order.get('day')}).")  # fmt: skip


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
    """#2022, live 11-07: two writers (an upload adding its video, `ops playlists --apply`
    making two playlists) each saved what they had read - the "Picks, graded" id was lost while
    the playlist stood on YouTube, and the next try would have made a second one. A save now
    keeps every id and every recorded add already on disk."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    disk = _load(path)
    data = dict(data)
    data["ids"] = {**dict(disk.get("ids") or {}), **dict(data.get("ids") or {})}
    added = {key: list(value or []) for key, value in dict(disk.get("added") or {}).items()}
    for video, names in dict(data.get("added") or {}).items():
        added[video] = sorted({*added.get(video, []), *(names or [])})
    if added:
        data["added"] = added
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def _reauth_note(channel_id: str) -> str:
    return (
        "playlists need the YouTube manage permission - run "
        f"py -m youtube.oauth_setup --channel {channel_id} once"
    )


def _channel_playlists(service) -> dict[str, str]:
    """{title: id} of the channel's own playlists (1 unit a page of 50). Never raises."""
    found: dict[str, str] = {}
    token = None
    try:
        for _page in range(4):
            record_call("playlists.list")
            kwargs: dict[str, Any] = {"part": "snippet", "mine": True, "maxResults": 50}
            if token:
                kwargs["pageToken"] = token
            resp = service.playlists().list(**kwargs).execute() or {}
            for item in resp.get("items") or []:
                title = str((item.get("snippet") or {}).get("title") or "")
                if title and item.get("id"):
                    found.setdefault(title, str(item["id"]))
            token = resp.get("nextPageToken")
            if not token:
                break
    except Exception as exc:
        logger.debug("channel playlists unread: %s", exc)
    return found


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
    # #2022: a playlist already on the channel is adopted by its title, never made twice
    on_channel = _channel_playlists(service) if any(not ids.get(n) for n in wanted) else {}
    for name in wanted:
        if ids.get(name):
            continue
        if on_channel.get(name):
            ids[name] = on_channel[name]
            data["ids"] = ids
            _save(path, data)
            logger.info("playlist %s is already on YouTube (%s) - kept", name, on_channel[name])
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
    long_form: bool = False,
) -> str:
    """Add an uploaded video to its franchise playlists, at the top (#1736); a long video to the
    long videos' playlist too. Returns a one-line note. Never raises."""
    if not service or not video_id:
        return ""
    names = playlists_for(channel_id, title, topic=topic, tags=tags)
    if long_form:
        names = list(dict.fromkeys([*long_playlists(channel_id), *names]))
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
    from core.series.countdown import countdown_playlist

    in_order = countdown_playlist(channel_id, title)  # #1855: the countdown plays day 21 to 1
    series: dict[str, list[str]] = dict(data.get("series") or {})
    for name in names:
        playlist_id = ids.get(name)
        if not playlist_id:
            notes.append(f"{name}: no playlist yet (ops playlists --apply)")
            continue
        if name in done:
            continue
        snippet: dict[str, Any] = {
            "playlistId": playlist_id,
            "resourceId": {"kind": "youtube#video", "videoId": video_id},
        }
        # #1855: the countdown in day order; #1736: everything else newest first - #1989: just
        # after a series block, which a video at the top would split (a playlist with no series: 0)
        snippet["position"] = len(series.get(name) or [])
        try:
            record_call("playlistItems.insert")  # wave 113: it booked nothing
            try:
                service.playlistItems().insert(part="snippet", body={"snippet": snippet}).execute()
            except Exception as exc:
                if name == in_order:
                    raise
                # a playlist sorted by YouTube refuses a position: added at its end instead
                logger.info("playlist %s refused the top (%s) - added at the end", name, exc)
                snippet.pop("position", None)
                record_call("playlistItems.insert")
                service.playlistItems().insert(part="snippet", body={"snippet": snippet}).execute()
        except Exception as exc:
            logger.warning("playlist add failed (%s -> %s): %s", video_id, name, exc)
            notes.append(f"{name}: {exc}")
            continue
        done.add(name)
        if name == in_order:
            series[name] = [*(series.get(name) or []), video_id]
        notes.append(f"added to {name}")
    added[video_id] = sorted(done)
    data["added"] = added
    if series:
        data["series"] = series
    try:
        _save(path, data)
    except OSError as exc:
        logger.debug("playlist store not saved: %s", exc)
    return "; ".join(notes)
