"""
Per-platform caption/title formatting (YouTube today; TikTok/IG deferred).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from publishing.base import PLATFORM_YOUTUBE

YOUTUBE_TITLE_MAX = 100
YOUTUBE_DESC_MAX = 5000
YOUTUBE_TAGS_MAX = 30


@dataclass
class FormattedPublish:
    platform: str
    title: str
    description: str
    tags: list[str]
    file_path: str
    privacy_status: str = "private"
    thumbnail_path: str | None = None


def _ai_disclosure_suffix() -> str:
    label = os.getenv("AI_CONTENT_DISCLOSURE_LABEL", "").strip()
    if not label:
        return ""
    return f"\n\n{label}"


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def format_for_platform(
    platform: str,
    *,
    file_path: str,
    title: str,
    description: str,
    tags: list[str] | None = None,
    privacy_status: str = "private",
    thumbnail_path: str | None = None,
) -> FormattedPublish:
    """Apply platform limits and AI disclosure (future platforms use same hook)."""
    platform = platform.strip().lower()
    tag_list = list(tags or [])[:YOUTUBE_TAGS_MAX]
    disclosure = _ai_disclosure_suffix()

    if platform == PLATFORM_YOUTUBE:
        desc = _truncate(description + disclosure, YOUTUBE_DESC_MAX)
        return FormattedPublish(
            platform=platform,
            title=_truncate(title, YOUTUBE_TITLE_MAX),
            description=desc,
            tags=tag_list,
            file_path=file_path,
            privacy_status=privacy_status,
            thumbnail_path=thumbnail_path,
        )

    # Deferred platforms — keep shape for later without registering publishers
    return FormattedPublish(
        platform=platform,
        title=_truncate(title, 150),
        description=_truncate(description + disclosure, 2200),
        tags=tag_list,
        file_path=file_path,
        privacy_status=privacy_status,
        thumbnail_path=thumbnail_path,
    )
