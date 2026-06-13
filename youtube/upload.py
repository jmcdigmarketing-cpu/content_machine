"""
YouTube upload — backward-compatible facade over publishing.YouTubePublisher.
"""

from __future__ import annotations

from publishing.base import (
    PUBLISH_STATUS_RETRYABLE,
    PUBLISH_STATUS_SUCCESS,
    PUBLISH_STATUS_TERMINAL_FAILURE,
    PublishRequest,
    PublishResult,
)
from publishing.youtube_publisher import (
    YouTubePublisher,
    _result_from_existing_log,
    build_video_status,
    is_youtube_configured,
)

# Legacy names used across the codebase
UploadRequest = PublishRequest
UploadResult = PublishResult

UPLOAD_STATUS_SUCCESS = PUBLISH_STATUS_SUCCESS
UPLOAD_STATUS_TERMINAL_FAILURE = PUBLISH_STATUS_TERMINAL_FAILURE
UPLOAD_STATUS_RETRYABLE = PUBLISH_STATUS_RETRYABLE

YOUTUBE_PUBLISH_MIN_LEAD_MINUTES = 15
TERMINAL_LOG_STATUSES = UPLOAD_STATUS_SUCCESS


def is_upload_configured(channel_id: str | None = None) -> bool:
    return is_youtube_configured(channel_id)


def upload_video(
    request: UploadRequest,
    *,
    channel_id: str | None = None,
    content_run_id: int | None = None,
) -> UploadResult:
    from config.channels import resolve_channel_id

    publisher = YouTubePublisher()
    return publisher.publish(
        request,
        channel_id=resolve_channel_id(channel_id),
        content_run_id=content_run_id,
    )


__all__ = [
    "TERMINAL_LOG_STATUSES",
    "UPLOAD_STATUS_RETRYABLE",
    "UPLOAD_STATUS_SUCCESS",
    "UPLOAD_STATUS_TERMINAL_FAILURE",
    "YOUTUBE_PUBLISH_MIN_LEAD_MINUTES",
    "UploadRequest",
    "UploadResult",
    "_result_from_existing_log",
    "build_video_status",
    "is_upload_configured",
    "upload_video",
]
