"""
Upload / publish queue — reserved optimal slots and CLI visibility.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from config.channels import resolve_channel_id


@dataclass
class QueueEntry:
    source: str  # job | publish_log
    ref_id: int
    title: str
    publish_at: datetime
    status: str
    content_run_id: int | None = None
    on_youtube: bool = False


def _run_on_youtube(channel_id: str, content_run_id: int | None) -> bool:
    if not content_run_id:
        return False
    from storage.repositories.publish_log import get_publish_log_repository

    repo = get_publish_log_repository()
    for row in repo.list_uploaded_for_channel(channel_id):
        if row.content_run_id == content_run_id and row.youtube_video_id:
            if not str(row.youtube_video_id).startswith("seed_"):
                return True
    for row in repo.list_future_scheduled(channel_id):
        if row.content_run_id == content_run_id and row.youtube_video_id:
            if not str(row.youtube_video_id).startswith("seed_"):
                return True
    return False


def _display_status(*, job_status: str, on_youtube: bool, last_error: str = "") -> str:
    if on_youtube:
        return job_status
    if job_status == "pending" and "quota" in (last_error or "").lower():
        return "awaiting_quota"
    if job_status in ("pending", "running"):
        return "awaiting_upload"
    return job_status


def _parse_iso_dt(raw) -> datetime | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _publish_at_from_job_payload(payload_json: str) -> datetime | None:
    try:
        payload = json.loads(payload_json or "{}")
    except json.JSONDecodeError:
        return None
    return _parse_iso_dt(payload.get("youtube_publish_at"))


def get_reserved_publish_times(channel_id: str) -> list[datetime]:
    """
    Future YouTube publish times already claimed (pending jobs + scheduled publish_log).
    """
    channel_id = resolve_channel_id(channel_id)
    now = datetime.now(timezone.utc)
    reserved: list[datetime] = []

    from storage.repositories.jobs import get_job_repository

    repo = get_job_repository()
    if hasattr(repo, "list_upload_jobs"):
        for job in repo.list_upload_jobs(channel_id):
            if job.status in ("failed",):
                continue
            pub = _publish_at_from_job_payload(job.payload_json)
            if pub and pub > now:
                reserved.append(pub)

    from storage.repositories.publish_log import get_publish_log_repository

    plog = get_publish_log_repository()
    if hasattr(plog, "list_future_scheduled"):
        for row in plog.list_future_scheduled(channel_id):
            when = _parse_iso_dt(getattr(row, "published_at", None))
            if when and when > now:
                reserved.append(when)

    return sorted(set(reserved))


def list_queue_entries(channel_id: str) -> list[QueueEntry]:
    """All upcoming scheduled publishes for a channel, sorted by time."""
    channel_id = resolve_channel_id(channel_id)
    now = datetime.now(timezone.utc)
    entries: list[QueueEntry] = []

    from storage.repositories.jobs import get_job_repository

    repo = get_job_repository()
    if hasattr(repo, "list_upload_jobs"):
        for job in repo.list_upload_jobs(channel_id):
            pub = _publish_at_from_job_payload(job.payload_json)
            if not pub or pub <= now:
                continue
            try:
                payload = json.loads(job.payload_json or "{}")
                title = str(payload.get("title", ""))[:60]
            except json.JSONDecodeError:
                title = ""
            on_yt = _run_on_youtube(channel_id, job.content_run_id)
            entries.append(
                QueueEntry(
                    source="job",
                    ref_id=job.id,
                    title=title or f"job {job.id}",
                    publish_at=pub,
                    status=_display_status(
                        job_status=job.status,
                        on_youtube=on_yt,
                        last_error=getattr(job, "last_error", "") or "",
                    ),
                    content_run_id=job.content_run_id,
                    on_youtube=on_yt,
                )
            )

    from storage.repositories.publish_log import get_publish_log_repository

    plog = get_publish_log_repository()
    if hasattr(plog, "list_future_scheduled"):
        for row in plog.list_future_scheduled(channel_id):
            when = _parse_iso_dt(getattr(row, "published_at", None))
            if not when or when <= now:
                continue
            entries.append(
                QueueEntry(
                    source="youtube",
                    ref_id=row.id,
                    title=row.detail[:60] if row.detail else f"run {row.content_run_id}",
                    publish_at=when,
                    status=row.status,
                    content_run_id=row.content_run_id,
                    on_youtube=True,
                )
            )

    entries.sort(key=lambda e: e.publish_at)
    deduped: list[QueueEntry] = []
    seen = set()
    for entry in entries:
        key = (
            entry.content_run_id,
            entry.publish_at.replace(second=0, microsecond=0),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped
