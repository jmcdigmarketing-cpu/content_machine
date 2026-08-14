"""Reliability / quota dashboard (O9) — one view of the credit-efficiency layer.

Gathers the state the waves 1–2 machinery enforces but didn't surface: Apify
breaker + budget, LLM provider breaker + daily spend, cache hit-rate, and YouTube
units. Read-only and fail-open — a missing subsystem shows as "n/a", never raises.

    py -m scripts.ops reliability     (or: py -m core.reliability)

Most state is read from the persisted stores (data/quota_state.json,
data/cache_stats.json, data/youtube_quota.json), so the dashboard is meaningful
even in a fresh process. In-process-only breakers (signal/LLM session) will be
empty unless run inside the same process as a discovery.
"""

from __future__ import annotations

import os
from typing import Any


def _f(env: str) -> float | None:
    raw = os.getenv(env, "").strip()
    if not raw:
        return None
    try:
        val = float(raw)
        return val if val > 0 else None
    except ValueError:
        return None


def _apify_section() -> dict[str, Any]:
    out: dict[str, Any] = {"budget": _f("APIFY_MONTHLY_BUDGET_USD")}
    try:
        from apis.apify_client import apify_disabled, apify_status

        out["status"] = apify_status()
        out["disabled"] = apify_disabled()
    except Exception:
        out["status"] = "n/a"
    try:
        from core.quota_governor import apify_get_usage, apify_is_exhausted

        exhausted, reason = apify_is_exhausted("main")
        out["persisted_exhausted"] = exhausted
        out["persisted_reason"] = reason
        out["usage_cache"] = apify_get_usage("main")
    except Exception:
        pass
    try:
        from core.reset_window import next_reset, reset_window_enabled

        if reset_window_enabled():
            nxt = next_reset("apify")
            out["next_reset"] = nxt.isoformat() if nxt else None
    except Exception:
        pass
    return out


def _llm_section() -> dict[str, Any]:
    out: dict[str, Any] = {"daily_budget": _f("LLM_DAILY_BUDGET_USD")}
    try:
        from core.llm_router import disabled_providers

        out["disabled_providers"] = disabled_providers()
        from core.quota_governor import llm_spend_today, persisted_dead_models

        out["spend_today"] = llm_spend_today()
        out["dead_models"] = dict(sorted(persisted_dead_models().items()))
    except Exception:
        out["disabled_providers"] = {}
    return out


def _signals_section() -> dict[str, Any]:
    out: dict[str, Any] = {"disabled": [], "cooldowns": {}, "persisted": {}}
    try:
        from core.quota_governor import persisted_disabled_signals

        out["persisted"] = dict(sorted(persisted_disabled_signals().items()))
    except Exception:
        pass
    try:
        from apis.register_signals import disabled_signals, signal_cooldowns

        cooldowns = signal_cooldowns()
        out["disabled"] = sorted(disabled_signals() - set(cooldowns) - set(out["persisted"]))
        out["cooldowns"] = dict(sorted(cooldowns.items()))
    except Exception:
        pass
    return out


def _cache_section() -> dict[str, Any]:
    try:
        from apis.cache_manager import get_cache_stats

        return get_cache_stats()
    except Exception:
        return {"total": 0, "hit_rate": 0.0, "by_prefix": {}}


def _youtube_section() -> dict[str, Any]:
    try:
        from apis.youtube_quota import get_usage_summary

        out: dict[str, Any] = dict(get_usage_summary())
    except Exception:
        return {}
    try:
        from core.reset_window import next_reset, reset_window_enabled

        if reset_window_enabled():
            nxt = next_reset("youtube")
            out["next_reset"] = nxt.isoformat() if nxt else None
    except Exception:
        pass
    return out


def _data_quality_section() -> list[str]:
    try:
        from core.data_quality import warnings

        return warnings()
    except Exception:
        return []


def gather() -> dict[str, Any]:
    """Assemble the full reliability snapshot (read-only, fail-open)."""
    return {
        "apify": _apify_section(),
        "llm": _llm_section(),
        "signals": _signals_section(),
        "cache": _cache_section(),
        "youtube": _youtube_section(),
        "data_quality": _data_quality_section(),
    }


def _hhmm(unix_ts: float) -> str:
    from datetime import datetime

    try:
        return datetime.fromtimestamp(float(unix_ts)).strftime("%H:%M")
    except (ValueError, OSError, OverflowError):
        return "?"


def _budget_line(used: float | None, budget: float | None) -> str:
    if budget is None:
        return "no budget set"
    used = used or 0.0
    pct = (used / budget * 100) if budget else 0.0
    flag = " ⚠" if used >= budget else ""
    return f"${used:.2f}/${budget:.2f} ({pct:.0f}%){flag}"


def render(data: dict[str, Any] | None = None) -> str:
    """Format the snapshot as an operator-facing multi-line report."""
    data = data or gather()
    lines = ["Reliability & quota", "=" * 40]

    ap = data.get("apify", {})
    lines.append("Apify")
    lines.append(f"  session : {ap.get('status', 'n/a')}")
    if ap.get("persisted_exhausted"):
        reason = str(ap.get("persisted_reason", ""))
        lines.append(f"  persisted: OFF — {reason}")
        low = reason.lower()
        if "unauthorized" in low or "(403)" in reason or "(401)" in reason:
            lines.append(
                "  hint    : auth/permissions — verify APIFY_CONTENT_MACHINE_KEY (not credits)"
            )
        elif "402" in reason or "credits exhausted" in low:
            lines.append("  hint    : monthly credits exhausted — wait for reset or add billing")
    cache = ap.get("usage_cache")
    if isinstance(cache, dict):
        lines.append(
            f"  usage   : ${cache.get('usage', 0):.2f}/${cache.get('limit', 0):.2f} (cached)"
        )
    lines.append(f"  budget  : {_budget_line(None, ap.get('budget'))}")
    if ap.get("persisted_exhausted") and ap.get("next_reset"):
        lines.append(f"  reset   : cycle resets {str(ap['next_reset'])[:16]} UTC (auto re-enable)")

    llm = data.get("llm", {})
    lines.append("LLM")
    disabled = llm.get("disabled_providers") or {}
    lines.append(f"  disabled: {', '.join(disabled) if disabled else '(none this process)'}")
    lines.append(f"  spend   : {_budget_line(llm.get('spend_today'), llm.get('daily_budget'))}")
    dead = llm.get("dead_models") or {}
    if dead:
        # Retired slugs (e.g. an OpenRouter ':free' variant that was withdrawn).
        # Persisted so a new run skips them instead of re-paying the 404.
        parts = [f"{slug} ({reason})" if reason else slug for slug, reason in dead.items()]
        lines.append("  dead    : " + ", ".join(parts))
        lines.append("            (clears on TTL or when you repoint the model env)")

    sig = data.get("signals", {})
    dis = sig.get("disabled") or []
    lines.append(f"Signals disabled (this process): {', '.join(dis) if dis else '(none)'}")
    cooldowns = sig.get("cooldowns") or {}
    if cooldowns:
        # ASCII arrow: unlike main.py, scripts/ops.py doesn't force UTF-8 stdout,
        # and cp1252 consoles can't encode '→'.
        parts = [f"{name} -> {_hhmm(until)}" for name, until in cooldowns.items()]
        lines.append(f"Signals cooling down (rate-limited): {', '.join(parts)}")
    persisted = sig.get("persisted") or {}
    if persisted:
        parts = [f"{name} ({reason})" if reason else name for name, reason in persisted.items()]
        lines.append("Signals disabled (persisted, clears on key change/TTL): " + ", ".join(parts))

    c = data.get("cache", {})
    total = c.get("total", 0)
    rate = c.get("hit_rate", 0.0) * 100
    lines.append(f"Cache: {c.get('hits', 0)} hits / {total} ({rate:.0f}% hit rate)")
    by_prefix = c.get("by_prefix") or {}
    for name in sorted(by_prefix):
        b = by_prefix[name]
        h, m = b.get("hits", 0), b.get("misses", 0)
        tot = h + m
        if tot:
            lines.append(f"  {name:<16} {h}/{tot} ({h / tot * 100:.0f}%)")

    yt = data.get("youtube", {})
    if yt:
        try:
            from core.themes import meter

            gauge = meter(yt.get("used", 0), yt.get("limit", 0), width=16)
        except Exception:
            gauge = f"{yt.get('used', 0):,}/{yt.get('limit', 0):,}"
        line = f"YouTube units: {gauge} used " f"(~{yt.get('remaining', 0):,} left today)"
        if yt.get("next_reset"):
            line += f" — resets {str(yt['next_reset'])[:16]} UTC"
        lines.append(line)

    dq = data.get("data_quality") or []
    if dq:
        lines.append("Data quality:")
        # ASCII marker for the same cp1252-console reason as the cooldown arrow above.
        lines.extend(f"  ! {w}" for w in dq)
    return "\n".join(lines)


def main() -> int:
    print(render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
