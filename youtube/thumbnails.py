"""
YouTube custom thumbnail upload via thumbnails.set (after videos.insert).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from apis.signal_contract import classify_exception, classify_http
from apis.youtube_quota import (
    has_quota_for_thumbnail,
    record_thumbnail_usage,
)
from config.channels import resolve_channel_id
from core.logging import get_logger
from storage.repositories.assets import get_asset_repository

logger = get_logger("youtube.thumbnails")

_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")


@dataclass
class ThumbnailUploadResult:
    status: str
    detail: str | None = None


def is_thumbnail_upload_enabled() -> bool:
    mode = os.getenv("YOUTUBE_THUMBNAIL_UPLOAD", "auto").lower()
    return mode not in ("0", "false", "no", "off")


def _mimetype_for_path(path: str) -> str:
    lower = path.lower()
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


def resolve_thumbnail_path(
    *,
    channel_id: str | None = None,
    content_run_id: int | None = None,
    explicit_path: str | None = None,
) -> str | None:
    """Resolve a deliberate run-linked path; never guess from directory mtime."""
    if content_run_id:
        from core.thumbnail_pick import ensure_thumbnail_ready

        picked = ensure_thumbnail_ready(content_run_id)
        if picked:
            return picked
    if explicit_path and os.path.isfile(explicit_path):
        return explicit_path

    if content_run_id:
        try:
            for asset in get_asset_repository().list_for_run(content_run_id):
                if asset.asset_type == "thumbnail" and asset.path and os.path.isfile(asset.path):
                    return asset.path
        except Exception as exc:
            logger.debug("Asset lookup for thumbnail failed: %s", exc)

    resolve_channel_id(channel_id)  # validate/fallback for consistent caller semantics
    return None


def set_video_thumbnail(service, video_id: str, image_path: str) -> ThumbnailUploadResult:
    """Call YouTube Data API thumbnails.set for an existing video."""
    if not video_id:
        return ThumbnailUploadResult("skipped", "No video_id")
    if not os.path.isfile(image_path):
        return ThumbnailUploadResult("not_found", f"File not found: {image_path}")

    if not has_quota_for_thumbnail():
        return ThumbnailUploadResult(
            "quota_exceeded",
            "Not enough quota units for thumbnails.set (~50)",
        )

    try:
        record_thumbnail_usage()
        media = MediaFileUpload(
            image_path,
            mimetype=_mimetype_for_path(image_path),
            resumable=False,
        )
        service.thumbnails().set(videoId=video_id, media_body=media).execute()
        return ThumbnailUploadResult(
            "set",
            f"thumbnails.set OK — {os.path.basename(image_path)}",
        )
    except HttpError as e:
        status_code = e.resp.status if e.resp else 0
        body = str(e).lower()
        if status_code == 403 and (
            "forbidden" in body or "ineligible" in body or "not allowed" in body or "upload" in body
        ):
            return ThumbnailUploadResult(
                "ineligible",
                "Channel/video not eligible for custom thumbnails via API "
                "(upload may still succeed in Studio when eligible)",
            )
        st, detail = classify_http(status_code, str(e))
        return ThumbnailUploadResult(st, detail[:500])
    except Exception as e:
        st, detail = classify_exception(e)
        return ThumbnailUploadResult(st, detail[:500])


def maybe_upload_thumbnail(
    service,
    *,
    video_id: str,
    channel_id: str | None = None,
    content_run_id: int | None = None,
    thumbnail_path: str | None = None,
) -> ThumbnailUploadResult:
    """Upload thumbnail when enabled and a file is available."""
    if not is_thumbnail_upload_enabled():
        return ThumbnailUploadResult("skipped", "YOUTUBE_THUMBNAIL_UPLOAD=off")

    path = resolve_thumbnail_path(
        channel_id=channel_id,
        content_run_id=content_run_id,
        explicit_path=thumbnail_path,
    )
    if not path:
        return ThumbnailUploadResult(
            "not_found",
            "No thumbnail file (render with THUMBNAIL_MODE=auto or add assets row)",
        )

    return set_video_thumbnail(service, video_id, path)


def merge_thumbnail_into_upload_detail(
    base_detail: str | None,
    thumb: ThumbnailUploadResult,
) -> str:
    if thumb.status in ("skipped", "not_found"):
        return base_detail or ""
    extra = (
        thumb.detail or "Thumbnail set on YouTube"
        if thumb.status == "set"
        else f"Thumbnail {thumb.status}: {thumb.detail or ''}"
    )
    if base_detail:
        return f"{base_detail} | {extra}"
    return extra
