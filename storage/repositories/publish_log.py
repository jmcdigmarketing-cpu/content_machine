import json
import os
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, or_, select
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


_LIVE_STATUSES = ("uploaded", "imported")
SEED_SOURCE = "tapin_seed"
SEED_ID_PREFIX = "seed_"


def is_seeded(record: Any) -> bool:
    """True for a row `analytics/seed_tapin` imported (#927): a historical video whose
    publish time the seed invented, not one this machine published."""
    video_id = str(getattr(record, "youtube_video_id", "") or "")
    if video_id.startswith(SEED_ID_PREFIX):
        return True
    try:
        metrics = json.loads(getattr(record, "metrics_json", None) or "{}")
    except (TypeError, ValueError):
        return False
    return isinstance(metrics, dict) and metrics.get("source") == SEED_SOURCE


def _json_default(value: Any) -> Any:
    """#928: the JSON log stored `published_at` datetimes as-is, so json.dump raised
    half-way through a file it had already truncated."""
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _duplicate_seed_ids(rows: list[tuple[int, str]]) -> list[int]:
    """Ids of every seeded row after the first (lowest id) for its video id."""
    seen: set[str] = set()
    extra: list[int] = []
    for row_id, video_id in sorted(rows):
        if video_id in seen:
            extra.append(row_id)
        else:
            seen.add(video_id)
    return extra


def counts_as_live(
    status: str, published_at: datetime | str | None, now: datetime | str | None = None
) -> bool:
    """True for a video that is on YouTube now (#915).

    A scheduled upload is logged `scheduled` and nothing ever moves it to `uploaded`, so
    once its `published_at` has passed it is live and must count - for analytics sync,
    the recommenders, the prediction ledger and the cadence window alike. Times may be
    datetimes or ISO strings.
    """
    if status in _LIVE_STATUSES:
        return True
    published = _parse_dt(published_at)
    current = _parse_dt(now) or datetime.now(timezone.utc)
    return status == "scheduled" and published is not None and published <= current


def _live_condition(now: datetime):
    """The same rule as `counts_as_live`, as a SQL condition."""
    return or_(
        PublishLog.status.in_(_LIVE_STATUSES),
        and_(
            PublishLog.status == "scheduled",
            PublishLog.published_at.isnot(None),
            PublishLog.published_at <= now,
        ),
    )


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
    def remove_duplicate_seeds(self, channel_id: str, *, apply: bool) -> int:
        """Seeded rows repeated by re-seeding (#927): the count, removed when `apply`."""

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
        os.makedirs(os.path.dirname(LOG_FILE) or ".", exist_ok=True)
        # #928: serialise first, then replace - a failed dump no longer truncates the log.
        text = json.dumps(rows, indent=2, default=_json_default)
        tmp = f"{LOG_FILE}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, LOG_FILE)

    def remove_duplicate_seeds(self, channel_id: str, *, apply: bool) -> int:
        with _lock:
            rows = self._read()
            seeded = [
                (int(r.get("id", 0)), str(r.get("youtube_video_id", "")))
                for r in rows
                if r.get("channel_id") == channel_id and is_seeded(_to_record(r))
            ]
            extra = set(_duplicate_seed_ids(seeded))
            if apply and extra:
                self._write([r for r in rows if int(r.get("id", 0)) not in extra])
        return len(extra)

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
        now = datetime.now(timezone.utc)
        return [
            _to_record(row)
            for row in self._read()
            if row.get("channel_id") == channel_id
            and row.get("status") in ("uploaded", "scheduled")
            and counts_as_live(str(row.get("status")), _parse_dt(row.get("published_at")), now)
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
        now = datetime.now(timezone.utc)
        out = []
        for row in self._read():
            if row.get("channel_id") != channel_id:
                continue
            published = _parse_dt(row.get("published_at"))
            if not published or not counts_as_live(str(row.get("status")), published, now):
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
                    PublishLog.status.in_(("uploaded", "scheduled")),
                    _live_condition(datetime.now(timezone.utc)),
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
                    _live_condition(datetime.now(timezone.utc)),
                    PublishLog.published_at.isnot(None),
                )
            ).all()
            return [_to_record(r) for r in rows]
        finally:
            session.close()

    def remove_duplicate_seeds(self, channel_id: str, *, apply: bool) -> int:
        session = get_session()
        try:
            rows = session.scalars(
                select(PublishLog).where(
                    PublishLog.channel_id == channel_id,
                    PublishLog.youtube_video_id.like(f"{SEED_ID_PREFIX}%"),
                )
            ).all()
            extra = set(_duplicate_seed_ids([(int(r.id), str(r.youtube_video_id)) for r in rows]))
            if apply and extra:
                for row in rows:
                    if int(row.id) in extra:
                        session.delete(row)
                session.commit()
            return len(extra)
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

    def remove_duplicate_seeds(self, channel_id: str, *, apply: bool) -> int:
        return self._primary().remove_duplicate_seeds(channel_id, apply=apply)


_repo = None


def get_publish_log_repository() -> PublishLogRepository:
    global _repo
    if _repo is None:
        _repo = DualPublishLogRepository()
    return _repo
