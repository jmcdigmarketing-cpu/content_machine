import json
import os
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from sqlalchemy import desc, select

from storage.db import get_session
from storage.models import ContentRun
from storage.repository_base import postgres_authoritative

RUNS_FILE = os.path.join("data", "content_runs.json")
_lock = threading.Lock()
_next_json_id = 0


@dataclass
class ContentRunRecord:
    id: int
    channel_id: str
    input_topic: str
    selected_topic: str
    status: str
    composite_score: float
    signals_json: str = "{}"
    variants_json: str = "[]"
    title: str = ""
    description: str = ""
    tags_json: str = "[]"
    brief_version: str = ""
    prompt_version: str = ""
    script_preview: str = ""
    mp3_path: str = ""
    mp4_path: str = ""
    timings_json: str = "{}"
    abort_reason: str = ""
    features_json: str = "{}"


class ContentRunRepository(ABC):
    @abstractmethod
    def create(self, data: dict[str, Any]) -> ContentRunRecord:
        pass

    @abstractmethod
    def update(self, run_id: int, data: dict[str, Any]) -> ContentRunRecord | None:
        pass

    @abstractmethod
    def get(self, run_id: int) -> ContentRunRecord | None:
        pass

    @abstractmethod
    def list_for_channel(
        self, channel_id: str, *, status: str | None = None
    ) -> list[ContentRunRecord]:
        pass


class JsonContentRunRepository(ContentRunRepository):
    def _read(self) -> list[dict]:
        if not os.path.exists(RUNS_FILE):
            return []
        with open(RUNS_FILE, encoding="utf-8") as f:
            return json.load(f)

    def _write(self, rows: list[dict]) -> None:
        os.makedirs(os.path.dirname(RUNS_FILE), exist_ok=True)
        with open(RUNS_FILE, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2)

    def _to_record(self, row: dict) -> ContentRunRecord:
        return ContentRunRecord(
            id=int(row.get("id", 0)),
            channel_id=str(row.get("channel_id", "default")),
            input_topic=str(row.get("input_topic", "")),
            selected_topic=str(row.get("selected_topic", "")),
            status=str(row.get("status", "")),
            composite_score=float(row.get("composite_score", 0)),
            signals_json=str(row.get("signals_json", "{}")),
            variants_json=str(row.get("variants_json", "[]")),
            title=str(row.get("title", "")),
            description=str(row.get("description", "")),
            tags_json=str(row.get("tags_json", "[]")),
            brief_version=str(row.get("brief_version", "")),
            prompt_version=str(row.get("prompt_version", "")),
            script_preview=str(row.get("script_preview", "")),
            mp3_path=str(row.get("mp3_path", "")),
            mp4_path=str(row.get("mp4_path", "")),
            timings_json=str(row.get("timings_json", "{}")),
            abort_reason=str(row.get("abort_reason", "")),
            features_json=str(row.get("features_json", "{}")),
        )

    def create(self, data: dict[str, Any]) -> ContentRunRecord:
        global _next_json_id
        with _lock:
            rows = self._read()
            run_id = max((r.get("id", 0) for r in rows), default=0) + 1
            row = {"id": run_id, **data}
            rows.append(row)
            self._write(rows)
        return self._to_record(row)

    def update(self, run_id: int, data: dict[str, Any]) -> ContentRunRecord | None:
        with _lock:
            rows = self._read()
            for i, row in enumerate(rows):
                if row.get("id") == run_id:
                    row.update(data)
                    rows[i] = row
                    self._write(rows)
                    return self._to_record(row)
        return None

    def get(self, run_id: int) -> ContentRunRecord | None:
        for row in self._read():
            if row.get("id") == run_id:
                return self._to_record(row)
        return None

    def list_for_channel(
        self, channel_id: str, *, status: str | None = None
    ) -> list[ContentRunRecord]:
        out = []
        for row in self._read():
            if row.get("channel_id") != channel_id:
                continue
            if status and row.get("status") != status:
                continue
            out.append(self._to_record(row))
        return sorted(out, key=lambda r: r.id, reverse=True)


class PostgresContentRunRepository(ContentRunRepository):
    def _row_to_record(self, row: ContentRun) -> ContentRunRecord:
        return ContentRunRecord(
            id=row.id,
            channel_id=row.channel_id,
            input_topic=row.input_topic,
            selected_topic=row.selected_topic,
            status=row.status,
            composite_score=float(row.composite_score),
            signals_json=row.signals_json,
            variants_json=row.variants_json,
            title=row.title,
            description=row.description,
            tags_json=getattr(row, "tags_json", "[]") or "[]",
            brief_version=getattr(row, "brief_version", "") or "",
            prompt_version=getattr(row, "prompt_version", "") or "",
            script_preview=row.script_preview,
            mp3_path=row.mp3_path,
            mp4_path=row.mp4_path,
            timings_json=row.timings_json,
            abort_reason=row.abort_reason,
            features_json=getattr(row, "features_json", "{}") or "{}",
        )

    def create(self, data: dict[str, Any]) -> ContentRunRecord:
        session = get_session()
        try:
            row = ContentRun(**data)
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._row_to_record(row)
        finally:
            session.close()

    def update(self, run_id: int, data: dict[str, Any]) -> ContentRunRecord | None:
        session = get_session()
        try:
            row = session.get(ContentRun, run_id)
            if not row:
                return None
            for key, value in data.items():
                if hasattr(row, key):
                    setattr(row, key, value)
            session.commit()
            session.refresh(row)
            return self._row_to_record(row)
        finally:
            session.close()

    def get(self, run_id: int) -> ContentRunRecord | None:
        session = get_session()
        try:
            row = session.get(ContentRun, run_id)
            return self._row_to_record(row) if row else None
        finally:
            session.close()

    def list_for_channel(
        self, channel_id: str, *, status: str | None = None
    ) -> list[ContentRunRecord]:
        session = get_session()
        try:
            stmt = select(ContentRun).where(ContentRun.channel_id == channel_id)
            if status:
                stmt = stmt.where(ContentRun.status == status)
            rows = session.scalars(stmt.order_by(desc(ContentRun.id))).all()
            return [self._row_to_record(r) for r in rows]
        finally:
            session.close()


class DualContentRunRepository(ContentRunRepository):
    def __init__(self):
        self._json = JsonContentRunRepository()
        self._pg = PostgresContentRunRepository() if postgres_authoritative() else None

    def _primary(self):
        return self._pg if self._pg else self._json

    def create(self, data: dict[str, Any]) -> ContentRunRecord:
        return self._primary().create(data)

    def update(self, run_id: int, data: dict[str, Any]) -> ContentRunRecord | None:
        return self._primary().update(run_id, data)

    def get(self, run_id: int) -> ContentRunRecord | None:
        return self._primary().get(run_id)

    def list_for_channel(
        self, channel_id: str, *, status: str | None = None
    ) -> list[ContentRunRecord]:
        return self._primary().list_for_channel(channel_id, status=status)


_repo = None


def get_content_run_repository() -> ContentRunRepository:
    global _repo
    if _repo is None:
        _repo = DualContentRunRepository()
    return _repo
