"""The channel's own uploads playlist (OAuth, `youtube.readonly`) - 2 units a read.

`channels.list(mine)` names the uploads playlist; `playlistItems.list` lists it, newest
first. The publisher's duplicate-upload check (#crash recovery) and the scoreboard's
"uploads this week" (#941) read the same two calls through here.
"""

from __future__ import annotations

from typing import Any

from apis.youtube_quota import record_call


def uploads_playlist_items(
    service: Any, *, max_results: int = 50, pages: int = 1
) -> list[dict[str, str]]:
    """[{video_id, title, published_at}] newest first; [] when the channel has none.
    ``pages`` (#1986): how many pages of `max_results` to read - 1 unit each.

    Errors propagate: the callers decide whether a failed read matters.
    """
    record_call("channels.list")  # wave 113: it booked nothing
    channels = service.channels().list(part="contentDetails", mine=True).execute()
    items = channels.get("items") or []
    if not items:
        return []
    uploads_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    out: list[dict[str, str]] = []
    token = None
    for _page in range(max(1, pages)):
        record_call("playlistItems.list")  # wave 113: it booked nothing
        query: dict[str, Any] = {
            "playlistId": uploads_id,
            "part": "snippet,contentDetails",
            "maxResults": max_results,
        }
        if token:
            query["pageToken"] = token
        playlist = service.playlistItems().list(**query).execute()
        out.extend(_page_items(playlist))
        token = playlist.get("nextPageToken") if isinstance(playlist, dict) else None
        if not token:
            break
    return out


def _page_items(playlist: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in playlist.get("items") or []:
        snippet = item.get("snippet") or {}
        details = item.get("contentDetails") or {}
        video_id = (snippet.get("resourceId") or {}).get("videoId")
        if not video_id:
            continue
        out.append(
            {
                "video_id": str(video_id),
                "title": str(snippet.get("title") or ""),
                # The video's own publish time; a scheduled video has none until it goes live.
                "published_at": str(details.get("videoPublishedAt") or ""),
            }
        )
    return out
