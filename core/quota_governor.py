"""Unified quota governor — O11 (credit_efficiency.md, Tier 4).

The **single module that talks to the cross-run persistence store**
(`core/quota_state.py` → `data/quota_state.json`) on behalf of every credit
subsystem. Three areas of state live here behind one façade:

- **Signals** (scope `"signal"`) — persistent per-signal breaker records with
  key-hash invalidation. A hard trip (quota/auth/no_key) is remembered across
  runs, and a *changed credential* clears the record immediately instead of
  waiting out the TTL (a fixed key means the failure reason is gone).
- **Apify** (scope `"apify"`) — the global-breaker exhaustion record + the
  cached `/users/me` usage reading, consulted by `apis/apify_client.py`.
- **LLM** (kv `llm_spend:<date>`) — today's cross-run spend, consulted by
  `core/llm_router.py`'s daily-budget downgrade.

Per decisions.md §13 the governor unifies **state + persistence + reporting**,
NOT the distinct check points: the Apify global breaker, the per-signal session
breaker, and the LLM provider breaker remain separate layers — they just read
and write their persisted state through this one module (and `snapshot()` gives
the dashboard a single cross-run view). TTL/reset *policy* stays with each
subsystem (e.g. Apify's reset-window TTL); the governor owns *where and how*
state is stored.

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
        quota_state.clear_value(_keyhash_key(name))
    except Exception as exc:
        # Warning, not debug: the record survives, so a paid signal the operator just
        # fixed stays disabled for up to a billing cycle (CLAUDE.md's expensive case).
        logger.warning("Could not clear persisted disable for signal '%s': %s", name, exc)


def clear_all_signals() -> None:
    """Drop every persisted signal record (reset helper)."""
    try:
        for name in quota_state.list_exhausted(_SCOPE):
            clear_signal(name)
    except Exception as exc:
        # The reset silently did nothing — the operator will assume it worked.
        logger.warning("Could not clear persisted signal disables: %s", exc)


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


# --------------------------------------------------------------------------- #
# Apify scope — global-breaker exhaustion + cached usage reading.
# The check point (the process breaker `_state`) stays in apify_client; only its
# cross-run persistence is routed here. TTL policy stays in apify_client too.
# --------------------------------------------------------------------------- #
_APIFY_SCOPE = "apify"


def _apify_usage_key(purpose: str) -> str:
    return f"apify_usage:{purpose}"


def apify_mark_exhausted(purpose: str, reason: str, ttl_seconds: int) -> None:
    """Persist a hard Apify credit/auth failure across runs (caller sets the TTL)."""
    try:
        quota_state.mark_exhausted(_APIFY_SCOPE, purpose, reason, ttl_seconds=ttl_seconds)
    except Exception as exc:
        logger.debug("apify persistence skipped for '%s': %s", purpose, exc)


def apify_is_exhausted(purpose: str) -> tuple[bool, str]:
    """(exhausted, reason) for a persisted Apify trip; fail-open to not-exhausted."""
    try:
        return quota_state.is_exhausted(_APIFY_SCOPE, purpose)
    except Exception:
        return False, ""


def apify_clear(purpose: str) -> None:
    try:
        quota_state.clear_exhausted(_APIFY_SCOPE, purpose)
    except Exception as exc:
        # Leaves Apify looking exhausted after credits are back — persists to reset day.
        logger.warning("Could not clear persisted Apify exhaustion for '%s': %s", purpose, exc)


def apify_get_usage(purpose: str) -> dict | None:
    """Last cached `/users/me` reading `{usage, limit}` or None if missing/expired."""
    try:
        val = quota_state.get_value(_apify_usage_key(purpose))
    except Exception:
        return None
    return val if isinstance(val, dict) else None


def apify_set_usage(purpose: str, usage: float, limit: float, ttl_seconds: int) -> None:
    try:
        quota_state.set_value(
            _apify_usage_key(purpose), {"usage": usage, "limit": limit}, ttl_seconds
        )
    except Exception as exc:
        logger.debug("apify usage cache skipped for '%s': %s", purpose, exc)


# --------------------------------------------------------------------------- #
# LLM scope — today's cross-run spend (drives the daily-budget downgrade).
# Budget/downgrade policy stays in llm_router; the governor owns the key format
# and the store access so the spend ledger has one home.
# --------------------------------------------------------------------------- #


def llm_today_spend_key() -> str:
    import datetime

    return f"llm_spend:{datetime.date.today().isoformat()}"


def llm_add_spend(cost: float, *, key: str | None = None, ttl_seconds: int = 48 * 3600) -> None:
    if cost <= 0:
        return
    try:
        quota_state.increment_value(key or llm_today_spend_key(), cost, ttl_seconds=ttl_seconds)
    except Exception as exc:
        # The daily-budget downgrade reads this ledger. If the write is lost the guard
        # under-counts spend and quietly stops guarding, so this must be visible.
        logger.warning("LLM spend of $%.4f not persisted (budget guard blind): %s", cost, exc)


def llm_spend_today(key: str | None = None) -> float:
    try:
        return float(quota_state.get_value(key or llm_today_spend_key(), 0.0) or 0.0)
    except Exception:
        return 0.0


def llm_reset_spend(key: str | None = None) -> None:
    try:
        quota_state.set_value(key or llm_today_spend_key(), 0.0, ttl_seconds=1)
    except Exception as exc:
        logger.warning("Could not reset the LLM spend ledger: %s", exc)


# --------------------------------------------------------------------------- #
# LLM dead-model scope — a (provider, model) slug the provider says doesn't exist.
# The session breaker in llm_router already skips it for the rest of the process;
# persisting it stops every NEW run paying the same 404 round-trip. Live runs on
# 2026-08-14 re-probed two retired free slugs on all three runs.
# The check point stays in llm_router (decisions.md §13) — only persistence here.
# --------------------------------------------------------------------------- #
_LLM_MODEL_SCOPE = "llm_model"


def llm_dead_model_ttl() -> int:
    """A retired slug is usually gone for good, but a model can come back, so this
    expires rather than persisting forever — one probe per TTL, not per run."""
    try:
        return int(os.getenv("LLM_DEAD_MODEL_TTL_SECONDS", str(24 * 60 * 60)))
    except ValueError:
        return 24 * 60 * 60


def _llm_model_slug(provider: str, model: str) -> str:
    return f"{provider}/{model}"


def _llm_model_keyhash_key(provider: str, model: str) -> str:
    return f"llm_model_keyhash:{_llm_model_slug(provider, model)}"


def llm_mark_model_dead(
    provider: str, model: str, reason: str, *, fingerprint: str = "", ttl_seconds: int | None = None
) -> None:
    """Persist a dead (provider, model) slug across runs.

    `fingerprint` is supplied by the caller (llm_router owns the provider->env
    mapping) so rotating a key or pointing the tier at a new slug invalidates the
    record instead of pinning a model off forever.
    """
    if not persist_enabled():
        return
    try:
        ttl = ttl_seconds if ttl_seconds is not None else llm_dead_model_ttl()
        quota_state.mark_exhausted(
            _LLM_MODEL_SCOPE, _llm_model_slug(provider, model), reason, ttl_seconds=ttl
        )
        if fingerprint:
            quota_state.set_value(
                _llm_model_keyhash_key(provider, model), fingerprint, ttl_seconds=ttl
            )
    except Exception as exc:
        logger.debug("dead-model persistence skipped for '%s/%s': %s", provider, model, exc)


def persisted_dead_models(fingerprints: dict[str, str] | None = None) -> dict[str, str]:
    """Unexpired dead-model records -> {"provider/model": reason}, key-hash checked.

    `fingerprints` maps "provider/model" -> current fingerprint; a record whose
    stored fingerprint no longer matches is cleared and not returned.
    """
    if not persist_enabled():
        return {}
    try:
        records = quota_state.list_exhausted(_LLM_MODEL_SCOPE)
    except Exception:
        return {}
    out: dict[str, str] = {}
    for slug, reason in records.items():
        stored = quota_state.get_value(f"llm_model_keyhash:{slug}")
        if stored and fingerprints is not None:
            current = fingerprints.get(slug, "")
            if current and current != stored:
                llm_clear_dead_model(slug)
                logger.info("Persisted dead-model '%s' cleared — config/credential changed", slug)
                continue
        out[slug] = reason
    return out


def llm_clear_dead_model(slug: str) -> None:
    try:
        quota_state.clear_exhausted(_LLM_MODEL_SCOPE, slug)
        quota_state.clear_value(f"llm_model_keyhash:{slug}")
    except Exception as exc:
        # A revived model stays skipped until the TTL expires.
        logger.warning("Could not clear persisted dead-model '%s': %s", slug, exc)


def llm_clear_dead_models() -> None:
    """Drop every persisted dead-model record (reset helper)."""
    try:
        for slug in quota_state.list_exhausted(_LLM_MODEL_SCOPE):
            llm_clear_dead_model(slug)
    except Exception as exc:
        logger.warning("Could not clear persisted dead-model records: %s", exc)


# --------------------------------------------------------------------------- #
# ElevenLabs character quota — same shape as APIFY_MONTHLY_BUDGET_USD.
# Check point stays in core/tts.py (decisions §13); only persistence lives here.
# Keyed by calendar month so a new month is a fresh counter; TTL is a safety net.
# --------------------------------------------------------------------------- #


def elevenlabs_chars_key() -> str:
    import datetime

    return f"elevenlabs_chars:{datetime.date.today().strftime('%Y-%m')}"


def elevenlabs_add_chars(
    n: int, *, key: str | None = None, ttl_seconds: int = 40 * 24 * 3600
) -> None:
    if n <= 0:
        return
    try:
        quota_state.increment_value(
            key or elevenlabs_chars_key(), float(n), ttl_seconds=ttl_seconds
        )
    except Exception as exc:
        logger.warning("ElevenLabs %s chars not persisted (quota guard blind): %s", n, exc)


def elevenlabs_chars_used(key: str | None = None) -> int:
    """For the budget *guard*: an unreadable ledger reads 0 so a render is never
    blocked (fail-open). Anything that *reports* the number uses the reading below."""
    try:
        return int(float(quota_state.get_value(key or elevenlabs_chars_key(), 0.0) or 0.0))
    except Exception:
        return 0


def elevenlabs_chars_reading(key: str | None = None) -> int | None:
    """#724: chars used, or None when the ledger exists but cannot be read."""
    try:
        if not quota_state.read_ok():
            return None
        return int(float(quota_state.get_value(key or elevenlabs_chars_key(), 0.0) or 0.0))
    except Exception:
        return None


def elevenlabs_would_exceed(chars: int, budget: int, *, key: str | None = None) -> bool:
    if budget <= 0 or chars <= 0:
        return False
    return elevenlabs_chars_used(key) + chars > budget


def elevenlabs_reset(key: str | None = None) -> None:
    try:
        quota_state.set_value(key or elevenlabs_chars_key(), 0.0, ttl_seconds=1)
    except Exception as exc:
        logger.warning("Could not reset the ElevenLabs character ledger: %s", exc)


# --------------------------------------------------------------------------- #
# YouTube scope (O12) — daily unit consumption, reported through the governor.
#
# `apis/youtube_quota.py` remains the counter and the *check point* (decisions §13:
# the governor unifies state + reporting, never the layered checks). It keeps its own
# per-day file because uploads and the job worker read it outside a run; this scope
# exists so `snapshot()` reports YouTube alongside Apify and LLM instead of the
# dashboard reaching into a second store directly.
# --------------------------------------------------------------------------- #


def youtube_usage() -> dict:
    """Today's YouTube unit usage, fail-open to zeros when the tracker is unreadable."""
    try:
        from apis.youtube_quota import get_usage_summary

        summary = get_usage_summary()
        used = int(summary.get("used") or 0)
        limit = int(summary.get("limit") or 0)
        return {
            "used": used,
            "limit": limit,
            "remaining": int(summary.get("remaining") or 0),
            "pct": round(100.0 * used / limit, 1) if limit else 0.0,
            "day": summary.get("day", ""),
        }
    except Exception:
        return {"used": 0, "limit": 0, "remaining": 0, "pct": 0.0, "day": ""}


# --------------------------------------------------------------------------- #
# Unified cross-run snapshot — one read for the reliability dashboard.
# In-process-only breakers (session signal/LLM) are layered on by the caller.
# --------------------------------------------------------------------------- #
def snapshot(apify_purpose: str = "main") -> dict:
    """Everything the governor persists, in one fail-open read."""
    exhausted, reason = apify_is_exhausted(apify_purpose)
    return {
        "apify": {
            "exhausted": exhausted,
            "reason": reason,
            "usage": apify_get_usage(apify_purpose),
        },
        "llm": {"spend_today": llm_spend_today(), "dead_models": persisted_dead_models()},
        "signals": {"persisted": persisted_disabled_signals()},
        "youtube": youtube_usage(),
        # #724: a report, not a guard -- None when the ledger is unreadable.
        "elevenlabs": {"chars_used": elevenlabs_chars_reading()},
    }
