"""Idempotency keys for publish_log rows."""

from __future__ import annotations

from publishing.base import PLATFORM_YOUTUBE


def idempotency_key(
    content_run_id: int | None,
    channel_id: str,
    platform: str = PLATFORM_YOUTUBE,
) -> str:
    if not content_run_id:
        return ""
    if platform == PLATFORM_YOUTUBE:
        return f"run:{channel_id}:{content_run_id}"
    return f"run:{channel_id}:{content_run_id}:{platform}"
