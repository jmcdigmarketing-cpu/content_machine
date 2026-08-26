"""
Publisher ABC — mirrors assets.AssetProvider for upload destinations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

PLATFORM_YOUTUBE = "youtube"
# TikTok / Instagram: deferred — see docs/platform_publish_setup.md

PUBLISH_STATUS_SUCCESS = frozenset({"uploaded", "scheduled"})
PUBLISH_STATUS_TERMINAL_FAILURE = frozenset(
    {"not_configured", "not_implemented", "invalid_file", "auth_error", "blocked"}
)
PUBLISH_STATUS_RETRYABLE = frozenset(
    {"quota_exceeded", "rate_limited", "error", "failed", "upstream_error"}
)


@dataclass
class PublishRequest:
    file_path: str
    title: str
    description: str
    tags: list[str] | None = None
    category_id: str = ""
    privacy_status: str = "private"
    publish_at: datetime | None = None
    thumbnail_path: str | None = None
    caption_path: str | None = None


@dataclass
class PublishResult:
    video_id: str | None
    status: str
    detail: str | None = None
    publish_log_id: int | None = None
    thumbnail_status: str | None = None
    thumbnail_detail: str | None = None
    platform: str = PLATFORM_YOUTUBE


class Publisher(ABC):
    """Upload a rendered video to one platform (idempotent publish_log per run)."""

    platform: str = "base"

    @abstractmethod
    def is_configured(self, channel_id: str) -> bool:
        pass

    @abstractmethod
    def publish(
        self,
        request: PublishRequest,
        *,
        channel_id: str,
        content_run_id: int | None = None,
    ) -> PublishResult:
        pass
