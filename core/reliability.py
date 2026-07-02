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
        from core.quota_state import get_value, is_exhausted

        exhausted, reason = is_exhausted("apify", "main")
        out["persisted_exhausted"] = exhausted
        out["persisted_reason"] = reason
        out["usage_cache"] = get_value("apify_usage:main")
    except Exception:
        pass
    return out


def _llm_section() -> dict[str, Any]:
    out: dict[str, Any] = {"daily_budget": _f("LLM_DAILY_BUDGET_USD")}
    try:
        from core.llm_router import _today_spend_key, disabled_providers

        out["disabled_providers"] = disabled_providers()
        from core.quota_state import get_value

        out["spend_today"] = float(get_value(_today_spend_key(), 0.0) or 0.0)
    except Exception:
        out["disabled_providers"] = {}
    return out


def _signals_section() -> dict[str, Any]:
    try:
        from apis.register_signals import disabled_signals, signal_cooldowns

        cooldowns = signal_cooldowns()
        return {
            "disabled": sorted(disabled_signals() - set(cooldowns)),
            "cooldowns": dict(sorted(cooldowns.items())),
        }
    except Exception:
        return {"disabled": [], "cooldowns": {}}


def _cache_section() -> dict[str, Any]:
    try:
        from apis.cache_manager import get_cache_stats

        return get_cache_stats()
    except Exception:
        return {"total": 0, "hit_rate": 0.0, "by_prefix": {}}


def _youtube_section() -> dict[str, Any]:
    try:
        from apis.youtube_quota import get_usage_summary

        return get_usage_summary()
    except Exception:
        return {}


def gather() -> dict[str, Any]:
    """Assemble the full reliability snapshot (read-only, fail-open)."""
    return {
        "apify": _apify_section(),
        "llm": _llm_section(),
        "signals": _signals_section(),
        "cache": _cache_section(),
        "youtube": _youtube_section(),
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

    llm = data.get("llm", {})
    lines.append("LLM")
    disabled = llm.get("disabled_providers") or {}
    lines.append(f"  disabled: {', '.join(disabled) if disabled else '(none this process)'}")
    lines.append(f"  spend   : {_budget_line(llm.get('spend_today'), llm.get('daily_budget'))}")

    sig = data.get("signals", {})
    dis = sig.get("disabled") or []
    lines.append(f"Signals disabled (this process): {', '.join(dis) if dis else '(none)'}")
    cooldowns = sig.get("cooldowns") or {}
    if cooldowns:
        # ASCII arrow: unlike main.py, scripts/ops.py doesn't force UTF-8 stdout,
        # and cp1252 consoles can't encode '→'.
        parts = [f"{name} -> {_hhmm(until)}" for name, until in cooldowns.items()]
        lines.append(f"Signals cooling down (rate-limited): {', '.join(parts)}")

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
        lines.append(
            f"YouTube units: {yt.get('used', 0):,}/{yt.get('limit', 0):,} used "
            f"(~{yt.get('remaining', 0):,} left today)"
        )
    return "\n".join(lines)


def main() -> int:
    print(render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
