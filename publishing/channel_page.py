"""The channel page (wave 159; the operator approved, 2026-11-07): `ops channel-page [--apply]`.

- #1702 (B05.6) sections: the playlists in `config/channel_page.json` ("Week in Review", "GTA",
  "UFC / MMA", "Picks, graded", "Full Videos") as single-playlist sections, each once its playlist
  exists; existing sections are kept and only the missing ones added (50 units each).
- #1703 (B05.7) the description: the config's text - what the channel covers, when it posts, a reason
  to subscribe and the AI-voice line - written with `channels.update(part=brandingSettings)`, read
  first so the keywords, country and trailer it does not change are sent back as they were.
- #1710 (B05.14) the featured video: YouTube's API has no setting for "returning subscribers"; it
  sets the trailer for visitors who have not subscribed (`brandingSettings.channel.
  unsubscribedTrailer`) to the latest public Week in Review, and the Week in Review section goes
  first so returning viewers see it at the top. The worker refreshes the trailer when a newer
  Week in Review is public (`refresh_trailer`).

The `youtube` scope is already on the token (`publishing.snippet_update.manage_scope_problem`).
"""

from __future__ import annotations

import json
import os
from typing import Any

from apis.youtube_quota import record_call
from core.logging import get_logger

logger = get_logger("publishing.channel_page")

_CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "channel_page.json"
)
DESCRIPTION_MAX = 1000


def page_config(channel_id: str) -> dict[str, Any]:
    try:
        with open(_CONFIG, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        logger.debug("channel_page.json unread: %s", exc)
        return {}
    found = data.get(channel_id) if isinstance(data, dict) else None
    return found if isinstance(found, dict) else {}


def channel_description(channel_id: str) -> str:
    """The About text with the weekly long slot filled in, cut to `DESCRIPTION_MAX` at a line."""
    from core.spaced_queue import long_slot_words

    text = str(page_config(channel_id).get("description") or "").replace(
        "{long_slot}", long_slot_words()
    )
    if len(text) <= DESCRIPTION_MAX:
        return text
    return text[:DESCRIPTION_MAX].rsplit("\n", 1)[0].rstrip()


def wanted_sections(channel_id: str, ids: dict[str, str] | None = None) -> list[tuple[str, str]]:
    """(name, playlist id) for each configured section whose playlist exists, in order."""
    if ids is None:
        from core.playlists import _load, store_path_for

        ids = dict(_load(store_path_for(channel_id)).get("ids") or {})
    return [
        (name, ids[name]) for name in page_config(channel_id).get("sections") or [] if ids.get(name)
    ]


def missing_sections(
    existing: list[dict[str, Any]], wanted: list[tuple[str, str]]
) -> list[tuple[str, str]]:
    """The wanted sections no existing section already shows."""
    shown = {
        str(playlist)
        for item in existing or []
        for playlist in ((item.get("contentDetails") or {}).get("playlists") or [])
    }
    return [(name, pid) for name, pid in wanted if pid not in shown]


def sync_sections(service: Any, channel_id: str, *, apply: bool) -> list[str]:
    """Add the missing sections - the Week in Review's first. Lines saying what was (or would be)
    added."""
    record_call("channelSections.list")
    existing = (service.channelSections().list(part="snippet,contentDetails", mine=True)
                .execute() or {}).get("items") or []  # fmt: skip
    wanted = wanted_sections(channel_id)
    missing = missing_sections(existing, wanted)
    if not missing:
        names = ", ".join(n for n, _p in wanted) or "none configured with a playlist yet"
        return [f"Sections: all on the page ({names})"]
    lines = []
    for name, pid in missing:
        snippet: dict[str, Any] = {"type": "singlePlaylist", "style": "horizontalRow"}
        if name == "Week in Review":
            snippet["position"] = 0
        if not apply:
            lines.append(f'Sections: would add "{name}" ({pid})')
            continue
        record_call("channelSections.insert")
        service.channelSections().insert(
            part="snippet,contentDetails",
            body={"snippet": snippet, "contentDetails": {"playlists": [pid]}},
        ).execute()
        lines.append(f'Sections: added "{name}"')
    return lines


def _channel(service: Any) -> dict[str, Any]:
    record_call("channels.list")
    items = (service.channels().list(part="brandingSettings", mine=True).execute() or {}).get(
        "items"
    ) or []
    return items[0] if items else {}


def branding_update(current: dict[str, Any], *, description: str, trailer: str) -> dict[str, Any]:
    """The brandingSettings to send: the current ones with the description (and, when given, the
    trailer) replaced - nothing else changes."""
    settings = json.loads(json.dumps(current.get("brandingSettings") or {}))
    channel = settings.setdefault("channel", {})
    if description:
        channel["description"] = description
    if trailer:
        channel["unsubscribedTrailer"] = trailer
    return settings


def sync_branding(
    service: Any,
    channel_id: str,
    *,
    apply: bool,
    trailer: str | None = None,
    with_description: bool = True,
) -> list[str]:
    """The description and the trailer; lines saying what changed (or would). The weekly trailer
    refresh passes `with_description=False`, so an edit made in Studio is not undone."""
    from video.week_compile import latest_public_compilation

    current = _channel(service)
    if not current.get("id"):
        return ["Description: the channel was not found"]
    channel = (current.get("brandingSettings") or {}).get("channel") or {}
    want_text = channel_description(channel_id) if with_description else ""
    want_trailer = latest_public_compilation(channel_id) if trailer is None else trailer
    lines = []
    text_changes = bool(want_text) and channel.get("description") != want_text
    trailer_changes = bool(want_trailer) and channel.get("unsubscribedTrailer") != want_trailer
    if text_changes:
        lines.append(
            f"Description: {'set' if apply else 'would set'} ({len(want_text)} characters)"
        )
    if trailer_changes:
        lines.append(f"Trailer for new visitors: {'set' if apply else 'would set'} to the Week in "
                     f"Review {want_trailer}")  # fmt: skip
    if not lines:
        return ["Description and trailer: already as configured"]
    if apply:
        body = {"id": current["id"], "brandingSettings": branding_update(
            current, description=want_text if text_changes else "",
            trailer=want_trailer if trailer_changes else "")}  # fmt: skip
        record_call("channels.update")
        service.channels().update(part="brandingSettings", body=body).execute()
    return lines


def channel_page_lines(channel_id: str, *, apply: bool, service: Any = None) -> list[str]:
    """`ops channel-page`: the sections, then the description and trailer. Never raises."""
    from publishing.snippet_update import manage_scope_problem

    problem = manage_scope_problem(channel_id)
    if problem:
        return [f"Channel page: {problem}"]
    try:
        if service is None:
            from youtube.oauth import get_youtube_service

            service = get_youtube_service(channel_id)
        if service is None:  # live 11-07: the sign-in had ended - say so, not an attribute error
            return [f"Channel page: no usable YouTube sign-in - py -m youtube.oauth_setup --channel "
                    f"{channel_id}, then run this again"]  # fmt: skip
        lines = sync_sections(service, channel_id, apply=apply)
        lines += sync_branding(service, channel_id, apply=apply)
        if not apply:
            lines.append("Dry run. --apply writes these to the channel.")
        return lines
    except Exception as exc:
        logger.warning("channel page not synced: %s", exc)
        return [f"Channel page: not synced - {str(exc)[:200]}"]


def refresh_trailer(channel_id: str, *, service: Any = None) -> list[str]:
    """#1710: the trailer moves to a newer public Week in Review - once a day from the worker,
    only when it differs, and only once the page has been set (`CHANNEL_PAGE` on). Never raises."""
    if os.getenv("CHANNEL_PAGE", "true").strip().lower() in ("0", "false", "no", "off"):
        return []
    try:
        from datetime import date

        from video.week_compile import latest_public_compilation

        newest = latest_public_compilation(channel_id)
        if not newest:
            return []
        from core.playlists import _load, _save, store_path_for
        from publishing.snippet_update import manage_scope_problem

        path = store_path_for(channel_id)
        data = _load(path)
        today = date.today().isoformat()
        if data.get("trailer") == newest or data.get("trailer_tried") == today:
            return []
        data["trailer_tried"] = today  # one try a day, whatever happens below
        _save(path, data)
        if manage_scope_problem(channel_id):
            return []
        if service is None:
            from youtube.oauth import get_youtube_service

            service = get_youtube_service(channel_id)
        lines = sync_branding(
            service, channel_id, apply=True, trailer=newest, with_description=False
        )
        data["trailer"] = newest
        _save(path, data)
        return lines
    except Exception as exc:
        logger.debug("trailer not refreshed: %s", exc)
        return []
