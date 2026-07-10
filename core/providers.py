"""Shared contract for Pillar 6 provider slots (video / TTS / ingest / grade / music …).

Generalizes the two provider patterns already in the repo — `apis/signal_contract`
(a uniform, never-raise result) and `assets/base.AssetProvider` + the fail-open chain
in `assets/manager` — into one thin contract every new tool seam returns.

Every seam built on this: is **env-gated OFF by default**, **lazy-imports** its heavy
backend (torch / whisperx / audiocraft never import at module load), and **fails open**
to the current behavior — it returns `ProviderResult.fail_open(...)`, never raises. That
keeps CI green with none of the optional extras installed.

Tool → module → env map: [docs/providers_runbook.md](../docs/providers_runbook.md).
Slot design: [docs/video_creation_stack.md](../docs/video_creation_stack.md).
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from core.logging import get_logger

logger = get_logger("core.providers")

# Status vocabulary (scoped analog of apis/signal_contract's status constants).
STATUS_OK = "ok"
STATUS_DISABLED = "disabled"  # env gate off / provider not selected
STATUS_NOT_CONFIGURED = "not_configured"  # selected but backend missing (uninstalled / no server)
STATUS_ERROR = "error"  # backend raised — logged and swallowed
STATUS_FAIL_OPEN = "fail_open"  # chain exhausted; caller falls back to current behavior


@dataclass
class ProviderResult:
    """Uniform result for a provider-slot call. `ok=False` ⇒ caller keeps its old path."""

    slot: str
    provider: str = ""
    ok: bool = False
    data: Any = None
    status: str = STATUS_FAIL_OPEN
    detail: str = ""
    cost_usd: float = 0.0

    @classmethod
    def fail_open(
        cls, slot: str, detail: str = "", *, status: str = STATUS_FAIL_OPEN
    ) -> ProviderResult:
        return cls(slot=slot, ok=False, status=status, detail=detail)

    @classmethod
    def success(
        cls, slot: str, provider: str, data: Any = None, *, cost_usd: float = 0.0, detail: str = ""
    ) -> ProviderResult:
        return cls(
            slot=slot,
            provider=provider,
            ok=True,
            data=data,
            status=STATUS_OK,
            detail=detail,
            cost_usd=cost_usd,
        )


def resolve_order(env_var: str, default: str = "") -> list[str]:
    """Parse a CSV provider-order env var. '' / 'none' / 'off' / '0' ⇒ [] (disabled).

    Mirrors ASSET_PROVIDER_ORDER handling in config/settings.py.
    """
    raw = (os.getenv(env_var, default) or "").strip()
    if not raw or raw.lower() in ("none", "off", "false", "0"):
        return []
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


def selected_provider(env_var: str, default: str = "none") -> str:
    """Single-choice provider gate (e.g. MUSIC_PROVIDER, AI_VIDEO_PROVIDER)."""
    return (os.getenv(env_var, default) or default).strip().lower()


def flag_enabled(env_var: str, default: bool = False) -> bool:
    """Boolean gate (e.g. EXPERT_PANEL_ENABLED, REFRAME_ENABLED)."""
    raw = os.getenv(env_var)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def run_chain(
    slot: str, providers: Iterable[Callable[..., ProviderResult | None]], /, **kwargs: Any
) -> ProviderResult:
    """Try each provider in order; fail-open; never raise.

    `providers` is an iterable of callables `fn(**kwargs) -> ProviderResult | None`.
    Returns the first `ok` result; `ProviderResult.fail_open` when the chain is
    exhausted. Mirrors `assets/manager._find_from_chain`.
    """
    last_detail = ""
    for fn in providers:
        name = getattr(fn, "__name__", "provider")
        try:
            result = fn(**kwargs)
        except Exception as exc:  # a broken provider must never break the caller
            last_detail = f"{name}: {exc}"
            logger.warning("provider slot %s (%s) failed: %s", slot, name, exc)
            continue
        if result is None:
            continue
        if result.ok:
            return result
        if result.detail:
            last_detail = result.detail
    return ProviderResult.fail_open(slot, last_detail)
