"""
Apify HTTP client — runs actors and fetches dataset results.

Two keys are supported:
  APIFY_CONTENT_MACHINE_KEY — general-purpose actor runs (Reddit, etc.)
  APIFY_BENABLE_BOT         — dedicated TikTok scraper actor key

Usage:
    from apis.apify_client import run_actor, fetch_dataset

Each actor run costs Apify credits; results are cached locally for TTL seconds
to avoid redundant calls during a session.
"""

from __future__ import annotations

import json
import os
from typing import Any

import requests

from apis.cache_manager import build_key, get_cached, set_cache
from core.logging import get_logger

logger = get_logger("apis.apify_client")

_BASE = "https://api.apify.com/v2"
_DEFAULT_TTL = 3600 * 6  # 6h cache
_MAX_FAILS = 2  # consecutive timeouts/errors before disabling for the session

# Process-level circuit breaker: once Apify is out of credits, unauthorized, or
# repeatedly failing, stop calling it so we don't burn credits/time re-trying
# across every variant during discovery.
_state: dict[str, Any] = {"disabled": False, "reason": "", "fails": 0, "checked": False}


def apify_disabled() -> bool:
    return bool(_state["disabled"])


def apify_status() -> str:
    if _state["disabled"]:
        return f"OFF — {_state['reason']}"
    return "ON"


def disable_apify(reason: str) -> None:
    if not _state["disabled"]:
        logger.warning("Apify disabled for this session: %s", reason)
    _state["disabled"] = True
    _state["reason"] = reason


def reset_apify_state() -> None:
    """Test/CLI helper — clear the circuit breaker."""
    _state.update({"disabled": False, "reason": "", "fails": 0, "checked": False})


def _note_failure() -> None:
    _state["fails"] += 1
    if _state["fails"] >= _MAX_FAILS:
        disable_apify("repeated Apify failures — skipping social signals this session")


def _key(purpose: str = "main") -> str:
    if purpose == "tiktok":
        return os.getenv("APIFY_BENABLE_BOT", "").strip()
    return os.getenv("APIFY_CONTENT_MACHINE_KEY", "").strip()


def _headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def run_actor(
    actor_id: str,
    input_data: dict[str, Any],
    *,
    purpose: str = "main",
    timeout_secs: int = 120,
    memory_mbytes: int = 256,
    ttl: int = _DEFAULT_TTL,
) -> list[dict] | None:
    """
    Synchronously run an Apify actor and return its dataset items.

    Results are cached by (actor_id, input_data) for `ttl` seconds.
    Returns None if the actor is not configured or fails.
    """
    if _state["disabled"]:
        return None

    api_key = _key(purpose)
    if not api_key:
        env_var = "APIFY_BENABLE_BOT" if purpose == "tiktok" else "APIFY_CONTENT_MACHINE_KEY"
        logger.debug("Apify key not set (%s) — skipping actor %s", env_var, actor_id)
        return None

    cache_key = build_key(f"apify:{actor_id}", json.dumps(input_data, sort_keys=True))
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    # Apify's REST path uses "username~actor-name", not "username/actor-name".
    path_actor = actor_id.replace("/", "~")
    url = f"{_BASE}/acts/{path_actor}/run-sync-get-dataset-items"
    params = {
        "token": api_key,
        "timeout": timeout_secs,
        "memoryMbytes": memory_mbytes,
        "format": "json",
    }
    try:
        resp = requests.post(
            url,
            params=params,
            json=input_data,
            timeout=timeout_secs + 15,
        )
        # Account-wide problems → trip the circuit breaker (don't retry this session).
        if resp.status_code in (401, 402, 403):
            disable_apify(f"Apify credits/auth ({resp.status_code}) — skipping social signals")
            return None
        # run-sync-get-dataset-items returns 200 OR 201 (Created) with the items.
        if resp.status_code not in (200, 201):
            # Actor-specific error (bad input, 404, 500) — fail just this actor.
            logger.warning(
                "Apify actor %s returned %s: %s", actor_id, resp.status_code, resp.text[:200]
            )
            return None
        items = resp.json() if isinstance(resp.json(), list) else []
        set_cache(cache_key, items, ttl_seconds=ttl)
        _state["fails"] = 0
        return items
    except requests.Timeout:
        logger.warning("Apify actor %s timed out after %ss", actor_id, timeout_secs)
        _note_failure()
        return None
    except Exception as exc:
        logger.warning("Apify actor %s failed: %s", actor_id, exc)
        _note_failure()
        return None


def apify_preflight(purpose: str = "main") -> tuple[bool, str]:
    """
    One cheap account check before discovery — verifies the key works and the
    monthly usage limit isn't already hit. Runs at most once per process; trips
    the circuit breaker on a hard failure so the actor calls skip instantly.

    Returns (available, status_message).
    """
    if _state["disabled"]:
        return False, _state["reason"]
    if _state["checked"]:
        return True, "ON"
    _state["checked"] = True

    api_key = _key(purpose)
    if not api_key:
        disable_apify("no APIFY_CONTENT_MACHINE_KEY set")
        return False, _state["reason"]

    try:
        resp = requests.get(f"{_BASE}/users/me", params={"token": api_key}, timeout=12)
    except Exception as exc:
        # Network blip — don't disable; let per-actor logic decide.
        logger.debug("Apify preflight network error: %s", exc)
        return True, "ON (precheck skipped)"

    if resp.status_code in (401, 403):
        disable_apify("Apify key unauthorized (preflight)")
        return False, _state["reason"]
    if resp.status_code != 200:
        return True, "ON (precheck inconclusive)"

    try:
        data = resp.json().get("data", {}) or {}
        usage = data.get("monthlyUsageCycleUsdSpent") or data.get("monthlyUsageUsd")
        limit = data.get("monthlyUsageCycleMaxUsd") or (data.get("limits", {}) or {}).get(
            "maxMonthlyUsageUsd"
        )
        if isinstance(usage, int | float) and isinstance(limit, int | float) and limit > 0:
            if usage >= limit:
                disable_apify(f"Apify monthly limit reached (${usage:.2f}/${limit:.2f})")
                return False, _state["reason"]
            return True, f"ON (${usage:.2f}/${limit:.2f} used)"
    except Exception as exc:
        logger.debug("Apify preflight parse error: %s", exc)
    return True, "ON"


def fetch_dataset(dataset_id: str, *, purpose: str = "main") -> list[dict] | None:
    """Fetch items from an existing Apify dataset by ID."""
    api_key = _key(purpose)
    if not api_key:
        return None
    try:
        resp = requests.get(
            f"{_BASE}/datasets/{dataset_id}/items",
            params={"token": api_key, "format": "json"},
            timeout=30,
        )
        if resp.status_code != 200:
            return None
        return resp.json() if isinstance(resp.json(), list) else []
    except Exception as exc:
        logger.debug("Apify dataset fetch failed: %s", exc)
        return None
