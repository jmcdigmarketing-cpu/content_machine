"""Unified multi-provider LLM router with task-tier routing.

Why this exists
---------------
Before this module, every LLM call went straight to a hardcoded OpenAI client
(`core/llm_client.get_openai_client`) and Claude was bolted on as duplicated raw
`requests.post` calls in three places. There was no way to (a) route cheap tasks
to cheap models, (b) add new providers without touching every call site, or
(c) measure real per-provider token spend.

This router fixes all three. Every LLM call in the app should go through
``complete`` / ``complete_json`` here.

Task tiers (minimal cost / maximal value)
-----------------------------------------
- ``cheap``   — domain inference, tagging, summaries, query rewriting, hook
                regen. Quality barely matters; route to the cheapest model.
- ``extract`` — grounded fact extraction (low-temp, JSON). Needs solid
                reasoning/JSON; route to a strong-but-cheap model.
- ``premium`` — final script + research brief (the product). Best available
                model; free-first by default, one env flip to upgrade to
                gpt-4o / Claude.

Providers
---------
DeepSeek, OpenRouter, Groq, Ollama, Doubao (Volcengine Ark) and OpenAI are all
OpenAI-API-compatible, so they share one client shape (different ``base_url`` +
key + model). Anthropic uses its native messages API.

Recommended free setup (no region-locked providers): DeepSeek for extract +
premium, OpenRouter (free ``:free`` models) for the cheap tier, optionally Ollama
for fully local drafts. Groq is wired but not a default (console signup is gated
for some accounts). Doubao stays wired but deprioritized — it's
China-region-locked (VPN + Chinese payment/ID) and saves ~zero over DeepSeek.

Tier resolution
---------------
Each tier reads ``LLM_<TIER>_PROVIDER`` / ``LLM_<TIER>_MODEL`` from the env. When
unset, a free-first preference chain picks the first *available* provider (key
present, and for Doubao/Ollama a model id configured). This means the router
degrades gracefully: if only ``OPENAI_API_KEY`` is set it behaves like the old
code; add ``DEEPSEEK_API_KEY`` + ``OPENROUTER_API_KEY`` and the tiers silently
move to the free providers.

Usage ledger
------------
Token usage from every call is accumulated in a process-global ledger so
``core.cost_meter`` can price real spend per provider/model instead of guessing.
Call ``reset_usage()`` at the start of a run; read it back with ``get_usage()``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import requests

# Importing settings ensures the project .env is loaded into os.environ before
# any tier resolution reads provider keys — even if the router is imported
# standalone (e.g. a one-off script) without the rest of the app.
import config.settings  # noqa: F401
from core.logging import get_logger

logger = get_logger(__name__)

# --- Provider registry -------------------------------------------------------
# kind="openai" providers all use the openai SDK with a custom base_url.
# kind="anthropic" uses the native messages API.
_PROVIDERS: dict[str, dict[str, str]] = {
    "openai": {"kind": "openai", "key_env": "OPENAI_API_KEY", "base_url": ""},
    "deepseek": {
        "kind": "openai",
        "key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com",
    },
    "openrouter": {
        "kind": "openai",
        # OpenRouter — one key, many models incl. free (`:free`) variants.
        "key_env": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
    },
    "groq": {
        "kind": "openai",
        # Groq's OpenAI-compatible endpoint (free, fastest) — kept wired, but not
        # a default: console signup is gated for some accounts.
        "key_env": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
    },
    "ollama": {
        "kind": "openai",
        # Local Ollama OpenAI-compatible server. No real key needed; available
        # only once OLLAMA_MODEL is set. Base URL overridable for remote hosts.
        "key_env": "OLLAMA_API_KEY",
        "base_url": "",  # resolved at call time (OLLAMA_BASE_URL or localhost)
    },
    "doubao": {
        "kind": "openai",
        # Volcengine Ark is OpenAI-compatible. Accepts ARK_API_KEY as an alias.
        # Region-locked (China) — kept for completeness, not a default.
        "key_env": "DOUBAO_API_KEY",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
    },
    "anthropic": {"kind": "anthropic", "key_env": "ANTHROPIC_API_KEY", "base_url": ""},
}

# Providers whose model id is account/host-specific and has no universal default:
# unavailable until a model id is configured via env.
_MODEL_REQUIRED = ("doubao", "ollama")

# Free-first preference chains per tier. First *available* provider wins.
# OpenRouter (free `:free` models) anchors the throwaway cheap tier, with local
# Ollama as the next free fallback; DeepSeek-V3 anchors extract + premium
# (near-gpt-4o quality, ~10x cheaper). Groq stays low (signup gated for some);
# Doubao is deprioritized (region-locked).
_TIER_PREFERENCE: dict[str, tuple[str, ...]] = {
    "cheap": ("openrouter", "ollama", "groq", "deepseek", "doubao", "openai"),
    "extract": ("deepseek", "openrouter", "groq", "ollama", "doubao", "openai", "anthropic"),
    "premium": ("deepseek", "openrouter", "openai", "anthropic", "groq", "ollama"),
}

# Per-provider default model for each tier. Model-required providers (Doubao,
# Ollama) have no universal default and must be set via env.
_DEFAULT_MODELS: dict[str, dict[str, str]] = {
    "openai": {"cheap": "gpt-4o-mini", "extract": "gpt-4o-mini", "premium": "gpt-4o"},
    "deepseek": {
        "cheap": "deepseek-chat",
        "extract": "deepseek-chat",
        "premium": "deepseek-chat",
    },
    "openrouter": {
        # Free (`:free`) models by default; override with OPENROUTER_MODEL.
        # Free models are rate-limited — fine for this volume.
        "cheap": "meta-llama/llama-3.3-70b-instruct:free",
        "extract": "deepseek/deepseek-chat",
        "premium": "deepseek/deepseek-chat",
    },
    "groq": {
        # 8b-instant for throwaway speed; 70b for anything needing more nuance.
        "cheap": "llama-3.1-8b-instant",
        "extract": "llama-3.3-70b-versatile",
        "premium": "llama-3.3-70b-versatile",
    },
    "ollama": {"cheap": "", "extract": "", "premium": ""},
    "doubao": {"cheap": "", "extract": "", "premium": ""},
    "anthropic": {
        "cheap": "claude-haiku-4-5-20251001",
        "extract": "claude-haiku-4-5-20251001",
        "premium": "claude-sonnet-4-20250514",
    },
}

_VALID_TIERS = frozenset(_TIER_PREFERENCE)


def _provider_key(provider: str) -> str:
    spec = _PROVIDERS.get(provider)
    if not spec:
        return ""
    key = os.getenv(spec["key_env"], "").strip()
    if not key and provider == "doubao":
        key = os.getenv("ARK_API_KEY", "").strip()
    # Ollama runs locally and needs no real key; the openai SDK just wants a
    # non-empty string, so default to a placeholder.
    if not key and provider == "ollama":
        key = "ollama"
    return key


# Providers whose bare `{PROVIDER}_MODEL` env var already means something else
# (legacy single-model config) — for these, only the per-tier form is honored as
# an override so we don't accidentally pin every tier to that one model.
_LEGACY_BARE_MODEL_ENV = ("openai", "anthropic")


def _model_override(provider: str, tier: str) -> str:
    """Env model override: `{PROVIDER}_MODEL_<TIER>` then bare `{PROVIDER}_MODEL`.

    The bare form is skipped for providers in `_LEGACY_BARE_MODEL_ENV` to avoid
    colliding with their pre-existing single-model env vars.
    """
    prefix = provider.upper()
    per_tier = os.getenv(f"{prefix}_MODEL_{tier.upper()}", "").strip()
    if per_tier:
        return per_tier
    if provider not in _LEGACY_BARE_MODEL_ENV:
        return os.getenv(f"{prefix}_MODEL", "").strip()
    return ""


def _default_model(provider: str, tier: str) -> str:
    override = _model_override(provider, tier)
    if override:
        return override
    return _DEFAULT_MODELS.get(provider, {}).get(tier, "")


def _provider_available(provider: str, tier: str) -> bool:
    if not _provider_key(provider):
        return False
    # Model-required providers (Doubao, Ollama) need a model id configured.
    return not (provider in _MODEL_REQUIRED and not _model_override(provider, tier))


# --- LLM session breaker (O6) -----------------------------------------------
# Once a provider returns a hard auth/quota status, skip it for the rest of the
# process so tier resolution + failover route around it (mirrors the signal
# breaker). Free providers' rate-limits are transient, so 429/5xx do NOT disable
# — they just trigger failover to the next provider (O5).
_llm_disabled_state: dict[str, str] = {}
_llm_breaker_lock = threading.Lock()


def _llm_disabled(provider: str) -> bool:
    with _llm_breaker_lock:
        return provider in _llm_disabled_state


def _disable_llm(provider: str, reason: str) -> None:
    with _llm_breaker_lock:
        if provider not in _llm_disabled_state:
            logger.warning("LLM provider '%s' disabled this session: %s", provider, reason)
        _llm_disabled_state[provider] = reason


# A specific (provider, model) slug that the provider says doesn't exist / isn't
# available on this account (e.g. a retired OpenRouter `:free` variant). Unlike the
# provider breaker above this is *per model*: OpenRouter's other models and tiers keep
# working. Skipping it for the session avoids a wasted 404 round-trip on every later call.
_dead_models: set[tuple[str, str]] = set()
_dead_models_loaded = False


def _dead_model_ttl_hours() -> float:
    try:
        from core.quota_governor import llm_dead_model_ttl

        return llm_dead_model_ttl() / 3600.0
    except Exception:
        return 24.0


def _model_fingerprint(provider: str, model: str) -> str:
    """Credential + configured-slug fingerprint, so rotating a key or pointing the
    tier at a different model re-probes instead of staying pinned off."""
    material = f"{_provider_key(provider)}|{model}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _load_persisted_dead_models() -> None:
    """Seed the session set from the cross-run store (O11 governor), once."""
    global _dead_models_loaded
    if _dead_models_loaded:
        return
    _dead_models_loaded = True
    try:
        from core.quota_governor import persisted_dead_models

        # Pass 1 (no fingerprints) just lists the stored slugs; pass 2 re-checks them
        # against what the CURRENT config resolves to, so a rotated key or a retargeted
        # tier clears the record instead of pinning a live model off.
        fps = {
            slug: _model_fingerprint(*slug.split("/", 1))
            for slug in persisted_dead_models()
            if "/" in slug
        }
        for slug in persisted_dead_models(fps):
            prov, _, mdl = slug.partition("/")
            if prov and mdl:
                _dead_models.add((prov, mdl))
    except Exception as exc:
        logger.debug("dead-model load skipped: %s", exc)


def _model_is_dead(provider: str, model: str) -> bool:
    with _llm_breaker_lock:
        if not _dead_models_loaded:
            _load_persisted_dead_models()
        return (provider, model) in _dead_models


def _mark_model_dead(provider: str, model: str, reason: str, tier: str = "") -> None:
    with _llm_breaker_lock:
        if (provider, model) in _dead_models:
            return
        _dead_models.add((provider, model))
    try:
        from core.quota_governor import llm_mark_model_dead

        llm_mark_model_dead(
            provider, model, reason, fingerprint=_model_fingerprint(provider, model)
        )
    except Exception as exc:
        logger.debug("dead-model persistence skipped: %s", exc)
    override = f"{provider.upper()}_MODEL_{tier.upper()}" if tier else f"{provider.upper()}_MODEL"
    logger.warning(
        "LLM model '%s/%s' unavailable (%s) — skipping it for %.0fh (persisted across "
        "runs). If this is a retired free slug, set %s to a live one; changing it "
        "clears the record.",
        provider,
        model,
        reason,
        _dead_model_ttl_hours(),
        override,
    )


def reset_llm_breaker(*, persisted: bool = True) -> None:
    """Test/CLI helper — re-enable all LLM providers and dead models.

    Clears the cross-run dead-model store too: a session-only reset would look like
    a no-op on the next call, since the persisted records reload immediately.
    """
    global _dead_models_loaded
    with _llm_breaker_lock:
        _llm_disabled_state.clear()
        _dead_models.clear()
        _dead_models_loaded = not persisted
    if persisted:
        try:
            from core.quota_governor import llm_clear_dead_models

            llm_clear_dead_models()
        except Exception:
            pass


def disabled_providers() -> dict[str, str]:
    """Providers disabled this session (provider -> reason). For the dashboard."""
    with _llm_breaker_lock:
        return dict(_llm_disabled_state)


def _free_mode_strict() -> bool:
    """Free-mode never-pay guard (set by core.run_mode.apply_cost_mode)."""
    return os.getenv("FREE_MODE_STRICT", "").strip().lower() in ("1", "true", "yes")


def _is_free_llm(provider: str, model: str) -> bool:
    """True for a zero-cost candidate: local Ollama, or an OpenRouter `:free` model."""
    if provider == "ollama":
        return True
    return provider == "openrouter" and model.strip().lower().endswith(":free")


def _resolve_chain(tier: str) -> list[tuple[str, str]]:
    """Ordered ``(provider, model)`` candidates for a tier — for failover.

    Forced ``LLM_<TIER>_PROVIDER`` goes first, then the free-first preference
    chain; session-disabled providers are dropped. Falls back to OpenAI's tier
    default so a hard error downstream is a clear auth error, not a routing crash.

    Free mode (``FREE_MODE_STRICT``) filters the chain to zero-cost candidates
    only and raises if none remain — a paid provider is never returned.
    """
    if tier not in _VALID_TIERS:
        tier = "cheap"
    forced = os.getenv(f"LLM_{tier.upper()}_PROVIDER", "").strip().lower()
    forced_model = os.getenv(f"LLM_{tier.upper()}_MODEL", "").strip()

    order: list[str] = []
    if forced and forced in _PROVIDERS:
        order.append(forced)
    for provider in _TIER_PREFERENCE[tier]:
        if provider not in order:
            order.append(provider)

    chain: list[tuple[str, str]] = []
    for provider in order:
        if _llm_disabled(provider):
            continue
        is_forced = provider == forced
        if not is_forced and not _provider_available(provider, tier):
            continue
        # LLM_<TIER>_MODEL pins the model only for the forced provider; failover
        # candidates use their own default (a forced model id won't be valid on a
        # different provider).
        model = (forced_model if is_forced else "") or _default_model(provider, tier)
        if model:
            chain.append((provider, model))

    if _free_mode_strict():
        chain = [(p, m) for (p, m) in chain if _is_free_llm(p, m)]
        if not chain:
            raise RuntimeError(
                "Free mode ($0, strict): no zero-cost LLM provider available. Set "
                "OPENROUTER_API_KEY (free :free models) or configure Ollama "
                "(OLLAMA_MODEL). See docs/free_mode.md."
            )
        return chain

    if not chain:
        return [("openai", _default_model("openai", tier))]
    return chain


def resolve_tier(tier: str) -> tuple[str, str]:
    """Return the primary ``(provider, model)`` for a task tier.

    Honors ``LLM_<TIER>_PROVIDER`` / ``LLM_<TIER>_MODEL`` overrides, else walks
    the free-first preference chain and returns the first available provider
    (skipping any disabled by the session breaker). See ``_resolve_chain`` for
    the full failover ordering.
    """
    return _resolve_chain(tier)[0]


# Error classes that warrant trying the next provider; a subset disables the
# failing provider for the session.
# "model_unavailable" fails over like the rest, but is deliberately NOT in _DISABLE_LLM
# (that would disable the whole provider — its other models/tiers are fine) nor in
# _SAME_PROVIDER_RETRY (a retired slug won't come back in a few seconds). It's handled
# per-model by _mark_model_dead instead.
_RETRYABLE_LLM = frozenset({"rate_limit", "quota", "auth", "server", "model_unavailable"})
_DISABLE_LLM = frozenset({"quota", "auth"})
# Only these transient classes are worth retrying on the SAME provider (auth/quota
# won't recover on a retry). Used when the chain has no fallback left — e.g. strict
# Free mode pins a single free provider and free tiers rate-limit briefly.
_SAME_PROVIDER_RETRY = frozenset({"rate_limit", "server"})
_LLM_RETRY_BACKOFFS = (1.5, 4.0)  # seconds before retry 1, retry 2 (bounded, ~5.5s total)


class LLMUnavailableError(RuntimeError):
    """Every candidate provider for a tier failed (e.g. the free tier is rate-limited
    and no paid fallback is configured in Free mode). Callers catch this to degrade
    gracefully instead of surfacing a raw provider traceback."""


def _classify_llm_error(exc: Exception) -> str:
    """Map a provider exception to a coarse class for failover decisions."""
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    if status == 429:
        return "rate_limit"
    if status == 402:
        return "quota"
    if status in (401, 403):
        return "auth"
    # 404 = this model doesn't exist / isn't available on this account (e.g. a retired
    # OpenRouter `:free` slug). A *provider* problem, not a bad request — fail over.
    if status == 404:
        return "model_unavailable"
    # Some providers report an unknown model as 400 rather than 404.
    if status == 400 and _looks_like_model_error(exc):
        return "model_unavailable"
    if isinstance(status, int) and 500 <= status < 600:
        return "server"
    name = type(exc).__name__.lower()
    if "timeout" in name or "connection" in name:
        return "server"
    return "other"


def _looks_like_model_error(exc: Exception) -> bool:
    """True when an error message points at the model slug rather than the request."""
    text = str(exc).lower()
    return "model" in text and any(
        phrase in text for phrase in ("not found", "unavailable", "invalid", "does not exist")
    )


# --- Usage ledger ------------------------------------------------------------
@dataclass
class _Usage:
    calls: list[dict[str, Any]] = field(default_factory=list)


_usage = _Usage()
_usage_lock = threading.Lock()


def reset_usage() -> None:
    """Clear the per-run token ledger. Call at the start of each run."""
    global _budget_warned
    with _usage_lock:
        _usage.calls.clear()
    with _spend_lock:
        _budget_warned = False


def get_usage() -> list[dict[str, Any]]:
    """Return a copy of recorded LLM calls: provider, model, in/out tokens, tier."""
    with _usage_lock:
        return [dict(c) for c in _usage.calls]


def _record_usage(provider: str, model: str, tier: str, in_tok: int, out_tok: int) -> None:
    with _usage_lock:
        _usage.calls.append(
            {
                "provider": provider,
                "model": model,
                "tier": tier,
                "input_tokens": int(in_tok or 0),
                "output_tokens": int(out_tok or 0),
            }
        )


# --- Daily spend ceiling (O7) ------------------------------------------------
# When today's *cross-run* LLM spend exceeds LLM_DAILY_BUDGET_USD, non-cheap tiers
# are downgraded to the free-first cheap chain (premium → cheap) so a runaway day
# can't keep billing paid models. Spend is only tracked when a budget is set
# (otherwise we skip the per-call pricing + file write entirely).
_spend_lock = threading.Lock()
_budget_warned = False


def _llm_daily_budget() -> float | None:
    raw = os.getenv("LLM_DAILY_BUDGET_USD", "").strip()
    if not raw:
        return None
    try:
        val = float(raw)
        return val if val > 0 else None
    except ValueError:
        return None


def _today_spend_key() -> str:
    # Thin alias — the governor owns the key format (core/quota_governor.py, O11).
    from core.quota_governor import llm_today_spend_key

    return llm_today_spend_key()


def _price_call(provider: str, model: str, in_tok: int, out_tok: int) -> float:
    try:
        from core.cost_meter import llm_cost_from_usage

        return llm_cost_from_usage(
            [
                {
                    "provider": provider,
                    "model": model,
                    "input_tokens": in_tok,
                    "output_tokens": out_tok,
                }
            ]
        )
    except Exception:
        return 0.0


def _add_llm_spend(cost: float) -> None:
    """Accumulate today's cross-run LLM spend (only when a budget is configured)."""
    if cost <= 0 or _llm_daily_budget() is None:
        return
    try:
        from core.quota_governor import llm_add_spend

        llm_add_spend(cost)
    except Exception:
        pass


def _over_llm_budget() -> bool:
    budget = _llm_daily_budget()
    if budget is None:
        return False
    try:
        from core.quota_governor import llm_spend_today

        return llm_spend_today() >= budget
    except Exception:
        return False


def reset_llm_spend() -> None:
    """Test/CLI helper — clear today's recorded LLM spend."""
    global _budget_warned
    _budget_warned = False
    try:
        from core.quota_governor import llm_reset_spend

        llm_reset_spend()
    except Exception:
        pass


# --- OpenAI-compatible client cache -----------------------------------------
_clients: dict[str, Any] = {}


def _openai_client(provider: str):
    if provider in _clients:
        return _clients[provider]
    from openai import OpenAI

    spec = _PROVIDERS[provider]
    kwargs: dict[str, Any] = {"api_key": _provider_key(provider)}
    base_url = spec["base_url"]
    if provider == "ollama":
        # Local Ollama server (override host for a remote box via OLLAMA_BASE_URL).
        base_url = os.getenv("OLLAMA_BASE_URL", "").strip() or "http://localhost:11434/v1"
    if base_url:
        kwargs["base_url"] = base_url
    if provider == "openrouter":
        # Optional ranking headers OpenRouter recommends (harmless if unset).
        site = os.getenv("OPENROUTER_SITE_URL", "").strip()
        app = os.getenv("OPENROUTER_APP_NAME", "Content Machine").strip()
        headers = {"X-Title": app}
        if site:
            headers["HTTP-Referer"] = site
        kwargs["default_headers"] = headers
    client = OpenAI(**kwargs)
    _clients[provider] = client
    return client


def _openai_complete(
    provider: str,
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> tuple[str, int, int]:
    client = _openai_client(provider)
    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "messages": messages,
    }
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    text = resp.choices[0].message.content or ""
    usage = getattr(resp, "usage", None)
    in_tok = getattr(usage, "prompt_tokens", 0) if usage else 0
    out_tok = getattr(usage, "completion_tokens", 0) if usage else 0
    return text, in_tok, out_tok


def _anthropic_complete(
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float,
    max_tokens: int,
) -> tuple[str, int, int]:
    key = _provider_key("anthropic")
    # Anthropic wants a top-level system param, not a system role message.
    system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system")
    convo = [m for m in messages if m.get("role") != "system"]
    body: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens or 1024,
        "temperature": temperature,
        "messages": convo or [{"role": "user", "content": " "}],
    }
    if system:
        body["system"] = system
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=body,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    blocks = data.get("content") or []
    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    usage = data.get("usage") or {}
    return text, int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))


def _normalize_messages(
    messages: list[dict[str, str]] | str, system: str | None
) -> list[dict[str, str]]:
    out = [{"role": "user", "content": messages}] if isinstance(messages, str) else list(messages)
    if system:
        out = [{"role": "system", "content": system}, *out]
    return out


def complete(
    messages: list[dict[str, str]] | str,
    *,
    tier: str = "cheap",
    system: str | None = None,
    temperature: float = 0.65,
    max_tokens: int = 1024,
    json_mode: bool = False,
    provider: str | None = None,
    model: str | None = None,
) -> str:
    """Run a completion through the routed provider for ``tier``, with failover.

    ``messages`` may be a plain prompt string or a list of role/content dicts.
    When ``provider``/``model`` are omitted the tier resolves to a *chain* of
    providers (O5): on a rate-limit/quota/auth/5xx error the next provider in the
    chain is tried, and hard auth/quota failures disable that provider for the
    session (O6). Pass an explicit ``provider`` to pin one (no failover). When
    today's spend exceeds ``LLM_DAILY_BUDGET_USD`` a non-cheap tier is downgraded
    to the free-first cheap chain (O7). Returns the raw text; records token usage.
    Raises only when every candidate fails.
    """
    msgs = _normalize_messages(messages, system)

    if provider:
        if not model:
            model = _default_model(provider, tier if tier in _VALID_TIERS else "cheap")
        candidates = [(provider, model)]
    else:
        # O7: over the daily budget → downgrade premium/extract to the cheap chain.
        if tier != "cheap" and _over_llm_budget():
            with _spend_lock:
                global _budget_warned
                if not _budget_warned:
                    logger.warning(
                        "LLM daily budget exceeded — downgrading '%s' tier to 'cheap'", tier
                    )
                    _budget_warned = True
            tier = "cheap"
        candidates = _resolve_chain(tier)

    # Skip slugs already proven unavailable this session (e.g. a retired `:free` model) so
    # we don't repeat the same 404 on every call. If that would empty the chain, keep the
    # original list so the failure path still surfaces the provider's real error.
    if provider is None:
        live = [c for c in candidates if not _model_is_dead(*c)]
        if live:
            candidates = live

    last_exc: Exception | None = None
    for idx, (prov, mdl) in enumerate(candidates):
        is_last = idx >= len(candidates) - 1
        attempt = 0
        while True:
            try:
                kind = _PROVIDERS.get(prov, {}).get("kind", "openai")
                if kind == "anthropic":
                    text, in_tok, out_tok = _anthropic_complete(
                        mdl, msgs, temperature=temperature, max_tokens=max_tokens
                    )
                else:
                    text, in_tok, out_tok = _openai_complete(
                        prov,
                        mdl,
                        msgs,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        json_mode=json_mode,
                    )
                _record_usage(prov, mdl, tier, in_tok, out_tok)
                if _llm_daily_budget() is not None:
                    _add_llm_spend(_price_call(prov, mdl, in_tok, out_tok))
                return text
            except Exception as exc:
                last_exc = exc
                err_class = _classify_llm_error(exc)
                if err_class in _DISABLE_LLM:
                    _disable_llm(prov, f"{err_class} ({type(exc).__name__})")
                if err_class == "model_unavailable":
                    _mark_model_dead(prov, mdl, type(exc).__name__, tier)
                if provider is not None:
                    raise  # explicitly pinned provider: no failover, no retry, raw error
                if err_class in _RETRYABLE_LLM:
                    if not is_last:
                        logger.info(
                            "LLM provider '%s' failed (%s) — failing over to next",
                            prov,
                            err_class,
                        )
                        break  # a different provider is cheaper than waiting
                    # No fallback left: retry the sole provider briefly on a transient
                    # error (free tiers rate-limit for seconds), then give up gracefully.
                    if err_class in _SAME_PROVIDER_RETRY and attempt < len(_LLM_RETRY_BACKOFFS):
                        wait = _LLM_RETRY_BACKOFFS[attempt]
                        logger.info(
                            "LLM '%s' transient error (%s), no fallback — retry %d in %.1fs",
                            prov,
                            err_class,
                            attempt + 1,
                            wait,
                        )
                        time.sleep(wait)
                        attempt += 1
                        continue
                    raise LLMUnavailableError(
                        f"all LLM providers failed for tier '{tier}': {exc}"
                    ) from exc
                raise  # non-retryable, unexpected error — surface as-is
    if last_exc:
        raise LLMUnavailableError(
            f"all LLM providers failed for tier '{tier}': {last_exc}"
        ) from last_exc
    raise RuntimeError("no LLM provider available for this tier")


def parse_json_payload(raw: str) -> dict[str, Any] | None:
    """Best-effort JSON parse: whole string, then the first {...} block."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return None
    return None


def complete_json(
    messages: list[dict[str, str]] | str,
    *,
    tier: str = "cheap",
    system: str | None = None,
    temperature: float = 0.5,
    max_tokens: int = 1024,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any] | None:
    """``complete`` with ``json_mode`` on, parsed into a dict (or None)."""
    raw = complete(
        messages,
        tier=tier,
        system=system,
        temperature=temperature,
        max_tokens=max_tokens,
        json_mode=True,
        provider=provider,
        model=model,
    )
    return parse_json_payload(raw)
