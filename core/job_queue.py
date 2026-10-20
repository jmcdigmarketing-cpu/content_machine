"""#148: one job store, listed and reordered for the queue panel."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from storage.repositories.jobs import JobRecord, JobRepository, get_job_repository

# What `analytics.queue_manager.cancel_queue_slots` writes on a job the operator removed.
REMOVED_BY_OPERATOR = "Removed from publish queue by operator"
OVERDUE_GRACE_MINUTES = 10


def removed_by_operator(job: JobRecord) -> bool:
    """A job the operator took out of the queue. It is stored as failed, and it is not waiting
    on anything (#1129: two removed in June were still "queue 3" in October)."""
    return job.status == "failed" and (job.last_error or "").strip() == REMOVED_BY_OPERATOR


def list_active_jobs(repo: JobRepository | None = None) -> list[JobRecord]:
    store = repo or get_job_repository()
    return [job for job in store.list_active_jobs() if not removed_by_operator(job)]


def overdue_uploads(
    jobs: list[JobRecord] | None,
    *,
    now: datetime | None = None,
    grace_minutes: float = OVERDUE_GRACE_MINUTES,
) -> list[JobRecord]:
    """Pending uploads whose time has passed - nothing is sending them (#1129).

    Run 132 was queued public for 9:30 pm on 2026-10-10 and was still pending the next day:
    uploads go out only while `jobs.worker` runs, and no line said it was not.
    """
    from storage.repositories.jobs import _parse_scheduled_at

    clock = now or datetime.now(timezone.utc)
    late: list[JobRecord] = []
    for job in jobs or []:
        if job.job_type != "upload" or job.status != "pending":
            continue
        due = _parse_scheduled_at(job.scheduled_at)
        if due is not None and (clock - due).total_seconds() > grace_minutes * 60:
            late.append(job)
    return late


def _local(job: JobRecord) -> str:
    from storage.repositories.jobs import _parse_scheduled_at

    due = _parse_scheduled_at(job.scheduled_at)
    if due is None:
        return "?"
    from analytics.upload_queue import when_label

    # #1527: the channel's zone, named - it printed the PC's (CDT) beside EDT everywhere else.
    return when_label(due, str(job.channel_id or "tapin"))


def _signed_out(channel_id: str) -> bool:
    """#1153: with the sign-in dead the worker cannot send - the line names the sign-in."""
    try:
        from youtube.oauth import signed_out

        return signed_out(channel_id)
    except Exception:
        return False


def quota_wait(channel_id: str) -> str:
    """#1526 (wave 116): "" while an upload can go, else when the daily quota resets in the
    channel's zone ("Tue 3:00 AM EDT"). Job 74 (run 173) was held by the quota on 10-19 and
    `ops status` said "nothing is sending uploads - py -m scripts.ops worker" while the worker
    task ran every 15 minutes. Fail-open: "" when the quota is unreadable."""
    try:
        from apis.youtube_quota import has_quota_for_upload, next_quota_retry_at

        if has_quota_for_upload():
            return ""
        from analytics.post_timing import format_scheduled_local

        return format_scheduled_local(next_quota_retry_at(), channel_id)
    except Exception:
        return ""


def quota_held_line(jobs: list[JobRecord] | None, reset: str) -> str:
    """#1526: what the worker pass holds for the quota - it printed "No pending jobs." and a
    requeue command for a job already queued. "" when no due upload is waiting."""
    held = overdue_uploads(jobs, grace_minutes=0)
    if not held or not reset:
        return ""
    noun = "upload waits" if len(held) == 1 else "uploads wait"
    runs = ", ".join(f"run {j.content_run_id}" for j in held[:3])
    return f"{len(held)} {noun} for the quota reset ({runs}) - it goes after {reset}"


def overdue_short(jobs: list[JobRecord] | None, channel_id: str) -> str:
    """The header's words: "1 upload overdue - ops worker", or ""."""
    late = [j for j in overdue_uploads(jobs) if j.channel_id == channel_id]
    if not late:
        return ""
    noun = "upload" if len(late) == 1 else "uploads"
    if _signed_out(channel_id):
        return f"{len(late)} {noun} overdue - sign in"
    if quota_wait(channel_id):  # #1526
        return f"{len(late)} {noun} {'waits' if len(late) == 1 else 'wait'} for the quota reset"
    return f"{len(late)} {noun} overdue - ops worker"


def overdue_lines(jobs: list[JobRecord] | None, channel_id: str) -> list[str]:
    """One line per overdue upload for `ops status`, with the command that sends it."""
    out: list[str] = []
    late = [job for job in overdue_uploads(jobs) if job.channel_id == channel_id]
    if not late:
        return out
    signed_out = _signed_out(channel_id)
    reset = "" if signed_out else quota_wait(channel_id)
    for job in late:
        if reset:  # #1526: held by the quota, not stuck
            out.append(
                f"Upload waiting: run {job.content_run_id} was due {_local(job)} and waits for "
                f"the quota reset at {reset} - the worker sends it then"
            )
            continue
        if signed_out:
            out.append(
                f"Upload overdue: run {job.content_run_id} was due {_local(job)} and the "
                "YouTube sign-in has expired - sign in first: "
                f"py -m youtube.oauth_setup --channel {channel_id}"
            )
            continue
        out.append(
            f"Upload overdue: run {job.content_run_id} was due {_local(job)} and nothing is "
            "sending uploads - py -m scripts.ops worker   "
            "(always on: py -m scripts.ops worker-task --install)"
        )
    return out


def display_status(job: JobRecord) -> str:
    err = (job.last_error or "").lower()
    if job.status == "pending" and "quota" in err:
        return "awaiting_quota"
    if job.job_type in {"render", "upload"}:
        return job.job_type
    return job.status


def queue_depth(jobs: list[JobRecord] | None) -> int:
    return len(jobs or [])


def queue_depth_badge(jobs: list[JobRecord] | None) -> str:
    return str(queue_depth(jobs))


def channel_depth(jobs: list[JobRecord] | None, channel_id: str) -> tuple[int, int]:
    """#989: (this channel's active jobs, every other channel's)."""
    mine = sum(1 for job in jobs or [] if job.channel_id == channel_id)
    return mine, len(jobs or []) - mine


def channel_queue_text(
    jobs: list[JobRecord] | None, channel_id: str, *, label: str = "queue"
) -> str:
    """'queue 2', or 'queue 2 (+1 other channel)' when another channel has jobs waiting."""
    mine, others = channel_depth(jobs, channel_id)
    if not others:
        return f"{label} {mine}"
    noun = "channel" if others == 1 else "channels"
    return f"{label} {mine} (+{others} other {noun})"


def apply_drag_order(repo: JobRepository, ordered_ids: list[int]) -> None:
    by_id = {job.id: job for job in repo.list_active_jobs()}
    for index, job_id in enumerate(ordered_ids):
        job = by_id.get(int(job_id))
        if job is None:
            continue
        try:
            payload: Any = json.loads(job.payload_json or "{}")
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload["sort_key"] = index
        repo.update(int(job_id), {"payload_json": json.dumps(payload)})
