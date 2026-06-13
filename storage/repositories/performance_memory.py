import json
import os
from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy import select

from config.paths import (
    PERFORMANCE_MEMORY_FILE,
    ROOT_DIR,
    ensure_data_dir,
    migrate_file_if_needed,
    resolve_existing_path,
)
from storage.db import get_session
from storage.models import PerformanceEntry
from storage.repository_base import postgres_authoritative

MEMORY_FILE = PERFORMANCE_MEMORY_FILE

MEMORY_DIR = os.path.join("data", "performance_memory")
_LEGACY_MEMORY = os.path.join(ROOT_DIR, "performance_memory.json")

DEFAULT_CHANNEL = "default"

PROXY_SOURCE = "proxy"


def _memory_path(channel_id: str) -> str:
    if channel_id == DEFAULT_CHANNEL:
        ensure_data_dir()
        migrate_file_if_needed(MEMORY_FILE, _LEGACY_MEMORY)
        return resolve_existing_path(MEMORY_FILE, _LEGACY_MEMORY)

    os.makedirs(MEMORY_DIR, exist_ok=True)

    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in channel_id)

    return os.path.join(MEMORY_DIR, f"{safe}.json")


def _engagement_from_entry(entry: dict[str, Any]) -> float | None:
    if entry.get("source") == PROXY_SOURCE:
        return None

    if "engaged_rate" in entry:
        return float(entry["engaged_rate"])

    if entry.get("source") in ("tapin_seed", "youtube_analytics"):
        if entry.get("alignment_score") is not None:
            return float(entry["alignment_score"]) / 100.0

    return None


class PerformanceMemoryRepository(ABC):
    @abstractmethod
    def log_performance(self, entry: dict[str, Any], channel_id: str = DEFAULT_CHANNEL) -> None:
        pass

    @abstractmethod
    def get_domain_average(self, domain: str, channel_id: str = DEFAULT_CHANNEL) -> float:
        pass

    @abstractmethod
    def get_domain_engagement_average(
        self, domain: str, channel_id: str = DEFAULT_CHANNEL
    ) -> float:
        pass

    @abstractmethod
    def get_channel_engagement_average(self, channel_id: str = DEFAULT_CHANNEL) -> float:
        pass

    @abstractmethod
    def load_all(self, channel_id: str = DEFAULT_CHANNEL) -> list[dict]:
        pass

    @abstractmethod
    def has_outcome_data(self, channel_id: str = DEFAULT_CHANNEL) -> bool:
        pass


class JsonPerformanceMemoryRepository(PerformanceMemoryRepository):
    def _read(self, channel_id: str = DEFAULT_CHANNEL) -> list:
        path = _memory_path(channel_id)

        if not os.path.exists(path):
            return []

        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: list, channel_id: str = DEFAULT_CHANNEL) -> None:
        path = _memory_path(channel_id)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def log_performance(self, entry: dict[str, Any], channel_id: str = DEFAULT_CHANNEL) -> None:
        data = self._read(channel_id)

        row = dict(entry)

        row.setdefault("channel_id", channel_id)

        data.append(row)

        self._write(data, channel_id)

    def _outcome_entries(self, channel_id: str) -> list[dict]:
        return [e for e in self._read(channel_id) if _engagement_from_entry(e) is not None]

    def get_domain_engagement_average(
        self, domain: str, channel_id: str = DEFAULT_CHANNEL
    ) -> float:
        entries = [e for e in self._outcome_entries(channel_id) if e.get("domain") == domain]

        if not entries:
            return 0.0

        rates = [_engagement_from_entry(e) for e in entries]

        rates = [r for r in rates if r is not None]

        return sum(rates) / len(rates) if rates else 0.0

    def get_channel_engagement_average(self, channel_id: str = DEFAULT_CHANNEL) -> float:
        entries = self._outcome_entries(channel_id)

        if not entries:
            return 0.0

        rates = [_engagement_from_entry(e) for e in entries]

        rates = [r for r in rates if r is not None]

        return sum(rates) / len(rates) if rates else 0.0

    def get_domain_average(self, domain: str, channel_id: str = DEFAULT_CHANNEL) -> float:
        avg = self.get_domain_engagement_average(domain, channel_id)

        if avg <= 0:
            return 1.0

        channel_avg = self.get_channel_engagement_average(channel_id)

        if channel_avg <= 0:
            return 1.0

        return max(0.4, min(1.6, avg / channel_avg))

    def has_outcome_data(self, channel_id: str = DEFAULT_CHANNEL) -> bool:
        return len(self._outcome_entries(channel_id)) > 0

    def load_all(self, channel_id: str = DEFAULT_CHANNEL) -> list[dict]:
        return self._read(channel_id)


class PostgresPerformanceMemoryRepository(PerformanceMemoryRepository):
    def _rows_as_entries(self, channel_id: str) -> list[dict]:
        session = get_session()

        try:
            rows = session.execute(
                select(PerformanceEntry).where(PerformanceEntry.channel_id == channel_id)
            ).scalars()

            out = []

            for row in rows:
                payload = json.loads(row.payload_json or "{}")

                payload.setdefault("domain", row.domain)

                payload.setdefault("alignment_score", row.alignment_score)

                payload.setdefault("channel_id", row.channel_id)

                out.append(payload)

            return out

        finally:
            session.close()

    def log_performance(self, entry: dict[str, Any], channel_id: str = DEFAULT_CHANNEL) -> None:
        session = get_session()

        try:
            session.add(
                PerformanceEntry(
                    channel_id=channel_id,
                    domain=entry.get("domain", "neutral"),
                    alignment_score=float(entry.get("alignment_score", 0)),
                    payload_json=json.dumps(entry),
                )
            )

            session.commit()

        finally:
            session.close()

    def _outcome_entries(self, channel_id: str) -> list[dict]:
        return [
            e for e in self._rows_as_entries(channel_id) if _engagement_from_entry(e) is not None
        ]

    def get_domain_engagement_average(
        self, domain: str, channel_id: str = DEFAULT_CHANNEL
    ) -> float:
        entries = [e for e in self._outcome_entries(channel_id) if e.get("domain") == domain]

        if not entries:
            return 0.0

        rates = [_engagement_from_entry(e) for e in entries]

        rates = [r for r in rates if r is not None]

        return sum(rates) / len(rates) if rates else 0.0

    def get_channel_engagement_average(self, channel_id: str = DEFAULT_CHANNEL) -> float:
        entries = self._outcome_entries(channel_id)

        if not entries:
            return 0.0

        rates = [_engagement_from_entry(e) for e in entries]

        rates = [r for r in rates if r is not None]

        return sum(rates) / len(rates) if rates else 0.0

    def get_domain_average(self, domain: str, channel_id: str = DEFAULT_CHANNEL) -> float:
        avg = self.get_domain_engagement_average(domain, channel_id)

        if avg <= 0:
            return 1.0

        channel_avg = self.get_channel_engagement_average(channel_id)

        if channel_avg <= 0:
            return 1.0

        return max(0.4, min(1.6, avg / channel_avg))

    def has_outcome_data(self, channel_id: str = DEFAULT_CHANNEL) -> bool:
        return len(self._outcome_entries(channel_id)) > 0

    def load_all(self, channel_id: str = DEFAULT_CHANNEL) -> list[dict]:
        return self._rows_as_entries(channel_id)


class DualPerformanceMemoryRepository(PerformanceMemoryRepository):
    def __init__(self):
        self._json = JsonPerformanceMemoryRepository()

        self._pg = PostgresPerformanceMemoryRepository() if postgres_authoritative() else None

    def _primary(self):
        return self._pg if self._pg else self._json

    def log_performance(self, entry: dict[str, Any], channel_id: str = DEFAULT_CHANNEL) -> None:
        self._primary().log_performance(entry, channel_id)

    def get_domain_average(self, domain: str, channel_id: str = DEFAULT_CHANNEL) -> float:
        return self._primary().get_domain_average(domain, channel_id)

    def get_domain_engagement_average(
        self, domain: str, channel_id: str = DEFAULT_CHANNEL
    ) -> float:
        return self._primary().get_domain_engagement_average(domain, channel_id)

    def get_channel_engagement_average(self, channel_id: str = DEFAULT_CHANNEL) -> float:
        return self._primary().get_channel_engagement_average(channel_id)

    def has_outcome_data(self, channel_id: str = DEFAULT_CHANNEL) -> bool:
        return self._primary().has_outcome_data(channel_id)

    def load_all(self, channel_id: str = DEFAULT_CHANNEL) -> list[dict]:
        return self._primary().load_all(channel_id)


_repo = None


def get_performance_memory_repository() -> PerformanceMemoryRepository:
    global _repo

    if _repo is None:
        _repo = DualPerformanceMemoryRepository()

    return _repo
