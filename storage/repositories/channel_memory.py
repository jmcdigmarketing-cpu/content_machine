import json
import os
from abc import ABC, abstractmethod

from sqlalchemy import func, select

from config.paths import (
    CHANNEL_MEMORY_FILE,
    ROOT_DIR,
    ensure_data_dir,
    migrate_file_if_needed,
    resolve_existing_path,
)
from storage.db import get_session
from storage.models import TopicScore
from storage.repository_base import postgres_authoritative

MEMORY_FILE = CHANNEL_MEMORY_FILE
MEMORY_DIR = os.path.join("data", "channel_memory")
DEFAULT_CHANNEL = "default"
_LEGACY_MEMORY = os.path.join(ROOT_DIR, "channel_memory.json")


def _memory_path(channel_id: str) -> str:
    if channel_id == DEFAULT_CHANNEL:
        ensure_data_dir()
        migrate_file_if_needed(MEMORY_FILE, _LEGACY_MEMORY)
        return resolve_existing_path(MEMORY_FILE, _LEGACY_MEMORY)
    os.makedirs(MEMORY_DIR, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in channel_id)
    return os.path.join(MEMORY_DIR, f"{safe}.json")


class ChannelMemoryRepository(ABC):
    @abstractmethod
    def add_score(self, topic: str, score: float, channel_id: str = DEFAULT_CHANNEL) -> None:
        pass

    @abstractmethod
    def get_historical_boost(self, topic: str, channel_id: str = DEFAULT_CHANNEL) -> float:
        pass

    @abstractmethod
    def load_all(self, channel_id: str = DEFAULT_CHANNEL) -> dict[str, list[float]]:
        pass


class JsonChannelMemoryRepository(ChannelMemoryRepository):
    def _read(self, channel_id: str = DEFAULT_CHANNEL) -> dict:
        path = _memory_path(channel_id)
        if not os.path.exists(path):
            return {}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: dict, channel_id: str = DEFAULT_CHANNEL) -> None:
        path = _memory_path(channel_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def add_score(self, topic: str, score: float, channel_id: str = DEFAULT_CHANNEL) -> None:
        data = self._read(channel_id)
        data.setdefault(topic, []).append(score)
        self._write(data, channel_id)

    def get_historical_boost(self, topic: str, channel_id: str = DEFAULT_CHANNEL) -> float:
        data = self._read(channel_id)
        if topic not in data or not data[topic]:
            return 0.0
        avg = sum(data[topic]) / len(data[topic])
        return min(avg * 0.2, 15)

    def load_all(self, channel_id: str = DEFAULT_CHANNEL) -> dict[str, list[float]]:
        return self._read(channel_id)


class PostgresChannelMemoryRepository(ChannelMemoryRepository):
    def add_score(self, topic: str, score: float, channel_id: str = DEFAULT_CHANNEL) -> None:
        session = get_session()
        try:
            session.add(TopicScore(channel_id=channel_id, topic=topic, score=float(score)))
            session.commit()
        finally:
            session.close()

    def get_historical_boost(self, topic: str, channel_id: str = DEFAULT_CHANNEL) -> float:
        session = get_session()
        try:
            avg = session.execute(
                select(func.avg(TopicScore.score)).where(
                    TopicScore.channel_id == channel_id,
                    TopicScore.topic == topic,
                )
            ).scalar()
        finally:
            session.close()
        if avg is None:
            return 0.0
        return min(float(avg) * 0.2, 15)

    def load_all(self, channel_id: str = DEFAULT_CHANNEL) -> dict[str, list[float]]:
        session = get_session()
        try:
            rows = session.execute(
                select(TopicScore.topic, TopicScore.score)
                .where(TopicScore.channel_id == channel_id)
                .order_by(TopicScore.id)
            ).all()
        finally:
            session.close()
        out: dict[str, list[float]] = {}
        for topic, score in rows:
            out.setdefault(topic, []).append(float(score))
        return out


class DualChannelMemoryRepository(ChannelMemoryRepository):
    """PostgreSQL authoritative when configured; JSON fallback otherwise."""

    def __init__(self):
        self._json = JsonChannelMemoryRepository()
        self._pg = PostgresChannelMemoryRepository() if postgres_authoritative() else None

    def _primary(self):
        return self._pg if self._pg else self._json

    def add_score(self, topic: str, score: float, channel_id: str = DEFAULT_CHANNEL) -> None:
        self._primary().add_score(topic, score, channel_id)

    def get_historical_boost(self, topic: str, channel_id: str = DEFAULT_CHANNEL) -> float:
        return self._primary().get_historical_boost(topic, channel_id)

    def load_all(self, channel_id: str = DEFAULT_CHANNEL) -> dict[str, list[float]]:
        return self._primary().load_all(channel_id)


_repo = None


def get_channel_memory_repository() -> ChannelMemoryRepository:
    global _repo
    if _repo is None:
        _repo = DualChannelMemoryRepository()
    return _repo
