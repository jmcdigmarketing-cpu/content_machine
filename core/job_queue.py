"""#148: one job store, listed and reordered for the queue panel."""

from __future__ import annotations

import json
from typing import Any

from storage.repositories.jobs import JobRecord, JobRepository, get_job_repository


def list_active_jobs(repo: JobRepository | None = None) -> list[JobRecord]:
    store = repo or get_job_repository()
    return store.list_active_jobs()


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
