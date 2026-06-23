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

import json
import os
import re
import threading
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


def resolve_tier(tier: str) -> tuple[str, str]:
    """Return (provider, model) for a task tier.

    Honors ``LLM_<TIER>_PROVIDER`` / ``LLM_<TIER>_MODEL`` overrides, else walks
    the free-first preference chain and returns the first available provider.
    Falls back to OpenAI's tier default so behavior never hard-fails when at
    least one key exists; raises only if nothing is configured at all.
    """
    if tier not in _VALID_TIERS:
        tier = "cheap"

    forced = os.getenv(f"LLM_{tier.upper()}_PROVIDER", "").strip().lower()
    forced_model = os.getenv(f"LLM_{tier.upper()}_MODEL", "").strip()
    if forced and forced in _PROVIDERS:
        model = forced_model or _default_model(forced, tier)
        return forced, model

    for provider in _TIER_PREFERENCE[tier]:
        if _provider_available(provider, tier):
            model = forced_model or _default_model(provider, tier)
            if model:
                return provider, model

    # Nothing in the chain is available; last resort is OpenAI's default so the
    # error surfaced downstream is a clear auth error, not a routing crash.
    return "openai", _default_model("openai", tier)


# --- Usage ledger ------------------------------------------------------------
@dataclass
class _Usage:
    calls: list[dict[str, Any]] = field(default_factory=list)


_usage = _Usage()
_usage_lock = threading.Lock()


def reset_usage() -> None:
    """Clear the per-run token ledger. Call at the start of each run."""
    with _usage_lock:
        _usage.calls.clear()


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
    """Run a completion through the routed provider for ``tier``.

    ``messages`` may be a plain prompt string or a list of role/content dicts.
    Pass ``provider``/``model`` to bypass tier routing. Returns the raw text
    (use ``complete_json`` when you want a parsed dict). Records token usage in
    the ledger. Raises on transport/auth errors (callers decide how to degrade).
    """
    if provider and not model:
        model = _default_model(provider, tier if tier in _VALID_TIERS else "cheap")
    if not (provider and model):
        provider, model = resolve_tier(tier)

    msgs = _normalize_messages(messages, system)
    kind = _PROVIDERS.get(provider, {}).get("kind", "openai")
    if kind == "anthropic":
        text, in_tok, out_tok = _anthropic_complete(
            model, msgs, temperature=temperature, max_tokens=max_tokens
        )
    else:
        text, in_tok, out_tok = _openai_complete(
            provider,
            model,
            msgs,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )
    _record_usage(provider, model, tier, in_tok, out_tok)
    return text


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
