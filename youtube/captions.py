"""YouTube captions.insert — a real caption *track*, distinct from burned ASS / booth VTT."""

from __future__ import annotations

import os
from dataclasses import dataclass

from googleapiclient.http import MediaFileUpload

from apis.youtube_quota import record_call
from core.logging import get_logger

logger = get_logger("youtube.captions")


@dataclass
class CaptionUploadResult:
    status: str
    detail: str | None = None


def resolve_caption_path(file_path: str | None = None, explicit: str | None = None) -> str | None:
    """Prefer an explicit track; otherwise a sibling .srt next to the mp4. Never guess."""
    if explicit and os.path.isfile(explicit):
        return explicit
    if file_path:
        sibling = os.path.splitext(file_path)[0] + ".srt"
        if os.path.isfile(sibling):
            return sibling
    return None


CAPTION_UNITS = 400  # YouTube's cost of captions.insert


def caption_quota_ok(remaining: int, *, waiting: int = 0) -> bool:
    """#1525 (the operator: only when quota allows): a caption file is 400 units - 1,200 of the
    8,629 spent on 2026-10-19, when uploads stopped at 4. It goes up only while one upload's worth
    is still left after it; the burned captions and YouTube's auto-captions remain either way.
    #1553 (2026-10-23): one upload's worth for each upload still `waiting` - three captions took
    1,200 units with three uploads queued, and run 184 waited for the reset."""
    from apis.youtube_quota import units_per_upload

    return int(remaining) - CAPTION_UNITS >= units_per_upload() * max(1, int(waiting))


def _waiting_uploads() -> int:
    """Upload jobs still pending - the one being sent is running, so it is not counted."""
    try:
        from core.job_queue import list_active_jobs

        return sum(
            1 for j in list_active_jobs() if j.job_type == "upload" and j.status == "pending"
        )
    except Exception as exc:
        logger.debug("upload queue unread for the caption reserve: %s", exc)
        return 0


def maybe_upload_captions(
    service, *, video_id: str, caption_path: str | None
) -> CaptionUploadResult:
    """Fail-open when no track file exists — do not call the Data API."""
    if not video_id:
        return CaptionUploadResult("skipped", "No video_id")
    if not caption_path or not os.path.isfile(caption_path):
        return CaptionUploadResult("not_found", "No caption track file")
    try:
        from apis.youtube_quota import get_usage_summary

        remaining = int(get_usage_summary().get("remaining") or 0)
    except Exception as exc:  # an unread ledger does not stop a caption (as before)
        logger.debug("caption quota unread: %s", exc)
        remaining = None
    waiting = _waiting_uploads() if remaining is not None else 0
    if remaining is not None and not caption_quota_ok(remaining, waiting=waiting):
        queued = f", {waiting} queued" if waiting else ""
        logger.info(
            "caption file skipped - keeps the uploads' units (%s left%s)", remaining, queued
        )
        return CaptionUploadResult(
            "skipped",
            f"caption file skipped - keeps the uploads' units ({remaining:,} left{queued})",
        )
    try:
        mime = "application/octet-stream"
        lower = caption_path.lower()
        if lower.endswith(".vtt"):
            mime = "text/vtt"
        elif lower.endswith(".srt"):
            mime = "application/octet-stream"
        record_call("captions.insert")  # wave 113: it booked nothing
        service.captions().insert(
            part="snippet",
            body={
                "snippet": {
                    "videoId": video_id,
                    "language": "en",
                    "name": "English",
                    "isDraft": False,
                }
            },
            media_body=MediaFileUpload(caption_path, mimetype=mime, resumable=False),
        ).execute()
        return CaptionUploadResult("set", os.path.basename(caption_path))
    except Exception as exc:
        logger.debug("captions.insert skipped: %s", exc)
        return CaptionUploadResult("error", str(exc)[:200])
