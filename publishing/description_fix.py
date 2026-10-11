"""Replace one line of a live description without a re-upload (#1066).

`rollback-publish` unlists the video. This leaves privacy alone and sends
`videos.update(part="snippet")` through `writable_snippet`, so title and
categoryId go back with the new description. Dry run by default: no client.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from core.logging import get_logger

logger = get_logger("publishing.description_fix")


@dataclass
class DescriptionFix:
    status: str
    detail: str = ""


def revised_description(current: str, find: str, replace: str) -> str:
    """The description with the first `find` replaced. Refuses a line that is not there."""
    text = current or ""
    needle = (find or "").strip()
    if not needle or needle not in text:
        raise ValueError(f"description has no {needle!r}")
    return text.replace(needle, replace, 1)


def apply_description_fix(
    video_id: str,
    *,
    find: str,
    replace: str,
    channel_id: str = "tapin",
    dry_run: bool = True,
) -> DescriptionFix:
    if not (video_id or "").strip():
        return DescriptionFix("invalid", "No video_id")
    needle = (find or "").strip()
    if not needle:
        return DescriptionFix("invalid", "No text to find")
    if dry_run:
        return DescriptionFix(
            "dry_run",
            f"Would replace:\n{needle}\nwith:\n{replace}\nNothing was sent to YouTube.",
        )

    enabled = os.getenv("YOUTUBE_UPLOAD_ENABLED", "").lower() in ("1", "true", "yes")
    if not enabled:
        return DescriptionFix("blocked", "YOUTUBE_UPLOAD_ENABLED is not true; nothing was sent")
    from publishing.snippet_update import manage_scope_problem

    problem = manage_scope_problem(channel_id)
    if problem:
        return DescriptionFix("blocked", problem)
    try:
        from publishing.snippet_update import fetch_snippets, writable_snippet
        from youtube.oauth import get_youtube_service

        service = get_youtube_service(channel_id)
        live = fetch_snippets(service, [video_id]).get(video_id)
        if live is None:
            return DescriptionFix("error", f"{video_id} not found on YouTube")
        try:
            description = revised_description(str(live.get("description") or ""), needle, replace)
        except ValueError as exc:
            return DescriptionFix("missing", str(exc))
        body = {"id": video_id, "snippet": writable_snippet(live, description=description)}
        service.videos().update(part="snippet", body=body).execute()
    except Exception as exc:
        from publishing.snippet_update import edit_error_text

        logger.warning("description update failed: %s", exc)
        return DescriptionFix("error", edit_error_text(exc, channel_id))
    return DescriptionFix("updated", f"{video_id} description updated")
