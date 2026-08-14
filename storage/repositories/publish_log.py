import json
import os
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from storage.db import get_session
from storage.models import PublishLog
from storage.repository_base import postgres_authoritative

LOG_FILE = os.path.join("data", "publish_log.json")
_lock = threading.Lock()


def _opt_int(value) -> int | None:
    """None/'' stay None (no associated run); anything numeric coerces to int.

    Legacy rows used 0 as the "no run" sentinel, which blocked the content_run_id
    foreign key; it is normalised to None here so both storage backends agree.
    """
    if value is None or value == "":
        return None
    try:
        return int(value) or None
    except (TypeError, ValueError):
        return None


@dataclass
class PublishLogRecord:
    id: int
    content_run_id: int | None
    channel_id: str
    youtube_video_id: str = ""
    privacy_status: str = "private"
    status: str = "pending"
    metrics_json: str = "{}"
    detail: str = ""
    idempotency_key: str = ""
    published_at: datetime | None = None


def _to_record(row) -> PublishLogRecord:
    if isinstance(row, dict):
        return PublishLogRecord(
            id=int(row.get("id", 0)),
            content_run_id=_opt_int(row.get("content_run_id")),
            channel_id=str(row.get("channel_id", "default")),
            youtube_video_id=str(row.get("youtube_video_id", "")),
            privacy_status=str(row.get("privacy_status", "private")),
            status=str(row.get("status", "pending")),
            metrics_json=str(row.get("metrics_json", "{}")),
            detail=str(row.get("detail", "")),
            idempotency_key=str(row.get("idempotency_key", "")),
            published_at=_parse_dt(row.get("published_at")),
        )
    return PublishLogRecord(
        id=row.id,
        content_run_id=_opt_int(row.content_run_id),
        channel_id=row.channel_id,
        youtube_video_id=row.youtube_video_id or "",
        privacy_status=row.privacy_status,
        status=row.status,
        metrics_json=row.metrics_json or "{}",
        detail=row.detail or "",
        idempotency_key=getattr(row, "idempotency_key", "") or "",
        published_at=getattr(row, "published_at", None),
    )


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


class PublishLogRepository(ABC):
    @abstractmethod
    def create(self, data: dict[str, Any]) -> PublishLogRecord:
        pass

    @abstractmethod
    def update(self, log_id: int, data: dict[str, Any]) -> PublishLogRecord | None:
        pass

    @abstractmethod
    def find_by_idempotency(self, key: str) -> PublishLogRecord | None:
        pass

    @abstractmethod
    def list_uploaded_for_channel(self, channel_id: str) -> list[PublishLogRecord]:
        pass

    @abstractmethod
    def list_future_scheduled(self, channel_id: str) -> list[PublishLogRecord]:
        pass

    @abstractmethod
    def list_timed_outcomes(self, channel_id: str) -> list[PublishLogRecord]:
        pass


class JsonPublishLogRepository(PublishLogRepository):
    def _read(self) -> list[dict]:
        if not os.path.exists(LOG_FILE):
            return []
        with open(LOG_FILE, encoding="utf-8") as f:
            return json.load(f)

    def _write(self, rows: list[dict]) -> None:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2)

    def create(self, data: dict[str, Any]) -> PublishLogRecord:
        key = str(data.get("idempotency_key") or "")
        if key:
            existing = self.find_by_idempotency(key)
            if existing:
                return existing
        with _lock:
            rows = self._read()
            log_id = max((r.get("id", 0) for r in rows), default=0) + 1
            row = {"id": log_id, "idempotency_key": "", **data}
            rows.append(row)
            self._write(rows)
        return _to_record(row)

    def update(self, log_id: int, data: dict[str, Any]) -> PublishLogRecord | None:
        with _lock:
            rows = self._read()
            for i, row in enumerate(rows):
                if row.get("id") == log_id:
                    row.update(data)
                    rows[i] = row
                    self._write(rows)
                    return _to_record(row)
        return None

    def find_by_idempotency(self, key: str) -> PublishLogRecord | None:
        if not key:
            return None
        for row in self._read():
            if row.get("idempotency_key") == key:
                return _to_record(row)
        return None

    def list_uploaded_for_channel(self, channel_id: str) -> list[PublishLogRecord]:
        return [
            _to_record(row)
            for row in self._read()
            if row.get("channel_id") == channel_id
            and row.get("status") == "uploaded"
            and row.get("youtube_video_id")
        ]

    def list_future_scheduled(self, channel_id: str) -> list[PublishLogRecord]:
        now = datetime.now(timezone.utc)
        out = []
        for row in self._read():
            if row.get("channel_id") != channel_id:
                continue
            if row.get("status") != "scheduled":
                continue
            pub = _parse_dt(row.get("published_at"))
            if pub and pub > now:
                out.append(_to_record(row))
        return out

    def list_timed_outcomes(self, channel_id: str) -> list[PublishLogRecord]:
        statuses = {"uploaded", "imported"}
        out = []
        for row in self._read():
            if row.get("channel_id") != channel_id:
                continue
            if row.get("status") not in statuses:
                continue
            if not _parse_dt(row.get("published_at")):
                continue
            out.append(_to_record(row))
        return out


class PostgresPublishLogRepository(PublishLogRepository):
    def create(self, data: dict[str, Any]) -> PublishLogRecord:
        key = str(data.get("idempotency_key") or "")
        if key:
            existing = self.find_by_idempotency(key)
            if existing:
                return existing
        session = get_session()
        try:
            row = PublishLog(**data)
            if data.get("published_at") and isinstance(data["published_at"], datetime):
                row.published_at = data["published_at"]
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_record(row)
        except IntegrityError:
            session.rollback()
            if key:
                existing = self.find_by_idempotency(key)
                if existing:
                    return existing
            raise
        finally:
            session.close()

    def update(self, log_id: int, data: dict[str, Any]) -> PublishLogRecord | None:
        session = get_session()
        try:
            row = session.get(PublishLog, log_id)
            if not row:
                return None
            for key, value in data.items():
                if hasattr(row, key):
                    setattr(row, key, value)
            session.commit()
            session.refresh(row)
            return _to_record(row)
        finally:
            session.close()

    def find_by_idempotency(self, key: str) -> PublishLogRecord | None:
        if not key:
            return None
        session = get_session()
        try:
            row = session.execute(
                select(PublishLog).where(PublishLog.idempotency_key == key)
            ).scalar_one_or_none()
            return _to_record(row) if row else None
        finally:
            session.close()

    def list_uploaded_for_channel(self, channel_id: str) -> list[PublishLogRecord]:
        session = get_session()
        try:
            rows = session.scalars(
                select(PublishLog).where(
                    PublishLog.channel_id == channel_id,
                    PublishLog.status == "uploaded",
                    PublishLog.youtube_video_id != "",
                )
            ).all()
            return [_to_record(r) for r in rows]
        finally:
            session.close()

    def list_future_scheduled(self, channel_id: str) -> list[PublishLogRecord]:
        now = datetime.now(timezone.utc)
        session = get_session()
        try:
            rows = session.scalars(
                select(PublishLog).where(
                    PublishLog.channel_id == channel_id,
                    PublishLog.status == "scheduled",
                    PublishLog.published_at.isnot(None),
                    PublishLog.published_at > now,
                )
            ).all()
            return [_to_record(r) for r in rows]
        finally:
            session.close()

    def list_timed_outcomes(self, channel_id: str) -> list[PublishLogRecord]:
        session = get_session()
        try:
            rows = session.scalars(
                select(PublishLog).where(
                    PublishLog.channel_id == channel_id,
                    PublishLog.status.in_(("uploaded", "imported")),
                    PublishLog.published_at.isnot(None),
                )
            ).all()
            return [_to_record(r) for r in rows]
        finally:
            session.close()


class DualPublishLogRepository(PublishLogRepository):
    def __init__(self):
        self._json = JsonPublishLogRepository()
        self._pg = PostgresPublishLogRepository() if postgres_authoritative() else None

    def _primary(self):
        return self._pg if self._pg else self._json

    def create(self, data: dict[str, Any]) -> PublishLogRecord:
        return self._primary().create(data)

    def update(self, log_id: int, data: dict[str, Any]) -> PublishLogRecord | None:
        return self._primary().update(log_id, data)

    def find_by_idempotency(self, key: str) -> PublishLogRecord | None:
        return self._primary().find_by_idempotency(key)

    def list_uploaded_for_channel(self, channel_id: str) -> list[PublishLogRecord]:
        return self._primary().list_uploaded_for_channel(channel_id)

    def list_future_scheduled(self, channel_id: str) -> list[PublishLogRecord]:
        return self._primary().list_future_scheduled(channel_id)

    def list_timed_outcomes(self, channel_id: str) -> list[PublishLogRecord]:
        return self._primary().list_timed_outcomes(channel_id)


_repo = None


def get_publish_log_repository() -> PublishLogRepository:
    global _repo
    if _repo is None:
        _repo = DualPublishLogRepository()
    return _repo
