import json
import os
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from storage.db import get_session
from storage.models import Asset
from storage.repository_base import postgres_authoritative

ASSETS_FILE = os.path.join("data", "assets.json")
_lock = threading.Lock()


@dataclass
class AssetRecord:
    id: int
    channel_id: str
    content_run_id: int | None
    asset_type: str
    provider: str
    path: str
    source_id: str = ""
    query: str = ""
    attribution: str = ""


class AssetRepository(ABC):
    @abstractmethod
    def create(self, data: dict[str, Any]) -> AssetRecord:
        pass

    @abstractmethod
    def list_for_run(self, content_run_id: int) -> list[AssetRecord]:
        pass


class JsonAssetRepository(AssetRepository):
    def _read(self) -> list[dict]:
        if not os.path.exists(ASSETS_FILE):
            return []
        with open(ASSETS_FILE, encoding="utf-8") as f:
            return json.load(f)

    def _write(self, rows: list[dict]) -> None:
        os.makedirs(os.path.dirname(ASSETS_FILE), exist_ok=True)
        with open(ASSETS_FILE, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2)

    def create(self, data: dict[str, Any]) -> AssetRecord:
        with _lock:
            rows = self._read()
            asset_id = max((r.get("id", 0) for r in rows), default=0) + 1
            row = {"id": asset_id, **data}
            rows.append(row)
            self._write(rows)
        return AssetRecord(**{k: row.get(k) for k in AssetRecord.__dataclass_fields__})

    def list_for_run(self, content_run_id: int) -> list[AssetRecord]:
        return [
            AssetRecord(**{k: r.get(k) for k in AssetRecord.__dataclass_fields__})
            for r in self._read()
            if r.get("content_run_id") == content_run_id
        ]


class PostgresAssetRepository(AssetRepository):
    def create(self, data: dict[str, Any]) -> AssetRecord:
        session = get_session()
        try:
            row = Asset(**data)
            session.add(row)
            session.commit()
            session.refresh(row)
            return AssetRecord(
                id=row.id,
                channel_id=row.channel_id,
                content_run_id=row.content_run_id,
                asset_type=row.asset_type,
                provider=row.provider,
                path=row.path,
                source_id=row.source_id or "",
                query=row.query or "",
                attribution=row.attribution or "",
            )
        finally:
            session.close()

    def list_for_run(self, content_run_id: int) -> list[AssetRecord]:
        from sqlalchemy import select

        session = get_session()
        try:
            rows = session.scalars(
                select(Asset).where(Asset.content_run_id == content_run_id)
            ).all()
            return [
                AssetRecord(
                    id=r.id,
                    channel_id=r.channel_id,
                    content_run_id=r.content_run_id,
                    asset_type=r.asset_type,
                    provider=r.provider,
                    path=r.path,
                    source_id=r.source_id or "",
                    query=r.query or "",
                    attribution=r.attribution or "",
                )
                for r in rows
            ]
        finally:
            session.close()


class DualAssetRepository(AssetRepository):
    def __init__(self):
        self._json = JsonAssetRepository()
        self._pg = PostgresAssetRepository() if postgres_authoritative() else None

    def _primary(self):
        return self._pg if self._pg else self._json

    def create(self, data: dict[str, Any]) -> AssetRecord:
        return self._primary().create(data)

    def list_for_run(self, content_run_id: int) -> list[AssetRecord]:
        return self._primary().list_for_run(content_run_id)


_repo = None


def get_asset_repository() -> AssetRepository:
    global _repo
    if _repo is None:
        _repo = DualAssetRepository()
    return _repo
