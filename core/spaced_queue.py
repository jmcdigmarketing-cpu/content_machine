"""Queue several rendered runs across the next open post slots (#757).

An all-angles run makes one long video plus up to five chapter Shorts - six uploads
against a 5-per-7-day cadence cap. `next_optimal_post_time` already skips times the queue
has reserved, so asking it repeatedly (each call `after` the previous slot) spreads them;
the cap decides how many go at all. Anything past it stays on disk with its reason
printed, never silently dropped.

Operator call 2026-09-16: a planned slot goes public at its time (uploaded private with
`publishAt`). A run forced past the grounding gate - or a Short cut from one - is held
unlisted however it was asked for (#754).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from analytics.post_timing import next_optimal_post_time
from core.cadence import cadence_status
from core.logging import get_logger
from core.run_features import load_features
from publishing.repurpose import enqueue_repurpose_jobs

logger = get_logger("core.spaced_queue")


@dataclass
class SpacedSlot:
    run_id: int
    title: str
    publish_at: datetime | None = None
    skipped: str = ""
    privacy: str = ""  # what it was queued as; "" until queued


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


def _override_held(features_json: str) -> bool:
    """True when this run, or the long video it was cut from, rendered past the gate."""
    try:
        features = json.loads(features_json or "{}")
    except (TypeError, ValueError):
        features = {}
    if not isinstance(features, dict):
        return False
    if features.get("grounding_override"):
        return True
    parent = features.get("parent_run_id")
    return bool(parent and load_features(int(parent)).get("grounding_override"))


def slot_privacy(requested: str | None, *, features_json: str = "") -> str:
    """Public at the slot by default; never public for a grounding override."""
    privacy = (requested or "public").strip().lower() or "public"
    if privacy == "public" and _override_held(features_json):
        return "unlisted"
    return privacy


def queue_spaced_uploads(
    slots: list[SpacedSlot],
    *,
    channel_id: str,
    privacy_status: str | None = None,
) -> list[int]:
    """Enqueue the planned slots. Skipped ones are left alone. Never raises.

    `privacy_status=None` means public at the slot, downgraded per run by `slot_privacy`.
    """
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
            privacy = slot_privacy(
                privacy_status, features_json=str(getattr(record, "features_json", "") or "")
            )
        except Exception as exc:
            logger.debug("spaced queue: privacy check for run %s failed: %s", slot.run_id, exc)
            privacy = "unlisted"
        try:
            result = enqueue_repurpose_jobs(
                channel_id=channel_id,
                content_run_id=int(slot.run_id),
                file_path=path,
                title=str(getattr(record, "title", "") or slot.title),
                description=str(getattr(record, "description", "") or ""),
                tags=tags,
                privacy_status=privacy,
                youtube_publish_at=slot.publish_at,
            )
        except Exception as exc:
            logger.warning("spaced queue: run %s not enqueued: %s", slot.run_id, exc)
            continue
        if getattr(result, "jobs", None):
            slot.privacy = privacy
            queued.append(int(slot.run_id))
    return queued
