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
_state: dict[str, Any] = {
    "disabled": False,
    "reason": "",
    "fails": 0,
    "checked": False,
    "synced": False,  # whether we've consulted cross-run persisted state yet
}


def _persist_ttl() -> int:
    try:
        return int(os.getenv("QUOTA_STATE_TTL_SECONDS", str(6 * 60 * 60)))
    except ValueError:
        return 6 * 60 * 60


def _usage_cache_ttl() -> int:
    try:
        return int(os.getenv("APIFY_USAGE_CACHE_TTL_SECONDS", str(20 * 60)))
    except ValueError:
        return 20 * 60


def _apify_budget() -> float | None:
    """Operator monthly spend ceiling (USD), or None if unset/invalid (O4)."""
    raw = os.getenv("APIFY_MONTHLY_BUDGET_USD", "").strip()
    if not raw:
        return None
    try:
        val = float(raw)
        return val if val > 0 else None
    except ValueError:
        return None


def _evaluate_apify_usage(usage: float, limit: float, purpose: str) -> tuple[bool, str]:
    """Decide availability from a usage reading.

    The operator budget (O4) trips *before* Apify's hard limit — graceful
    degradation instead of slamming into the 402 wall. A trip disables Apify for
    the session and persists it so the next run skips instantly too.
    """
    budget = _apify_budget()
    if budget is not None and usage >= budget:
        reason = f"Apify operator budget reached (${usage:.2f}/${budget:.2f})"
        disable_apify(reason)
        _persist_exhausted(purpose, reason)
        return False, _state["reason"]
    if limit and usage >= limit:
        reason = f"Apify monthly limit reached (${usage:.2f}/${limit:.2f})"
        disable_apify(reason)
        _persist_exhausted(purpose, reason)
        return False, _state["reason"]
    label = f"${usage:.2f}/${limit:.2f} used" if limit else f"${usage:.2f} used"
    if budget is not None:
        label += f", budget ${budget:.2f}"
    return True, f"ON ({label})"


def _sync_persistent(purpose: str) -> None:
    """Seed the in-process breaker from cross-run persisted exhaustion (once).

    A prior run that hit a hard 402/limit recorded it in data/quota_state.json;
    a fresh process picks that up here and skips Apify instantly — no network
    preflight, no failing actor round-trip.
    """
    if _state["synced"] or _state["disabled"]:
        return
    _state["synced"] = True
    try:
        from core.quota_state import is_exhausted

        exhausted, reason = is_exhausted("apify", purpose)
    except Exception:
        return
    if exhausted:
        _state["disabled"] = True
        _state["reason"] = f"{reason} (persisted)"
        logger.info("Apify skipped from persisted state: %s", reason)


def _persist_exhausted(purpose: str, reason: str) -> None:
    """Remember a hard credit/auth failure across runs (TTL'd)."""
    try:
        from core.quota_state import mark_exhausted

        mark_exhausted("apify", purpose, reason, ttl_seconds=_persist_ttl())
    except Exception:
        pass


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
    """Test/CLI helper — clear the in-process circuit breaker."""
    _state.update({"disabled": False, "reason": "", "fails": 0, "checked": False, "synced": False})


def apify_credit_exhausted() -> bool:
    """Back-compat alias: true once the session breaker has tripped (e.g. 402)."""
    return apify_disabled()


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
    _sync_persistent(purpose)
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
        # Account-wide problems → trip the circuit breaker (don't retry this session
        # OR the next run, within the persisted TTL).
        if resp.status_code in (401, 402, 403):
            reason = f"Apify credits/auth ({resp.status_code}) — skipping social signals"
            disable_apify(reason)
            _persist_exhausted(purpose, reason)
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
    _sync_persistent(purpose)
    if _state["disabled"]:
        return False, _state["reason"]
    if _state["checked"]:
        return True, "ON"
    _state["checked"] = True

    api_key = _key(purpose)
    if not api_key:
        disable_apify("no APIFY_CONTENT_MACHINE_KEY set")
        return False, _state["reason"]

    # O3: reuse a recent usage reading instead of re-hitting /users/me on
    # back-to-back runs (the limit/usage barely moves minute to minute).
    try:
        from core.quota_state import get_value, set_value
    except Exception:
        get_value = set_value = None  # type: ignore[assignment]
    if get_value is not None:
        cached = get_value(f"apify_usage:{purpose}")
        if isinstance(cached, dict):
            usage = cached.get("usage")
            limit = cached.get("limit")
            if isinstance(usage, int | float) and isinstance(limit, int | float) and limit > 0:
                # Still enforce the operator budget against the cached reading.
                available, status = _evaluate_apify_usage(float(usage), float(limit), purpose)
                if not available:
                    return available, status
                return True, f"ON (${usage:.2f}/${limit:.2f} used, cached)"

    try:
        resp = requests.get(f"{_BASE}/users/me", params={"token": api_key}, timeout=12)
    except Exception as exc:
        # Network blip — don't disable; let per-actor logic decide.
        logger.debug("Apify preflight network error: %s", exc)
        return True, "ON (precheck skipped)"

    if resp.status_code in (401, 403):
        reason = "Apify key unauthorized (preflight)"
        disable_apify(reason)
        _persist_exhausted(purpose, reason)
        return False, _state["reason"]
    if resp.status_code != 200:
        return True, "ON (precheck inconclusive)"

    try:
        data = resp.json().get("data", {}) or {}
        usage = data.get("monthlyUsageCycleUsdSpent") or data.get("monthlyUsageUsd")
        limit = data.get("monthlyUsageCycleMaxUsd") or (data.get("limits", {}) or {}).get(
            "maxMonthlyUsageUsd"
        )
        if isinstance(usage, int | float):
            limit_val = float(limit) if isinstance(limit, int | float) else 0.0
            available, status = _evaluate_apify_usage(float(usage), limit_val, purpose)
            if available and limit_val > 0 and set_value is not None:
                set_value(
                    f"apify_usage:{purpose}",
                    {"usage": float(usage), "limit": limit_val},
                    _usage_cache_ttl(),
                )
            return available, status
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
        if resp.status_code not in (200, 201):
            return None
        return resp.json() if isinstance(resp.json(), list) else []
    except Exception as exc:
        logger.debug("Apify dataset fetch failed: %s", exc)
        return None
