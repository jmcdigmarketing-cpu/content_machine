import json
import os
import tempfile
import threading
import time
from typing import Any

from config.paths import (
    ROOT_DIR,
    SIGNAL_CACHE_FILE,
    ensure_data_dir,
    migrate_file_if_needed,
    resolve_existing_path,
)
from core import process_state
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
        data = None
        entry = cache.get(key)
        if entry:
            timestamp = entry.get("timestamp")
            if timestamp:
                ttl = entry.get("ttl") or TTL_SECONDS
                if time.time() - timestamp <= ttl:
                    data = entry.get("data")
    _record_cache_access(key, data is not None)
    return data


def get_expired(key) -> tuple[Any, float] | None:
    """Expired-but-present payload and its age in seconds, or None.

    Does not record a cache access — the caller already went through get_cached.
    Fresh entries return None here (get_cached should have served them).
    """
    with _cache_lock:
        cache = load_cache()
        entry = cache.get(key)
        if not entry:
            return None
        try:
            timestamp = float(entry.get("timestamp") or 0)
        except (TypeError, ValueError):
            return None
        if timestamp <= 0:
            return None
        ttl = entry.get("ttl") or TTL_SECONDS
        age = time.time() - timestamp
        if age <= float(ttl or 0):
            return None
        data = entry.get("data")
        if data is None:
            return None
        return data, age


def cache_age_seconds(key) -> float | None:
    """Age of a live cache entry in seconds, or None when absent/expired.

    Mirrors `get_expired`'s contract in reverse: it reports on a *fresh* entry
    and, like that function, does not record a cache access - the caller has
    already been through `get_cached`. Exists so a consumer can tell the operator
    how old a reused payload is instead of only that it was reused.
    """
    with _cache_lock:
        cache = load_cache()
        entry = cache.get(key)
        if not entry:
            return None
        try:
            timestamp = float(entry.get("timestamp") or 0)
        except (TypeError, ValueError):
            return None
        if timestamp <= 0:
            return None
        ttl = entry.get("ttl") or TTL_SECONDS
        age = time.time() - timestamp
        return age if age <= float(ttl or 0) else None


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


# --- Cache-hit instrumentation (O8) -----------------------------------------
# Count hits vs misses per cache-key prefix (the signal/source name) so the TTLs
# in register_signals._cache_ttl_for can be tuned from data, and the reliability
# dashboard can show how much caching actually saves. In-process counters are
# merged into data/cache_stats.json on flush_cache_stats() (called once per run).
_stats_lock = threading.Lock()
_stats: dict[str, dict[str, int]] = {}


def _prefix_of(key: str) -> str:
    """`reddit::topic` -> `reddit`; `apify:actor::json` -> `apify`."""
    return key.split("::", 1)[0].split(":", 1)[0] or "unknown"


def _record_cache_access(key: str, hit: bool) -> None:
    prefix = _prefix_of(key)
    with _stats_lock:
        bucket = _stats.setdefault(prefix, {"hits": 0, "misses": 0, "stale": 0})
        bucket["hits" if hit else "misses"] += 1


def record_stale_served(key: str) -> None:
    """A live miss that reused an expired payload. Not a hit — worse than fresh."""
    prefix = _prefix_of(key)
    with _stats_lock:
        bucket = _stats.setdefault(prefix, {"hits": 0, "misses": 0, "stale": 0})
        bucket["stale"] = int(bucket.get("stale") or 0) + 1


def _stats_path() -> str:
    from config.paths import CACHE_STATS_FILE

    return CACHE_STATS_FILE


def _load_stats_file() -> dict[str, dict[str, int]]:
    path = _stats_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _merge_stats(
    base: dict[str, dict[str, int]], extra: dict[str, dict[str, int]]
) -> dict[str, dict[str, int]]:
    out = {k: dict(v) for k, v in base.items()}
    for prefix, counts in extra.items():
        b = out.setdefault(prefix, {"hits": 0, "misses": 0, "stale": 0})
        b["hits"] = b.get("hits", 0) + int(counts.get("hits", 0))
        b["misses"] = b.get("misses", 0) + int(counts.get("misses", 0))
        b["stale"] = b.get("stale", 0) + int(counts.get("stale", 0))
    return out


def get_cache_stats() -> dict[str, Any]:
    """Persisted + in-process hit/miss counts, with an overall hit-rate summary."""
    with _stats_lock:
        live = {k: dict(v) for k, v in _stats.items()}
    merged = _merge_stats(_load_stats_file(), live)
    hits = sum(v.get("hits", 0) for v in merged.values())
    misses = sum(v.get("misses", 0) for v in merged.values())
    stale = sum(v.get("stale", 0) for v in merged.values())
    total = hits + misses
    return {
        "by_prefix": merged,
        "hits": hits,
        "misses": misses,
        "stale_served": stale,
        "total": total,
        "hit_rate": (hits / total) if total else 0.0,
    }


def session_cache_stats() -> dict[str, dict[str, int]]:
    """In-process (not-yet-flushed) hit/miss counters by prefix.

    Approximates "this run since the last flush" — used by the per-run trace
    (core/run_trace.py). The persisted aggregate remains `get_cache_stats()`.
    """
    with _stats_lock:
        return {k: dict(v) for k, v in _stats.items()}


def flush_cache_stats() -> None:
    """Merge in-process counters into data/cache_stats.json, then clear them.

    Called once per discovery run and again at pipeline end via
    ``finalize_run_observability()`` so post-discovery cache hits are captured.
    """
    with _stats_lock:
        if not _stats:
            return
        live = {k: dict(v) for k, v in _stats.items()}
        _stats.clear()
    try:
        merged = _merge_stats(_load_stats_file(), live)
        _write_cache_file(_stats_path(), merged)
    except Exception as exc:
        logger.debug("cache_stats flush skipped: %s", exc)


def reset_cache_stats() -> None:
    """Test/CLI helper — clear both in-process and persisted cache stats."""
    with _stats_lock:
        _stats.clear()
    try:
        _write_cache_file(_stats_path(), {})
    except Exception as exc:
        logger.debug("_write_cache_file skipped: %s", exc)


# --- process-global state reset (#827) --------------------------------------
def _reset_process_state() -> None:
    """In-memory only: `reset_cache_stats()` also rewrites the stats file."""
    global _resolved_path
    with _cache_lock:
        _resolved_path = None
    with _stats_lock:
        _stats.clear()


process_state.register_reset("apis.cache_manager", _reset_process_state)
