"""
Fan one rendered video out to enabled publish jobs (YouTube only for now).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime

from analytics.post_timing import next_optimal_post_time
from config.channels import get_channel_profile, resolve_channel_id
from core.logging import get_logger
from publishing.base import PLATFORM_YOUTUBE
from publishing.registry import get_publisher, listed_publish_platforms
from publishing.repurpose_format import format_for_platform
from storage.repositories.jobs import JobRecord, enqueue_publish_job

logger = get_logger("publishing.repurpose")

DEFERRED_PLATFORMS = frozenset({"tiktok", "instagram", "facebook"})


@dataclass
class RepurposeResult:
    jobs: list[JobRecord] = field(default_factory=list)
    platforms: list[str] = field(default_factory=list)
    skipped_platforms: list[str] = field(default_factory=list)


def _repurpose_enabled(channel_id: str) -> bool:
    profile = get_channel_profile(channel_id)
    if profile.repurpose_publish is False:
        return False
    env = os.getenv("REPURPOSE_PUBLISH_ENABLED", "true").lower()
    return env in ("1", "true", "yes")


def _slot_for_platform(
    platform: str,
    channel_id: str,
    *,
    youtube_publish_at: datetime | None,
    scheduled_at: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    """Return (job scheduled_at, youtube_publish_at) for one platform."""
    if platform == PLATFORM_YOUTUBE:
        if youtube_publish_at:
            from datetime import timezone

            when = scheduled_at or datetime.now(timezone.utc)
            return when, youtube_publish_at
        return scheduled_at, None

    when = next_optimal_post_time(channel_id)
    return when, None


def enqueue_repurpose_jobs(
    *,
    channel_id: str,
    content_run_id: int,
    file_path: str,
    title: str,
    description: str,
    tags: list[str] | None = None,
    privacy_status: str = "private",
    scheduled_at: datetime | None = None,
    youtube_publish_at: datetime | None = None,
    thumbnail_path: str | None = None,
) -> RepurposeResult:
    """
    Enqueue idempotent publish jobs for each enabled platform on the channel.

    TikTok/Instagram in channels.json are skipped until a later development phase.
    """
    channel_id = resolve_channel_id(channel_id)
    result = RepurposeResult()

    if not _repurpose_enabled(channel_id):
        job = enqueue_publish_job(
            platform=PLATFORM_YOUTUBE,
            channel_id=channel_id,
            content_run_id=content_run_id,
            file_path=file_path,
            title=title,
            description=description,
            tags=tags,
            privacy_status=privacy_status,
            scheduled_at=scheduled_at,
            youtube_publish_at=youtube_publish_at,
            thumbnail_path=thumbnail_path,
        )
        result.jobs.append(job)
        result.platforms.append(PLATFORM_YOUTUBE)
        return result

    platforms = listed_publish_platforms(channel_id)
    if not platforms:
        platforms = (PLATFORM_YOUTUBE,)

    for platform in platforms:
        if platform in DEFERRED_PLATFORMS:
            result.skipped_platforms.append(platform)
            logger.info(
                "Skipping %s publish for run %s (deferred phase)",
                platform,
                content_run_id,
            )
            continue

        publisher = get_publisher(platform)
        if not publisher:
            result.skipped_platforms.append(platform)
            logger.warning("No publisher registered for %s", platform)
            continue

        formatted = format_for_platform(
            platform,
            file_path=file_path,
            title=title,
            description=description,
            tags=tags,
            privacy_status=privacy_status,
            thumbnail_path=thumbnail_path,
        )

        job_when, yt_pub = _slot_for_platform(
            platform,
            channel_id,
            youtube_publish_at=youtube_publish_at,
            scheduled_at=scheduled_at,
        )

        job = enqueue_publish_job(
            platform=platform,
            channel_id=channel_id,
            content_run_id=content_run_id,
            file_path=formatted.file_path,
            title=formatted.title,
            description=formatted.description,
            tags=formatted.tags,
            privacy_status=formatted.privacy_status,
            scheduled_at=job_when,
            youtube_publish_at=yt_pub,
            thumbnail_path=formatted.thumbnail_path,
        )
        result.jobs.append(job)
        result.platforms.append(platform)
        logger.info(
            "Repurpose job %s enqueued for platform=%s run=%s",
            job.id,
            platform,
            content_run_id,
        )

    return result
