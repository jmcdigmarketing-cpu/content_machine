"""Queue several rendered runs across the next open post slots (#757).

An all-angles run makes one long video plus up to five chapter Shorts - six uploads
against a 5-per-7-day cadence cap. `next_optimal_post_time` already skips times the queue
has reserved, so asking it repeatedly (each call `after` the previous slot) spreads them;
the cap decides how many go at all. Anything past it stays on disk with its reason
printed, never silently dropped.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from analytics.post_timing import next_optimal_post_time
from core.cadence import cadence_status
from core.logging import get_logger
from publishing.repurpose import enqueue_repurpose_jobs

logger = get_logger("core.spaced_queue")


@dataclass
class SpacedSlot:
    run_id: int
    title: str
    publish_at: datetime | None = None
    skipped: str = ""


def plan_spaced_uploads(
    items: list[tuple[int, str]],
    *,
    channel_id: str,
    topic: str = "",
    reserve: int = 0,
) -> list[SpacedSlot]:
    """One open slot per run, in order, until the cadence window is full.

    `reserve` holds slots for uploads this session already queued (the long video).
    """
    status = cadence_status(channel_id)
    room = max(0, status.cap - status.total - max(0, reserve))
    out: list[SpacedSlot] = []
    after: datetime | None = None
    for index, (run_id, title) in enumerate(items):
        if index >= room:
            out.append(
                SpacedSlot(
                    run_id=int(run_id),
                    title=str(title),
                    skipped=f"cadence cap {status.cap}/{status.window_days}d reached",
                )
            )
            continue
        when = next_optimal_post_time(channel_id, topic, after=after)
        after = when
        out.append(SpacedSlot(run_id=int(run_id), title=str(title), publish_at=when))
    return out


def queue_spaced_uploads(
    slots: list[SpacedSlot],
    *,
    channel_id: str,
    privacy_status: str = "unlisted",
) -> list[int]:
    """Enqueue the planned slots. Skipped ones are left alone. Never raises."""
    from storage.repositories.content_runs import get_content_run_repository

    repo = get_content_run_repository()
    queued: list[int] = []
    for slot in slots:
        if slot.publish_at is None:
            continue
        try:
            record = repo.get(int(slot.run_id))
        except Exception as exc:
            logger.warning("spaced queue: run %s unreadable: %s", slot.run_id, exc)
            continue
        path = str(getattr(record, "mp4_path", "") or "") if record is not None else ""
        if not path:
            logger.warning("spaced queue: run %s has no mp4", slot.run_id)
            continue
        try:
            tags = json.loads(getattr(record, "tags_json", "") or "[]")
        except (TypeError, ValueError):
            tags = []
        try:
            result = enqueue_repurpose_jobs(
                channel_id=channel_id,
                content_run_id=int(slot.run_id),
                file_path=path,
                title=str(getattr(record, "title", "") or slot.title),
                description=str(getattr(record, "description", "") or ""),
                tags=tags,
                privacy_status=privacy_status,
                youtube_publish_at=slot.publish_at,
            )
        except Exception as exc:
            logger.warning("spaced queue: run %s not enqueued: %s", slot.run_id, exc)
            continue
        if getattr(result, "jobs", None):
            queued.append(int(slot.run_id))
    return queued
