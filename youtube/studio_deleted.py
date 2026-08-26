"""#106 Detect Studio-deleted videos and cancel the matching publish_log row.

Re-queue already exists; this is the missing detection half. videos.list omits
ids that are gone. Fail-open when upload is not configured — no live Google in tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging import get_logger

if TYPE_CHECKING:
    from storage.repositories.publish_log import PublishLogRecord

logger = get_logger("youtube.studio_deleted")


def detect_studio_deleted(
    channel_id: str,
    *,
    service=None,
) -> list[PublishLogRecord]:
    """Cancel uploaded rows whose youtube_video_id is missing from videos.list."""
    from storage.repositories.publish_log import get_publish_log_repository

    repo = get_publish_log_repository()
    rows = [
        r
        for r in repo.list_uploaded_for_channel(channel_id)
        if (r.youtube_video_id or "").strip() and r.status != "cancelled"
    ]
    if not rows:
        return []
    if service is None:
        try:
            from youtube.oauth import get_youtube_service
            from youtube.upload import is_upload_configured

            if not is_upload_configured(channel_id):
                logger.debug("studio-deleted skipped: upload not configured")
                return []
            service = get_youtube_service(channel_id)
        except Exception as exc:
            logger.debug("studio-deleted service skipped: %s", exc)
            return []
    ids = [r.youtube_video_id for r in rows]
    found: set[str] = set()
    try:
        for start in range(0, len(ids), 50):
            chunk = ids[start : start + 50]
            resp = service.videos().list(part="id", id=",".join(chunk), maxResults=50).execute()
            for item in resp.get("items") or []:
                vid = str(item.get("id") or "")
                if vid:
                    found.add(vid)
    except Exception as exc:
        logger.debug("videos.list for studio-deleted skipped: %s", exc)
        return []
    cancelled: list[PublishLogRecord] = []
    for row in rows:
        if row.youtube_video_id in found:
            continue
        try:
            repo.update(
                row.id,
                {
                    "status": "cancelled",
                    "detail": (row.detail + " | " if row.detail else "")
                    + "Studio-deleted (missing from videos.list)",
                },
            )
            cancelled.append(row)
        except Exception as exc:
            logger.debug("publish_log cancel skipped for %s: %s", row.id, exc)
    return cancelled
