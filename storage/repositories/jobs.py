import json
import os
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from storage.db import get_session
from storage.models import Job
from storage.repository_base import postgres_authoritative

JOBS_FILE = os.path.join("data", "jobs.json")
_lock = threading.Lock()

JOB_PENDING = "pending"
JOB_RUNNING = "running"
JOB_COMPLETED = "completed"
JOB_FAILED = "failed"


def _parse_scheduled_at(value) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _job_is_ready(row: dict) -> bool:
    scheduled = _parse_scheduled_at(row.get("scheduled_at"))
    if scheduled is None:
        return True
    return scheduled <= datetime.now(timezone.utc)


@dataclass
class JobRecord:
    id: int
    channel_id: str
    job_type: str
    status: str
    content_run_id: int | None = None
    payload_json: str = "{}"
    attempts: int = 0
    max_attempts: int = 3
    last_error: str = ""
    scheduled_at: datetime | str | None = None


class JobRepository(ABC):
    @abstractmethod
    def enqueue(self, data: dict[str, Any]) -> JobRecord:
        pass

    @abstractmethod
    def claim_next(self, job_type: str | None = None) -> JobRecord | None:
        pass

    @abstractmethod
    def update(self, job_id: int, data: dict[str, Any]) -> JobRecord | None:
        pass

    @abstractmethod
    def reclaim_stuck_running(self, max_age_minutes: int = 45) -> int:
        pass

    @abstractmethod
    def list_upload_jobs(self, channel_id: str) -> list[JobRecord]:
        pass

    @abstractmethod
    def list_active_jobs(self) -> list[JobRecord]:
        pass


def _claim_sort_tuple(row: dict) -> tuple[int, int]:
    job_id = int(row.get("id") or 0)
    try:
        payload = json.loads(row.get("payload_json") or "{}")
        if isinstance(payload, dict) and payload.get("sort_key") is not None:
            return (int(payload["sort_key"]), job_id)
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    return (job_id, job_id)


def _record_from_row(row: dict) -> JobRecord:
    return JobRecord(**{k: row.get(k) for k in JobRecord.__dataclass_fields__})


def _parse_publish_from_payload(payload_json: str):
    try:
        payload = json.loads(payload_json or "{}")
    except json.JSONDecodeError:
        return None
    raw = payload.get("youtube_publish_at")
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


class JsonJobRepository(JobRepository):
    def _read(self) -> list[dict]:
        if not os.path.exists(JOBS_FILE):
            return []
        with open(JOBS_FILE, encoding="utf-8") as f:
            return json.load(f)

    def _write(self, rows: list[dict]) -> None:
        os.makedirs(os.path.dirname(JOBS_FILE), exist_ok=True)
        with open(JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2)

    def enqueue(self, data: dict[str, Any]) -> JobRecord:
        with _lock:
            rows = self._read()
            job_id = max((r.get("id", 0) for r in rows), default=0) + 1
            row = {
                "id": job_id,
                "status": JOB_PENDING,
                "attempts": 0,
                **data,
            }
            if isinstance(row.get("scheduled_at"), datetime):
                row["scheduled_at"] = row["scheduled_at"].isoformat()
            rows.append(row)
            self._write(rows)
        return _record_from_row(row)

    def claim_next(self, job_type: str | None = None) -> JobRecord | None:
        with _lock:
            rows = self._read()
            ready: list[tuple[tuple[int, int], int]] = []
            for i, row in enumerate(rows):
                if row.get("status") != JOB_PENDING:
                    continue
                if job_type and row.get("job_type") != job_type:
                    continue
                if not _job_is_ready(row):
                    continue
                ready.append((_claim_sort_tuple(row), i))
            if not ready:
                return None
            ready.sort(key=lambda item: item[0])
            i = ready[0][1]
            row = rows[i]
            row["status"] = JOB_RUNNING
            row["attempts"] = int(row.get("attempts", 0)) + 1
            row["updated_at"] = datetime.now(timezone.utc).isoformat()
            rows[i] = row
            self._write(rows)
            return _record_from_row(row)

    def reclaim_stuck_running(self, max_age_minutes: int = 45) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
        reclaimed = 0
        with _lock:
            rows = self._read()
            changed = False
            for i, row in enumerate(rows):
                if row.get("status") != JOB_RUNNING:
                    continue
                updated = _parse_scheduled_at(row.get("updated_at"))
                if updated and updated > cutoff:
                    continue
                row["status"] = JOB_PENDING
                row["last_error"] = (row.get("last_error") or "")[
                    :200
                ] + " [reclaimed stuck running job]"
                row["updated_at"] = datetime.now(timezone.utc).isoformat()
                rows[i] = row
                reclaimed += 1
                changed = True
            if changed:
                self._write(rows)
        return reclaimed

    def update(self, job_id: int, data: dict[str, Any]) -> JobRecord | None:
        with _lock:
            rows = self._read()
            for i, row in enumerate(rows):
                if row.get("id") == job_id:
                    row.update(data)
                    row["updated_at"] = datetime.now(timezone.utc).isoformat()
                    rows[i] = row
                    self._write(rows)
                    return _record_from_row(row)
        return None

    def list_upload_jobs(self, channel_id: str) -> list[JobRecord]:
        active = {JOB_PENDING, JOB_RUNNING, JOB_COMPLETED}
        out = []
        for row in self._read():
            if row.get("channel_id") != channel_id:
                continue
            if row.get("job_type") != "upload":
                continue
            if row.get("status") not in active:
                continue
            if not _parse_publish_from_payload(row.get("payload_json", "{}")):
                continue
            out.append(_record_from_row(row))
        return out

    def list_active_jobs(self) -> list[JobRecord]:
        active = {JOB_PENDING, JOB_RUNNING, JOB_FAILED}
        return [_record_from_row(row) for row in self._read() if row.get("status") in active]


class PostgresJobRepository(JobRepository):
    def _to_record(self, row: Job) -> JobRecord:
        return JobRecord(
            id=row.id,
            channel_id=row.channel_id,
            job_type=row.job_type,
            status=row.status,
            content_run_id=row.content_run_id,
            payload_json=row.payload_json,
            attempts=row.attempts,
            max_attempts=row.max_attempts,
            last_error=row.last_error or "",
            scheduled_at=row.scheduled_at,
        )

    def enqueue(self, data: dict[str, Any]) -> JobRecord:
        session = get_session()
        try:
            row = Job(status=JOB_PENDING, **data)
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._to_record(row)
        finally:
            session.close()

    def claim_next(self, job_type: str | None = None) -> JobRecord | None:
        session = get_session()
        try:
            now = datetime.now(timezone.utc)
            q = (
                select(Job)
                .where(Job.status == JOB_PENDING)
                .where((Job.scheduled_at.is_(None)) | (Job.scheduled_at <= now))
            )
            if job_type:
                q = q.where(Job.job_type == job_type)
            rows = list(session.scalars(q).all())
            if not rows:
                return None
            rows.sort(
                key=lambda item: _claim_sort_tuple(
                    {"id": item.id, "payload_json": item.payload_json or "{}"}
                )
            )
            row = rows[0]
            row.status = JOB_RUNNING
            row.attempts = (row.attempts or 0) + 1
            session.commit()
            session.refresh(row)
            return self._to_record(row)
        finally:
            session.close()

    def reclaim_stuck_running(self, max_age_minutes: int = 45) -> int:
        session = get_session()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
            rows = session.scalars(
                select(Job).where(Job.status == JOB_RUNNING).where(Job.updated_at < cutoff)
            ).all()
            count = 0
            for row in rows:
                row.status = JOB_PENDING
                row.last_error = (row.last_error or "")[:200] + " [reclaimed stuck running job]"
                count += 1
            if count:
                session.commit()
            return count
        finally:
            session.close()

    def update(self, job_id: int, data: dict[str, Any]) -> JobRecord | None:
        session = get_session()
        try:
            row = session.get(Job, job_id)
            if not row:
                return None
            for key, value in data.items():
                if hasattr(row, key):
                    setattr(row, key, value)
            session.commit()
            session.refresh(row)
            return self._to_record(row)
        finally:
            session.close()

    def list_upload_jobs(self, channel_id: str) -> list[JobRecord]:
        session = get_session()
        try:
            rows = session.scalars(
                select(Job).where(
                    Job.channel_id == channel_id,
                    Job.job_type == "upload",
                    Job.status.in_([JOB_PENDING, JOB_RUNNING, JOB_COMPLETED]),
                )
            ).all()
            out = []
            for row in rows:
                if _parse_publish_from_payload(row.payload_json or ""):
                    out.append(self._to_record(row))
            return out
        finally:
            session.close()

    def list_active_jobs(self) -> list[JobRecord]:
        session = get_session()
        try:
            rows = session.scalars(
                select(Job).where(
                    Job.status.in_([JOB_PENDING, JOB_RUNNING, JOB_FAILED]),
                )
            ).all()
            return [self._to_record(row) for row in rows]
        finally:
            session.close()


class DualJobRepository(JobRepository):
    def __init__(self):
        self._json = JsonJobRepository()
        self._pg = PostgresJobRepository() if postgres_authoritative() else None

    def _primary(self):
        return self._pg if self._pg else self._json

    def enqueue(self, data: dict[str, Any]) -> JobRecord:
        return self._primary().enqueue(data)

    def claim_next(self, job_type: str | None = None) -> JobRecord | None:
        return self._primary().claim_next(job_type)

    def update(self, job_id: int, data: dict[str, Any]) -> JobRecord | None:
        return self._primary().update(job_id, data)

    def reclaim_stuck_running(self, max_age_minutes: int = 45) -> int:
        return self._primary().reclaim_stuck_running(max_age_minutes)

    def list_upload_jobs(self, channel_id: str) -> list[JobRecord]:
        return self._primary().list_upload_jobs(channel_id)

    def list_active_jobs(self) -> list[JobRecord]:
        return self._primary().list_active_jobs()


_repo = None


def get_job_repository() -> JobRepository:
    global _repo
    if _repo is None:
        _repo = DualJobRepository()
    return _repo


def enqueue_publish_job(
    *,
    platform: str = "youtube",
    channel_id: str,
    content_run_id: int,
    file_path: str,
    title: str,
    description: str,
    tags: list[str] | None = None,
    privacy_status: str = "private",
    scheduled_at: datetime | None = None,
    youtube_publish_at: datetime | None = None,
    thumbnail_path: str | None = None,
) -> JobRecord:
    payload = {
        "platform": platform.strip().lower(),
        "file_path": file_path,
        "title": title,
        "description": description,
        "tags": tags or [],
        "privacy_status": privacy_status,
    }
    if thumbnail_path:
        payload["thumbnail_path"] = thumbnail_path
    if youtube_publish_at is not None:
        when = youtube_publish_at
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        payload["youtube_publish_at"] = when.isoformat()
    when = scheduled_at or datetime.now(timezone.utc)
    return get_job_repository().enqueue(
        {
            "channel_id": channel_id,
            "job_type": "upload",
            "content_run_id": content_run_id,
            "payload_json": json.dumps(payload),
            "scheduled_at": when,
        }
    )


def enqueue_upload_job(
    *,
    channel_id: str,
    content_run_id: int,
    file_path: str,
    title: str,
    description: str,
    tags: list[str] | None = None,
    privacy_status: str = "private",
    scheduled_at: datetime | None = None,
    youtube_publish_at: datetime | None = None,
    thumbnail_path: str | None = None,
) -> JobRecord:
    """Backward-compatible wrapper — YouTube upload job."""
    return enqueue_publish_job(
        platform="youtube",
        channel_id=channel_id,
        content_run_id=content_run_id,
        file_path=file_path,
        title=title,
        description=description,
        tags=tags,
        privacy_status=privacy_status,
        scheduled_at=scheduled_at,
        youtube_publish_at=youtube_publish_at,
        thumbnail_path=thumbnail_path,
    )
