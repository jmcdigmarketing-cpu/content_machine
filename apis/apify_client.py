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
        if resp.status_code == 402:
            logger.warning("Apify: out of credits for actor %s", actor_id)
            return None
        # run-sync-get-dataset-items returns 201 (Created) with the dataset items,
        # not 200 — accept both. The dataset payload may itself carry an error object,
        # which is handled by the caller's data-shape checks.
        if resp.status_code not in (200, 201):
            logger.warning(
                "Apify actor %s returned %s: %s", actor_id, resp.status_code, resp.text[:200]
            )
            return None
        items = resp.json() if isinstance(resp.json(), list) else []
        set_cache(cache_key, items, ttl=ttl)
        return items
    except requests.Timeout:
        logger.warning("Apify actor %s timed out after %ss", actor_id, timeout_secs)
        return None
    except Exception as exc:
        logger.warning("Apify actor %s failed: %s", actor_id, exc)
        return None


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
