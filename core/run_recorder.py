"""Persist content runs and record learning outcomes."""

from __future__ import annotations

import json
import os
from typing import Any

from apis.topic_scorer import infer_domain
from config.channels import resolve_channel_id
from core.logging import get_logger
from storage.repositories.channel_memory import get_channel_memory_repository
from storage.repositories.content_runs import get_content_run_repository
from storage.repositories.performance_memory import (
    PROXY_SOURCE,
    get_performance_memory_repository,
)

logger = get_logger("run_recorder")

_RECORD_PROXY_LEARNING = os.getenv("RECORD_PROXY_LEARNING", "").lower() in (
    "1",
    "true",
    "yes",
)


def _signals_for_storage(signals: dict[str, Any]) -> str:
    slim = {}
    for name, sig in (signals or {}).items():
        if not isinstance(sig, dict):
            continue
        slim[name] = {
            "connected": sig.get("connected"),
            "active": sig.get("active"),
            "score": sig.get("score"),
            "status": sig.get("status"),
        }
    return json.dumps(slim)


def record_content_run(
    *,
    channel_id: str,
    input_topic: str,
    selected_topic: str,
    status: str,
    composite_score: float,
    signals: dict[str, Any],
    variants: list[tuple[str, float]],
    title: str = "",
    description: str = "",
    tags_json: str = "[]",
    brief_version: str = "",
    prompt_version: str = "",
    script: str = "",
    mp3_path: str = "",
    mp4_path: str = "",
    timings: dict[str, float] | None = None,
    abort_reason: str = "",
) -> int:
    channel_id = resolve_channel_id(channel_id)
    repo = get_content_run_repository()
    record = repo.create(
        {
            "channel_id": channel_id,
            "input_topic": input_topic,
            "selected_topic": selected_topic,
            "status": status,
            "composite_score": float(composite_score),
            "signals_json": _signals_for_storage(signals),
            "variants_json": json.dumps(variants),
            "title": title,
            "description": description,
            "tags_json": tags_json,
            "brief_version": brief_version,
            "prompt_version": prompt_version,
            "script_preview": (script or "")[:2000],
            "mp3_path": mp3_path or "",
            "mp4_path": mp4_path or "",
            "timings_json": json.dumps(timings or {}),
            "abort_reason": abort_reason or "",
        }
    )
    logger.info("Recorded content run %s (%s)", record.id, status)
    return record.id


def update_content_run_media(
    run_id: int,
    *,
    mp3_path: str,
    mp4_path: str,
    status: str = "rendered",
) -> None:
    get_content_run_repository().update(
        run_id,
        {"mp3_path": mp3_path, "mp4_path": mp4_path, "status": status},
    )


def record_learning_outcome(
    *,
    channel_id: str,
    topic: str,
    score: float,
    content_run_id: int | None = None,
) -> None:
    """
    Record learning signals. Pre-publish composite scores are NOT written to
    performance memory by default (they reinforced the wrong objective).
    Set RECORD_PROXY_LEARNING=true to restore legacy proxy logging.
    """
    channel_id = resolve_channel_id(channel_id)
    domain = infer_domain(topic, channel_id)

    get_channel_memory_repository().add_score(topic, float(score), channel_id)

    if _RECORD_PROXY_LEARNING:
        get_performance_memory_repository().log_performance(
            {
                "domain": domain,
                "alignment_score": score,
                "topic": topic,
                "channel_id": channel_id,
                "content_run_id": content_run_id,
                "source": PROXY_SOURCE,
            },
            channel_id,
        )
        logger.debug("Logged proxy alignment score for %s", topic)
    else:
        logger.debug(
            "Skipped proxy performance log for %s (await real publish metrics)",
            topic,
        )


def record_publish_outcome(
    *,
    channel_id: str,
    topic: str,
    domain: str,
    views: int,
    engaged_rate: float,
    likes: int = 0,
    subscribers_gained: int = 0,
    content_run_id: int | None = None,
    title: str = "",
) -> None:
    """Record real YouTube analytics — drives learned weights."""
    channel_id = resolve_channel_id(channel_id)
    get_performance_memory_repository().log_performance(
        {
            "domain": domain,
            "alignment_score": round(engaged_rate * 100, 2),
            "engaged_rate": engaged_rate,
            "views": views,
            "likes": likes,
            "subscribers_gained": subscribers_gained,
            "topic": topic,
            "title": title,
            "channel_id": channel_id,
            "content_run_id": content_run_id,
            "source": "youtube_analytics",
        },
        channel_id,
    )
