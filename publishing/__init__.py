"""Multi-platform publish layer (YouTube today; TikTok/Instagram deferred)."""

from publishing.base import (
    PLATFORM_YOUTUBE,
    PUBLISH_STATUS_RETRYABLE,
    PUBLISH_STATUS_SUCCESS,
    PUBLISH_STATUS_TERMINAL_FAILURE,
    Publisher,
    PublishRequest,
    PublishResult,
)

__all__ = [
    "PLATFORM_YOUTUBE",
    "PUBLISH_STATUS_RETRYABLE",
    "PUBLISH_STATUS_SUCCESS",
    "PUBLISH_STATUS_TERMINAL_FAILURE",
    "PublishRequest",
    "PublishResult",
    "Publisher",
]
