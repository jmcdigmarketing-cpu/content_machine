import json
import os
import tempfile
import threading
import time

from config.paths import (
    ROOT_DIR,
    SIGNAL_CACHE_FILE,
    ensure_data_dir,
    migrate_file_if_needed,
    resolve_existing_path,
)
from core.logging import get_logger

logger = get_logger("apis.cache_manager")

_cache_lock = threading.Lock()
_resolved_path: str | None = None
TTL_SECONDS = 60 * 60 * 3  # 3 hours

_LEGACY_CACHE = os.path.join(ROOT_DIR, "signal_cache.json")


def _cache_path() -> str:
    global _resolved_path
    if _resolved_path:
        return _resolved_path

    ensure_data_dir()
    migrate_file_if_needed(SIGNAL_CACHE_FILE, _LEGACY_CACHE)
    _resolved_path = resolve_existing_path(SIGNAL_CACHE_FILE, _LEGACY_CACHE)
    return _resolved_path


def load_cache():
    path = _cache_path()
    if not os.path.exists(path):
        return {}

    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("Could not read signal cache %s: %s", path, exc)
        return {}


def _write_cache_file(path: str, cache: dict) -> None:
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        suffix=".tmp",
        prefix="signal_cache_",
        dir=directory,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, default=str)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def save_cache(cache):
    path = _cache_path()
    last_error = None

    for attempt in range(4):
        try:
            _write_cache_file(path, cache)
            return
        except (PermissionError, OSError) as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(0.05 * (attempt + 1))
                continue
            raise last_error from exc


def build_key(prefix, topic):
    return f"{prefix}::{topic.lower()}"


def get_cached(key):
    with _cache_lock:
        cache = load_cache()

        if key not in cache:
            return None

        entry = cache[key]
        timestamp = entry.get("timestamp")

        if not timestamp:
            return None

        ttl = entry.get("ttl") or TTL_SECONDS
        if time.time() - timestamp > ttl:
            return None

        return entry.get("data")


def set_cache(key, data, ttl_seconds=None):
    with _cache_lock:
        try:
            cache = load_cache()

            cache[key] = {
                "timestamp": time.time(),
                "data": data,
                "ttl": ttl_seconds or TTL_SECONDS,
            }

            save_cache(cache)
        except Exception as exc:
            logger.warning(
                "Signal cache write skipped for %s (%s): %s",
                key,
                _cache_path(),
                exc,
            )
