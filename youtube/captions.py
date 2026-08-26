"""YouTube captions.insert — a real caption *track*, distinct from burned ASS / booth VTT."""

from __future__ import annotations

import os
from dataclasses import dataclass

from googleapiclient.http import MediaFileUpload

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


def maybe_upload_captions(
    service, *, video_id: str, caption_path: str | None
) -> CaptionUploadResult:
    """Fail-open when no track file exists — do not call the Data API."""
    if not video_id:
        return CaptionUploadResult("skipped", "No video_id")
    if not caption_path or not os.path.isfile(caption_path):
        return CaptionUploadResult("not_found", "No caption track file")
    try:
        mime = "application/octet-stream"
        lower = caption_path.lower()
        if lower.endswith(".vtt"):
            mime = "text/vtt"
        elif lower.endswith(".srt"):
            mime = "application/octet-stream"
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
