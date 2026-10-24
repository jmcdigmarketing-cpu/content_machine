"""
Upload / publish queue — reserved optimal slots and CLI visibility.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

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


def _logged_runs(channel_id: str) -> set[int]:
    """The runs YouTube has, by the publish log (uploaded or scheduled ahead).

    #1527 (wave 116): a job's payload is only the slot it was sent with. Runs 162, 164 and 165
    went public on 10-18 and their finished jobs still held 10-22 to 10-23, so the queue listed
    them as coming and `next_optimal_post_time` started after Fri 10-23 - Sat noon. A video
    moved in Studio (run 156, Mon noon to Tue noon) showed at its old slot as well."""
    from storage.repositories.publish_log import get_publish_log_repository

    repo = get_publish_log_repository()
    rows = list(repo.list_uploaded_for_channel(channel_id) or [])
    rows += list(repo.list_future_scheduled(channel_id) or [])
    return {
        int(row.content_run_id)
        for row in rows
        if row.content_run_id
        and row.youtube_video_id
        and not str(row.youtube_video_id).startswith("seed_")
    }


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
    logged = _logged_runs(channel_id)
    if hasattr(repo, "list_upload_jobs"):
        for job in repo.list_upload_jobs(channel_id):
            if job.status in ("failed",):
                continue
            if job.content_run_id and int(job.content_run_id) in logged:
                continue  # #1527: the publish log holds its real time
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
    logged = _logged_runs(channel_id)
    if hasattr(repo, "list_upload_jobs"):
        for job in repo.list_upload_jobs(channel_id):
            pub = _publish_at_from_job_payload(job.payload_json)
            if not pub or pub <= now:
                continue
            if int(job.content_run_id or 0) in logged:
                continue  # #1527: listed below at the publish log's time, or already public
            from core.spaced_queue import job_reserves_slot

            if not job_reserves_slot(job.content_run_id):
                continue  # #1558: a held run uploads unlisted - this time is not its slot
            try:
                payload = json.loads(job.payload_json or "{}")
                title = str(payload.get("title", ""))[:60]
            except json.JSONDecodeError:
                title = ""
            entries.append(
                QueueEntry(
                    source="job",
                    ref_id=job.id,
                    title=title or f"job {job.id}",
                    publish_at=pub,
                    status=_display_status(
                        job_status=job.status,
                        on_youtube=False,
                        last_error=getattr(job, "last_error", "") or "",
                    ),
                    content_run_id=job.content_run_id,
                    on_youtube=False,
                )
            )

    from storage.repositories.publish_log import get_publish_log_repository, video_title

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
                    title=video_title(row, fallback=f"run {row.content_run_id}")[:60],
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


def _zone(channel_id: str):
    from zoneinfo import ZoneInfo

    from analytics.post_timing import get_post_schedule

    try:
        return ZoneInfo(get_post_schedule(channel_id).timezone)
    except Exception:
        return ZoneInfo("America/New_York")


def when_label(when: datetime, channel_id: str) -> str:
    """ "Tue 10-20 12:00 PM EDT" - the channel's zone, named (#1527)."""
    moment = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
    local = moment.astimezone(_zone(channel_id))
    return f"{local:%a %m-%d} {local.hour % 12 or 12}:{local:%M %p %Z}"


def queue_lines(entries: list[QueueEntry], channel_id: str, *, limit: int = 6) -> list[str]:
    """#1527 (wave 116): one line per upcoming video in the channel's zone. `ops status`
    printed job slots in UTC and YouTube's in EDT with no label, so "Tue 12:00" and "Tue 16:00"
    were the same minute - runs 156 and 161. A second video at a minute says so."""
    out: list[str] = []
    first_at: dict[datetime, int | None] = {}
    for entry in entries[:limit]:
        minute = entry.publish_at.astimezone(timezone.utc).replace(second=0, microsecond=0)
        line = (
            f"  - {when_label(entry.publish_at, channel_id)}  {entry.title[:35]}  [{entry.status}]"
        )
        if minute in first_at:
            line += f" - the same minute as run {first_at[minute]}"
        else:
            first_at[minute] = entry.content_run_id
        out.append(line)
    return out


def two_week_line(
    entries: list[QueueEntry], channel_id: str, *, now: datetime | None = None
) -> str:
    """#1429 (wave 116): the next 14 days at a glance - how many are scheduled, on how many
    days, the first day with none and the last day with one."""
    moment = now or datetime.now(timezone.utc)
    horizon = moment + timedelta(days=14)
    zone = _zone(channel_id)
    ahead = [e for e in entries if moment < e.publish_at <= horizon]
    if not ahead:
        return "Next 14 days: nothing scheduled on YouTube"
    today = moment.astimezone(zone).date()
    days = sorted({e.publish_at.astimezone(zone).date() for e in ahead})
    span = [today + timedelta(days=i) for i in range(14)]
    empty = [d for d in span if d not in days and d < days[-1]]

    def label(day) -> str:
        return f"{day:%a %m-%d}"

    line = f"Next 14 days: {len(ahead)} scheduled on {len(days)} of 14 days"
    if empty:
        line += f" - first empty day {label(empty[0])},"
    else:
        line += " -"
    return f"{line} nothing after {label(days[-1])}"
