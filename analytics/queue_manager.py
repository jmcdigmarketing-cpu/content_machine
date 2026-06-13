"""
Publish queue management — reset YouTube state after deleting a scheduled video.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from analytics.post_timing import format_scheduled_local
from analytics.upload_queue import QueueEntry, list_queue_entries
from config.channels import resolve_channel_id
from core.logging import get_logger
from storage.repositories.content_runs import get_content_run_repository
from storage.repositories.jobs import get_job_repository
from storage.repositories.publish_log import get_publish_log_repository

logger = get_logger("analytics.queue_manager")

REQUEUEABLE_LOG_STATUSES = frozenset({"uploaded", "scheduled", "pending"})


@dataclass
class RequeueCandidate:
    content_run_id: int
    title: str
    publish_log_id: int
    status: str
    youtube_video_id: str
    publish_at: datetime | None
    mp4_path: str


def _parse_dt(value) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _base_idempotency_key(channel_id: str, content_run_id: int) -> str:
    return f"run:{channel_id}:{content_run_id}"


def _publish_logs_for_run(channel_id: str, content_run_id: int) -> list[dict]:
    repo = get_publish_log_repository()
    primary = repo._primary() if hasattr(repo, "_primary") else repo
    if hasattr(primary, "_read"):
        return [
            r
            for r in primary._read()
            if int(r.get("content_run_id", 0)) == content_run_id
            and r.get("channel_id") == channel_id
        ]
    out = []
    for method in (
        getattr(repo, "list_future_scheduled", None),
        getattr(repo, "list_uploaded_for_channel", None),
    ):
        if not method:
            continue
        for row in method(channel_id):
            if row.content_run_id == content_run_id:
                out.append(
                    {
                        "id": row.id,
                        "status": row.status,
                        "youtube_video_id": row.youtube_video_id,
                        "published_at": row.published_at,
                        "idempotency_key": row.idempotency_key,
                    }
                )
    return out


def list_requeue_candidates(channel_id: str) -> list[RequeueCandidate]:
    """Runs with MP4 on disk that look uploaded/scheduled (user may have deleted on YT)."""
    channel_id = resolve_channel_id(channel_id)
    runs_repo = get_content_run_repository()
    candidates: list[RequeueCandidate] = []

    for run in runs_repo.list_for_channel(channel_id):
        if run.status != "rendered":
            continue
        mp4 = (run.mp4_path or "").strip()
        if not mp4:
            continue

        logs = _publish_logs_for_run(channel_id, run.id)
        active = [
            lg
            for lg in logs
            if str(lg.get("status", "")) in REQUEUEABLE_LOG_STATUSES
            and str(lg.get("status", "")) != "cancelled"
        ]
        if not active:
            continue

        lg = active[-1]
        candidates.append(
            RequeueCandidate(
                content_run_id=run.id,
                title=run.title or run.selected_topic,
                publish_log_id=int(lg.get("id", 0)),
                status=str(lg.get("status", "")),
                youtube_video_id=str(lg.get("youtube_video_id", "")),
                publish_at=_parse_dt(lg.get("published_at")),
                mp4_path=mp4,
            )
        )

    return sorted(candidates, key=lambda c: c.content_run_id, reverse=True)


def reset_publish_for_requeue(
    content_run_id: int,
    channel_id: str,
    *,
    reason: str = "User reset: re-queue after YouTube delete",
) -> bool:
    """
    Cancel publish_log rows so upload can run again with a fresh idempotency key.
    """
    channel_id = resolve_channel_id(channel_id)
    repo = get_publish_log_repository()
    base_key = _base_idempotency_key(channel_id, content_run_id)
    changed = False

    for lg in _publish_logs_for_run(channel_id, content_run_id):
        status = str(lg.get("status", ""))
        if status == "cancelled":
            continue
        if status not in REQUEUEABLE_LOG_STATUSES:
            continue
        log_id = int(lg.get("id", 0))
        if not log_id:
            continue
        archived_key = f"{base_key}:cancelled:{int(time.time())}"
        repo.update(
            log_id,
            {
                "status": "cancelled",
                "youtube_video_id": "",
                "idempotency_key": archived_key,
                "detail": reason,
            },
        )
        logger.info("Cancelled publish_log %s for run %s", log_id, content_run_id)
        changed = True

    return changed


def requeue_content_run(
    content_run_id: int,
    channel_id: str,
    *,
    privacy_status: str = "private",
    youtube_publish_at: datetime | None = None,
    scheduled_at: datetime | None = None,
) -> int:
    """Reset publish state and enqueue a new upload job. Returns job id."""
    from publishing.repurpose import enqueue_repurpose_jobs

    channel_id = resolve_channel_id(channel_id)
    run = get_content_run_repository().get(content_run_id)
    if not run:
        raise ValueError(f"Run {content_run_id} not found")
    if run.channel_id != channel_id:
        channel_id = run.channel_id

    mp4 = (run.mp4_path or "").strip()
    if not mp4:
        raise ValueError(f"Run {content_run_id} has no MP4 path")

    reset_publish_for_requeue(content_run_id, channel_id)

    tags = []
    try:
        tags = json.loads(getattr(run, "tags_json", "[]") or "[]")
    except json.JSONDecodeError:
        tags = []

    when = scheduled_at or datetime.now(timezone.utc)
    thumb_path = ""
    try:
        from storage.repositories.assets import get_asset_repository

        for asset in get_asset_repository().list_for_run(content_run_id):
            if asset.asset_type == "thumbnail" and asset.path:
                thumb_path = asset.path
                break
    except Exception as exc:
        logger.debug("No thumbnail asset for run %s: %s", content_run_id, exc)

    repurpose = enqueue_repurpose_jobs(
        channel_id=channel_id,
        content_run_id=content_run_id,
        file_path=mp4,
        title=run.title or run.selected_topic,
        description=run.description or "",
        tags=tags if isinstance(tags, list) else [],
        privacy_status=privacy_status,
        scheduled_at=when,
        youtube_publish_at=youtube_publish_at,
        thumbnail_path=thumb_path or None,
    )
    if not repurpose.jobs:
        raise RuntimeError("No publish jobs enqueued")
    return repurpose.jobs[0].id


def cancel_queue_entry(
    entry: QueueEntry,
    channel_id: str,
    *,
    reason: str = "Cancelled from queue",
) -> bool:
    """Cancel one queue row (upload job + publish_log for that run)."""
    channel_id = resolve_channel_id(channel_id)
    changed = False

    if entry.source == "job":
        updated = get_job_repository().update(
            entry.ref_id,
            {"status": "failed", "last_error": reason[:500]},
        )
        if updated:
            changed = True
            logger.info("Cancelled job %s", entry.ref_id)

    if entry.content_run_id:
        if reset_publish_for_requeue(entry.content_run_id, channel_id, reason=reason):
            changed = True
    elif entry.source == "youtube":
        repo = get_publish_log_repository()
        if repo.update(
            entry.ref_id,
            {
                "status": "cancelled",
                "detail": reason,
                "youtube_video_id": "",
            },
        ):
            changed = True

    return changed


def cancel_queue_slots(
    channel_id: str,
    slot_numbers: list[int],
    *,
    reason: str = "Removed from publish queue by operator",
) -> list[int]:
    """
    Cancel queue slots by 1-based index (same order as list_queue_entries / main.py display).
    Returns slot numbers that were cancelled.
    """
    entries = list_queue_entries(channel_id)
    done: list[int] = []
    for n in slot_numbers:
        idx = n - 1
        if idx < 0 or idx >= len(entries):
            logger.warning("Queue slot %s out of range (1-%s)", n, len(entries))
            continue
        if cancel_queue_entry(entries[idx], channel_id, reason=reason):
            done.append(n)
    return done


def format_requeue_menu_line(candidate: RequeueCandidate, channel_id: str) -> str:
    when = ""
    if candidate.publish_at:
        when = format_scheduled_local(candidate.publish_at, channel_id)
    vid = candidate.youtube_video_id or "(no id)"
    return (
        f"[run {candidate.content_run_id}] {candidate.title[:45]} — "
        f"{candidate.status} YT:{vid} {when}"
    )
