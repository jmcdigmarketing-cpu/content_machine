"""Unified quota governor — the O11 seed (credit_efficiency.md, Tier 4).

Stage shipped here: **persistent per-signal breaker records with key-hash
invalidation**. A hard signal trip (quota/auth/no_key) is remembered across
runs in `data/quota_state.json` (scope `"signal"`), so a fresh process skips
the failing round-trip — and a *changed credential* clears the record
immediately instead of waiting out the TTL (a fixed key means the failure
reason is gone).

Per decisions.md §13 the governor unifies **state + persistence + reporting**,
NOT the distinct check points: the Apify global breaker and the per-signal
session breaker remain separate layers that consult this store. Apify and the
LLM router still talk to `core/quota_state.py` directly — migrating them
behind this module is the remaining O11 work.

Everything here is fail-open: any storage error reads as "nothing persisted".
"""

from __future__ import annotations

import hashlib
import os

from core import quota_state
from core.logging import get_logger

logger = get_logger("core.quota_governor")

_SCOPE = "signal"

# Signal name -> env vars whose values constitute its credential. A change in
# any of them invalidates that signal's persisted disable record ("key-hash
# invalidation"). Signals not listed fingerprint as "" and fall back to plain
# TTL expiry — exactly the pre-existing Apify persistence behavior.
_SIGNAL_CREDENTIAL_ENVS: dict[str, tuple[str, ...]] = {
    "reddit": ("APIFY_CONTENT_MACHINE_KEY", "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"),
    "twitter": ("APIFY_CONTENT_MACHINE_KEY",),
    "tiktok_trends": ("APIFY_CONTENT_MACHINE_KEY",),
    "youtube_competitors": ("APIFY_CONTENT_MACHINE_KEY",),
    "youtube": ("YOUTUBE_API_KEY",),
    "finnhub": ("FINNHUB_API_KEY",),
    "fred": ("FRED_API_KEY",),
    "rawg": ("RAWG_API_KEY",),
    "igdb": ("IGDB_CLIENT_ID", "IGDB_CLIENT_SECRET"),
    "twitch": ("TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET"),
    "tmdb": ("TMDB_API_KEY",),
    "lastfm": ("LASTFM_API_KEY",),
    "odds": ("ODDS_API_KEY",),
    "api_sports": ("API_SPORTS_KEY",),
    "news": ("NEWS_API_KEY",),
    "web_search": (
        "BRAVE_API_KEY",
        "BRAVE_SEARCH_API_KEY",
        "TAVILY_API_KEY",
        "SERPAPI_KEY",
    ),
}


def persist_enabled() -> bool:
    return os.getenv("SIGNAL_BREAKER_PERSIST", "true").lower() in ("1", "true", "yes")


def _default_ttl() -> int:
    try:
        return int(os.getenv("QUOTA_STATE_TTL_SECONDS", str(6 * 60 * 60)))
    except ValueError:
        return 6 * 60 * 60


def _fingerprint(name: str) -> str:
    envs = _SIGNAL_CREDENTIAL_ENVS.get(name)
    if not envs:
        return ""
    material = "|".join(os.getenv(e, "").strip() for e in envs)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _keyhash_key(name: str) -> str:
    return f"signal_keyhash:{name}"


def disable_signal(name: str, reason: str, ttl_seconds: int | None = None) -> None:
    """Persist a hard signal trip across runs (no-op when persistence is off)."""
    if not persist_enabled():
        return
    try:
        ttl = ttl_seconds if ttl_seconds is not None else _default_ttl()
        quota_state.mark_exhausted(_SCOPE, name, reason, ttl_seconds=ttl)
        fp = _fingerprint(name)
        if fp:
            quota_state.set_value(_keyhash_key(name), fp, ttl_seconds=ttl)
    except Exception as exc:
        logger.debug("signal persistence skipped for '%s': %s", name, exc)


def clear_signal(name: str) -> None:
    """Drop one persisted signal record (operator fixed the underlying issue)."""
    try:
        quota_state.clear_exhausted(_SCOPE, name)
    except Exception:
        pass


def clear_all_signals() -> None:
    """Drop every persisted signal record (reset helper)."""
    try:
        for name in quota_state.list_exhausted(_SCOPE):
            quota_state.clear_exhausted(_SCOPE, name)
    except Exception:
        pass


def persisted_disabled_signals() -> dict[str, str]:
    """Unexpired persisted signal trips -> {name: reason}, after key-hash checks.

    A record whose stored credential fingerprint no longer matches the current
    env (key fixed/rotated) is cleared here and not returned.
    """
    if not persist_enabled():
        return {}
    try:
        records = quota_state.list_exhausted(_SCOPE)
    except Exception:
        return {}
    out: dict[str, str] = {}
    for name, reason in records.items():
        stored = quota_state.get_value(_keyhash_key(name))
        if stored:
            current = _fingerprint(name)
            if current and current != stored:
                clear_signal(name)
                logger.info("Persisted disable for signal '%s' cleared — credential changed", name)
                continue
        out[name] = reason
    return out
