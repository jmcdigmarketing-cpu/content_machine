"""Cross-run quota/credit state — persisted, TTL'd, fail-open.

Why this exists
---------------
The Apify circuit breaker and the per-signal breaker are *process-scoped*: every
fresh `py main.py` invocation re-pays the first failing call per exhausted provider
and re-runs the Apify preflight network round-trip. This module remembers two
things across runs in `data/quota_state.json` so a new process can skip work it can
already know is pointless:

- **Exhaustion records** (`mark_exhausted`/`is_exhausted`): "provider X is out of
  credits / unauthorized until time T". A later run skips it without re-paying.
- **TTL'd key/values** (`set_value`/`get_value`): e.g. the last Apify usage reading,
  so back-to-back runs reuse it instead of re-hitting `/users/me`.

This is the seed of the eventual unified quota governor (credit_efficiency.md O11);
for now it's a thin, dependency-light store consulted by `apis/apify_client.py` and
`core/llm_router.py`.

Design notes
------------
- **Fail-open:** any read/write error is swallowed and treated as "not exhausted /
  no cached value", so a corrupt or unwritable state file never blocks a run.
- **Lazy expiry:** expired records are ignored on read and pruned on the next write.
- **Scope + name:** records are keyed `"{scope}:{name}"` (e.g. `apify:main`,
  `llm:openrouter`) so multiple subsystems share one file without colliding.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from typing import Any

from config.paths import QUOTA_STATE_FILE, ensure_data_dir
from core.logging import get_logger

logger = get_logger("core.quota_state")

_lock = threading.RLock()
_DEFAULT_TTL = 6 * 60 * 60  # 6h — conservative; re-checks a few times a day


def _key(scope: str, name: str) -> str:
    return f"{scope}:{name}"


def _load() -> dict[str, Any]:
    path = QUOTA_STATE_FILE
    if not os.path.exists(path):
        return {"disabled": {}, "kv": {}}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"disabled": {}, "kv": {}}
        data.setdefault("disabled", {})
        data.setdefault("kv", {})
        return data
    except Exception as exc:
        logger.debug("quota_state read failed (%s): %s", path, exc)
        return {"disabled": {}, "kv": {}}


def _prune(data: dict[str, Any], now: float) -> dict[str, Any]:
    for bucket in ("disabled", "kv"):
        section = data.get(bucket) or {}
        data[bucket] = {
            k: v
            for k, v in section.items()
            if isinstance(v, dict) and float(v.get("until", 0) or 0) > now
        }
    return data


def _save(data: dict[str, Any]) -> None:
    try:
        ensure_data_dir()
        directory = os.path.dirname(QUOTA_STATE_FILE) or "."
        fd, tmp = tempfile.mkstemp(suffix=".tmp", prefix="quota_state_", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            os.replace(tmp, QUOTA_STATE_FILE)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception as exc:
        # Fail-open: persistence is an optimization, never load-bearing.
        logger.debug("quota_state write skipped: %s", exc)


def mark_exhausted(scope: str, name: str, reason: str, ttl_seconds: int | None = None) -> None:
    """Record `{scope}:{name}` as exhausted for `ttl_seconds` (default 6h)."""
    now = time.time()
    until = now + (ttl_seconds if ttl_seconds is not None else _DEFAULT_TTL)
    with _lock:
        data = _prune(_load(), now)
        data["disabled"][_key(scope, name)] = {"reason": reason, "until": until}
        _save(data)


def is_exhausted(scope: str, name: str) -> tuple[bool, str]:
    """Return (exhausted, reason). Expired records read as not-exhausted."""
    now = time.time()
    with _lock:
        rec = (_load().get("disabled") or {}).get(_key(scope, name))
    if not isinstance(rec, dict):
        return False, ""
    if float(rec.get("until", 0) or 0) <= now:
        return False, ""
    return True, str(rec.get("reason", ""))


def clear_exhausted(scope: str, name: str) -> None:
    """Remove an exhaustion record (e.g. operator fixed the key)."""
    with _lock:
        data = _load()
        if data.get("disabled", {}).pop(_key(scope, name), None) is not None:
            _save(data)


def set_value(key: str, value: Any, ttl_seconds: int) -> None:
    """Cache a small value (e.g. last usage reading) for `ttl_seconds`."""
    now = time.time()
    with _lock:
        data = _prune(_load(), now)
        data["kv"][key] = {"value": value, "until": now + ttl_seconds}
        _save(data)


def get_value(key: str, default: Any = None) -> Any:
    """Return a cached value, or `default` if missing/expired."""
    now = time.time()
    with _lock:
        rec = (_load().get("kv") or {}).get(key)
    if not isinstance(rec, dict) or float(rec.get("until", 0) or 0) <= now:
        return default
    return rec.get("value", default)


def increment_value(key: str, delta: float, ttl_seconds: int, *, default: float = 0.0) -> None:
    """Atomically add ``delta`` to a numeric cached value (read-modify-write under lock)."""
    if not delta:
        return
    now = time.time()
    with _lock:
        data = _prune(_load(), now)
        rec = (data.get("kv") or {}).get(key)
        current = default
        if isinstance(rec, dict) and float(rec.get("until", 0) or 0) > now:
            try:
                current = float(rec.get("value", default) or default)
            except (TypeError, ValueError):
                current = default
        data["kv"][key] = {"value": round(current + delta, 6), "until": now + ttl_seconds}
        _save(data)


def reset_all() -> None:
    """Test/CLI helper — wipe all persisted quota state."""
    with _lock:
        _save({"disabled": {}, "kv": {}})
