"""The channel's own uploads playlist (OAuth, `youtube.readonly`) - 2 units a read.

`channels.list(mine)` names the uploads playlist; `playlistItems.list` lists it, newest
first. The publisher's duplicate-upload check (#crash recovery) and the scoreboard's
"uploads this week" (#941) read the same two calls through here.
"""

from __future__ import annotations

from typing import Any


def uploads_playlist_items(service: Any, *, max_results: int = 50) -> list[dict[str, str]]:
    """[{video_id, title, published_at}] newest first; [] when the channel has none.

    Errors propagate: the callers decide whether a failed read matters.
    """
    channels = service.channels().list(part="contentDetails", mine=True).execute()
    items = channels.get("items") or []
    if not items:
        return []
    uploads_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    playlist = (
        service.playlistItems()
        .list(playlistId=uploads_id, part="snippet,contentDetails", maxResults=max_results)
        .execute()
    )
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
