"""Thumbnail score persistence (Postgres + JSON fallback)."""

from __future__ import annotations

import json
import os
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from storage.db import get_session
from storage.models import ThumbnailScore
from storage.repository_base import postgres_authoritative

SCORES_FILE = os.path.join("data", "thumbnail_scores.json")
_lock = threading.Lock()


def _row_to_record(row: dict) -> ThumbnailScoreRecord:
    return ThumbnailScoreRecord(
        id=int(row.get("id", 0)),
        content_run_id=int(row.get("content_run_id", 0)),
        channel_id=str(row.get("channel_id", "default")),
        image_path=str(row.get("image_path", "")),
        topic=str(row.get("topic", "")),
        curiosity=float(row.get("curiosity", 0)),
        clarity=float(row.get("clarity", 0)),
        contrast=float(row.get("contrast", 0)),
        emotion=float(row.get("emotion", 0)),
        overall=float(row.get("overall", 0)),
        suggestions_json=str(row.get("suggestions_json", "[]")),
        source=str(row.get("source", "heuristic")),
    )


@dataclass
class ThumbnailScoreRecord:
    id: int
    content_run_id: int
    channel_id: str
    image_path: str
    topic: str
    curiosity: float = 0.0
    clarity: float = 0.0
    contrast: float = 0.0
    emotion: float = 0.0
    overall: float = 0.0
    suggestions_json: str = "[]"
    source: str = "heuristic"

    def suggestions(self) -> list[str]:
        try:
            data = json.loads(self.suggestions_json or "[]")
            return [str(s) for s in data if s]
        except json.JSONDecodeError:
            return []


class ThumbnailScoreRepository(ABC):
    @abstractmethod
    def create(self, data: dict[str, Any]) -> ThumbnailScoreRecord:
        pass

    @abstractmethod
    def latest_for_run(self, content_run_id: int) -> ThumbnailScoreRecord | None:
        pass


class JsonThumbnailScoreRepository(ThumbnailScoreRepository):
    def _read(self) -> list[dict]:
        if not os.path.exists(SCORES_FILE):
            return []
        with open(SCORES_FILE, encoding="utf-8") as f:
            return json.load(f)

    def _write(self, rows: list[dict]) -> None:
        os.makedirs(os.path.dirname(SCORES_FILE), exist_ok=True)
        with open(SCORES_FILE, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2)

    def create(self, data: dict[str, Any]) -> ThumbnailScoreRecord:
        with _lock:
            rows = self._read()
            row_id = max((r.get("id", 0) for r in rows), default=0) + 1
            row = {"id": row_id, **data}
            rows.append(row)
            self._write(rows)
        return _row_to_record(row)

    def latest_for_run(self, content_run_id: int) -> ThumbnailScoreRecord | None:
        rows = [r for r in self._read() if r.get("content_run_id") == content_run_id]
        if not rows:
            return None
        row = max(rows, key=lambda r: r.get("id", 0))
        return _row_to_record(row)


class PostgresThumbnailScoreRepository(ThumbnailScoreRepository):
    def create(self, data: dict[str, Any]) -> ThumbnailScoreRecord:
        session = get_session()
        try:
            row = ThumbnailScore(**data)
            session.add(row)
            session.commit()
            session.refresh(row)
            return ThumbnailScoreRecord(
                id=row.id,
                content_run_id=row.content_run_id,
                channel_id=row.channel_id,
                image_path=row.image_path,
                topic=row.topic,
                curiosity=row.curiosity,
                clarity=row.clarity,
                contrast=row.contrast,
                emotion=row.emotion,
                overall=row.overall,
                suggestions_json=row.suggestions_json or "[]",
                source=row.source or "heuristic",
            )
        finally:
            session.close()

    def latest_for_run(self, content_run_id: int) -> ThumbnailScoreRecord | None:
        session = get_session()
        try:
            row = session.scalars(
                select(ThumbnailScore)
                .where(ThumbnailScore.content_run_id == content_run_id)
                .order_by(ThumbnailScore.id.desc())
                .limit(1)
            ).first()
            if not row:
                return None
            return ThumbnailScoreRecord(
                id=row.id,
                content_run_id=row.content_run_id,
                channel_id=row.channel_id,
                image_path=row.image_path,
                topic=row.topic,
                curiosity=row.curiosity,
                clarity=row.clarity,
                contrast=row.contrast,
                emotion=row.emotion,
                overall=row.overall,
                suggestions_json=row.suggestions_json or "[]",
                source=row.source or "heuristic",
            )
        finally:
            session.close()


class DualThumbnailScoreRepository(ThumbnailScoreRepository):
    def _primary(self) -> ThumbnailScoreRepository:
        if postgres_authoritative():
            return PostgresThumbnailScoreRepository()
        return JsonThumbnailScoreRepository()

    def create(self, data: dict[str, Any]) -> ThumbnailScoreRecord:
        return self._primary().create(data)

    def latest_for_run(self, content_run_id: int) -> ThumbnailScoreRecord | None:
        return self._primary().latest_for_run(content_run_id)


_repo = None


def get_thumbnail_score_repository() -> ThumbnailScoreRepository:
    global _repo
    if _repo is None:
        _repo = DualThumbnailScoreRepository()
    return _repo
