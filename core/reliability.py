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

from core.logging import get_logger

logger = get_logger("core.reliability")


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
    except Exception as exc:
        logger.debug("apify_get_usage skipped: %s", exc)
    try:
        from core.reset_window import next_reset, reset_window_enabled

        if reset_window_enabled():
            nxt = next_reset("apify")
            out["next_reset"] = nxt.isoformat() if nxt else None
    except Exception as exc:
        logger.debug("Reset-window line skipped: %s", exc)
    return out


def _llm_section() -> dict[str, Any]:
    out: dict[str, Any] = {"daily_budget": _f("LLM_DAILY_BUDGET_USD")}
    try:
        from core.llm_router import disabled_providers

        out["disabled_providers"] = disabled_providers()
        from core.quota_governor import llm_spend_today, persisted_dead_models

        out["spend_today"] = llm_spend_today()
        out["dead_models"] = dict(sorted(persisted_dead_models().items()))
    except Exception as exc:
        logger.debug("llm reliability section skipped: %s", exc)
        out["disabled_providers"] = {}
    try:
        from core.cost_meter import escaped_free_first

        out["escaped_free_first"] = escaped_free_first()
    except Exception as exc:
        logger.debug("escaped_free_first skipped: %s", exc)
        out["escaped_free_first"] = False
    return out


def _signals_section() -> dict[str, Any]:
    out: dict[str, Any] = {"disabled": [], "cooldowns": {}, "persisted": {}}
    try:
        from core.quota_governor import persisted_disabled_signals

        out["persisted"] = dict(sorted(persisted_disabled_signals().items()))
    except Exception as exc:
        logger.debug("persisted_disabled_signals skipped: %s", exc)
    try:
        from apis.register_signals import disabled_signals, signal_cooldowns

        cooldowns = signal_cooldowns()
        out["disabled"] = sorted(disabled_signals() - set(cooldowns) - set(out["persisted"]))
        out["cooldowns"] = dict(sorted(cooldowns.items()))
    except Exception as exc:
        logger.debug("disabled_signals skipped: %s", exc)
    return out


def _cache_section() -> dict[str, Any]:
    try:
        from apis.cache_manager import get_cache_stats

        return get_cache_stats()
    except Exception:
        return {"total": 0, "hit_rate": 0.0, "by_prefix": {}}


def _youtube_section() -> dict[str, Any]:
    try:
        from apis.youtube_quota import get_usage_summary, uploads_remaining

        summary = get_usage_summary()
        out: dict[str, Any] = dict(summary)
        out["uploads_left"] = uploads_remaining(summary)
    except Exception as exc:
        logger.debug("youtube quota section skipped: %s", exc)
        return {}
    try:
        from core.reset_window import next_reset, reset_window_enabled

        if reset_window_enabled():
            nxt = next_reset("youtube")
            out["next_reset"] = nxt.isoformat() if nxt else None
    except Exception as ext:
        logger.debug("Reset-window line skipped: %s", ext)
    return out


def _data_quality_section() -> list[str]:
    try:
        from core.data_quality import warnings

        return warnings()
    except Exception:
        return []


def _elevenlabs_section() -> dict[str, Any]:
    raw = os.getenv("ELEVENLABS_MONTHLY_CHAR_BUDGET", "").strip()
    budget: int | None = None
    if raw.lower() not in ("", "0", "off", "false", "no"):
        try:
            val = int(raw)
            budget = val if val > 0 else None
        except ValueError:
            budget = None
    out: dict[str, Any] = {"budget": budget}
    try:
        from core.quota_governor import elevenlabs_chars_reading

        # #724: None when the ledger is unreadable -- unknown, never zero.
        out["chars_used"] = elevenlabs_chars_reading()
    except Exception as exc:
        logger.debug("elevenlabs_chars_reading skipped: %s", exc)
        out["chars_used"] = None
    return out


def _competitor_health_section() -> list[str]:
    try:
        from config.channels import resolve_channel_id
        from core.competitor_health import inspect_competitors, warning_lines

        cid = resolve_channel_id(os.getenv("CONTENT_CHANNEL_ID") or None)
        report = inspect_competitors(cid, missing_snapshot_ok=True)
        return warning_lines(report)
    except Exception as exc:
        logger.debug("competitor health section skipped: %s", exc)
        return []


def _fact_expiry_section() -> list[str]:
    try:
        from core.fact_expiry import warning_lines

        return warning_lines(os.getenv("CONTENT_CHANNEL_ID") or None)
    except Exception as exc:
        logger.debug("fact expiry section skipped: %s", exc)
        return []


def _policy_canary_section() -> list[str]:
    """Snapshot only — no HTTP (same shape as competitor health)."""
    try:
        from core.policy_canary import warning_lines

        return warning_lines()
    except Exception as exc:
        logger.debug("policy canary section skipped: %s", exc)
        return []


def _metrics_sync_section() -> dict[str, Any]:
    """Stalled metrics sync is an incident (#366). Fresh sync is not a WARNING."""
    try:
        import json
        from datetime import datetime, timezone

        from config.channels import resolve_channel_id
        from core.metrics_sync_health import metrics_sync_incident
        from storage.repositories.publish_log import get_publish_log_repository

        cid = resolve_channel_id(os.getenv("CONTENT_CHANNEL_ID") or None)
        rows = get_publish_log_repository().list_uploaded_for_channel(cid)
        uploads = len(rows)
        now = datetime.now(timezone.utc)
        ages: list[float] = []
        for row in rows:
            try:
                metrics = json.loads(row.metrics_json or "{}")
            except Exception:
                metrics = {}
            if not isinstance(metrics, dict) or not metrics:
                continue
            when = row.published_at
            if when is None:
                ages.append(0.0)
                continue
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            ages.append(max(0.0, (now - when).total_seconds() / 86400.0))
        last_age = min(ages) if ages else (None if uploads else 0.0)
        incident = metrics_sync_incident(
            uploads=uploads, last_metrics_age_days=last_age, stall_days=7.0
        )
        detail = incident or (
            f"metrics sync fresh ({last_age:.0f}d)"
            if last_age is not None
            else "metrics sync fresh"
        )
        return {"incident": incident, "detail": detail}
    except Exception as exc:
        logger.debug("metrics sync section skipped: %s", exc)
        return {"incident": None, "detail": "metrics sync n/a"}


def _store_section() -> dict[str, Any]:
    try:
        from config.paths import DATA_DIR

        path = os.path.join(DATA_DIR, "content_os.db")
        if os.path.isfile(path):
            size = os.path.getsize(path)
            return {"bytes": size, "detail": f"sqlite {size} bytes"}
        return {"bytes": 0, "detail": "database n/a"}
    except Exception as exc:
        logger.debug("store size skipped: %s", exc)
        return {"bytes": 0, "detail": "database n/a"}


def gather() -> dict[str, Any]:
    """Assemble the full reliability snapshot (read-only, fail-open)."""
    return {
        "apify": _apify_section(),
        "llm": _llm_section(),
        "signals": _signals_section(),
        "cache": _cache_section(),
        "youtube": _youtube_section(),
        "elevenlabs": _elevenlabs_section(),
        "data_quality": _data_quality_section(),
        "competitor_health": _competitor_health_section(),
        "fact_expiry": _fact_expiry_section(),
        "policy_canary": _policy_canary_section(),
        "metrics_sync": _metrics_sync_section(),
        "store": _store_section(),
    }


def _hhmm(unix_ts: float) -> str:
    from datetime import datetime

    try:
        return datetime.fromtimestamp(float(unix_ts)).strftime("%H:%M")
    except (ValueError, OSError, OverflowError):
        return "?"


def _utilization_lines(data: dict[str, Any]) -> list[str]:
    """Unused quota as allocated leftover — generalizes ops economics item 4."""
    out: list[str] = []
    el = data.get("elevenlabs") or {}
    budget = el.get("budget")
    if budget and "chars_used" in el and el["chars_used"] is None:
        # #724: the ledger could not be read, so "all of it unused" would be invented.
        out.append("ElevenLabs: unused chars unknown (ledger unreadable)")
    elif budget:
        used = int(el.get("chars_used") or 0)
        left = max(0, int(budget) - used)
        try:
            from core.unit_economics import _plan_chars, _plan_usd

            chars = _plan_chars()
            leftover_usd = (left / chars) * _plan_usd() if chars else 0.0
        except Exception as exc:
            logger.debug("TTS leftover allocation skipped: %s", exc)
            leftover_usd = 0.0
        out.append(
            f"ElevenLabs: {left:,} chars unused"
            + (f" (~${leftover_usd:.2f} allocated leftover)" if leftover_usd else "")
        )
    cache = (data.get("apify") or {}).get("usage_cache")
    if isinstance(cache, dict):
        try:
            limit = float(cache.get("limit") or 0)
            usage = float(cache.get("usage") or 0)
        except (TypeError, ValueError):
            limit, usage = 0.0, 0.0
        if limit > 0:
            leftover = max(0.0, limit - usage)
            out.append(f"Apify: ${leftover:.2f} unused of ${limit:.2f} cached limit")
    yt = data.get("youtube") or {}
    if yt.get("limit"):
        left = yt.get("uploads_left")
        if left is None:
            try:
                from apis.youtube_quota import uploads_remaining

                left = uploads_remaining(yt)
            except Exception as exc:
                logger.debug("uploads_remaining skipped: %s", exc)
                left = 0
        out.append(f"YouTube: ~{left} uploads leftover this reset")
    return out


def _budget_line(used: float | None, budget: float | None) -> str:
    if budget is None:
        return "no budget set"
    used = used or 0.0
    pct = (used / budget * 100) if budget else 0.0
    flag = " ⚠" if used >= budget else ""
    return f"${used:.2f}/${budget:.2f} ({pct:.0f}%){flag}"


def _apify_cache_dollars_saved(by_prefix: dict[str, Any]) -> float:
    """Hits on paid Apify signal prefixes × COST_APIFY_PER_RUN (#372)."""
    try:
        from core.cost_meter import _APIFY_SIGNALS, _rate
    except Exception:
        return 0.0
    hits = 0
    for name in _APIFY_SIGNALS:
        bucket = (by_prefix or {}).get(name) or {}
        try:
            hits += int(bucket.get("hits") or 0)
        except (TypeError, ValueError):
            continue
    if hits <= 0:
        return 0.0
    return round(hits * _rate("COST_APIFY_PER_RUN", 0.02), 4)


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
    if llm.get("escaped_free_first"):
        lines.append("  escaped : this process used a paid LLM after a free-first miss")
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
    saved = _apify_cache_dollars_saved(by_prefix)
    if saved > 0:
        lines.append(f"  Apify cache hits saved ~${saved:.2f}")

    yt = data.get("youtube", {})
    if yt:
        try:
            from core.themes import meter

            gauge = meter(yt.get("used", 0), yt.get("limit", 0), width=16)
        except Exception:
            gauge = f"{yt.get('used', 0):,}/{yt.get('limit', 0):,}"
        uploads_left = yt.get("uploads_left")
        if uploads_left is None:
            try:
                from apis.youtube_quota import uploads_remaining

                uploads_left = uploads_remaining(yt)
            except Exception as exc:
                logger.debug("uploads_remaining skipped: %s", exc)
                uploads_left = 0
        line = (
            f"YouTube units: {gauge} used "
            f"(~{yt.get('remaining', 0):,} left today; ~{uploads_left} uploads left this reset)"
        )
        if yt.get("next_reset"):
            line += f" — resets {str(yt['next_reset'])[:16]} UTC"
        lines.append(line)
        if int(uploads_left or 0) < 1:
            try:
                from apis.youtube_quota import quota_increase_advice

                lines.append(quota_increase_advice(yt if yt.get("remaining") is not None else None))
            except Exception as exc:
                logger.debug("quota increase playbook skipped: %s", exc)

    util = _utilization_lines(data)
    if util:
        lines.append("Subscription utilization")
        lines.extend(f"  {u}" for u in util)

    el = data.get("elevenlabs") or {}
    if el.get("budget") and "chars_used" in el and el["chars_used"] is None:
        # #724: an unreadable ledger is not "0 used".
        lines.append(f"ElevenLabs chars: unknown/{int(el['budget']):,} (ledger unreadable)")
    elif el.get("budget"):
        used = int(el.get("chars_used") or 0)
        budget = int(el["budget"])
        pct = (used / budget * 100) if budget else 0.0
        flag = " !" if used >= budget else ""
        lines.append(f"ElevenLabs chars: {used:,}/{budget:,} ({pct:.0f}%){flag}")

    dq = data.get("data_quality") or []
    if dq:
        lines.append("Data quality:")
        # ASCII marker for the same cp1252-console reason as the cooldown arrow above.
        lines.extend(f"  ! {w}" for w in dq)

    ch = data.get("competitor_health") or []
    if ch:
        lines.append("Competitor health:")
        lines.extend(f"  ! {w}" for w in ch)

    fe = data.get("fact_expiry") or []
    if fe:
        lines.append("Fact expiry:")
        lines.extend(f"  ! {w}" for w in fe)

    pc = data.get("policy_canary") or []
    if pc:
        lines.append("Policy canary:")
        lines.extend(f"  ! {w}" for w in pc)

    ms = data.get("metrics_sync") or {}
    if isinstance(ms, dict) and (ms.get("incident") or ms.get("detail")):
        lines.append(f"  metrics : {ms.get('incident') or ms.get('detail')}")

    store = data.get("store") or {}
    if isinstance(store, dict) and store.get("detail"):
        lines.append(f"  database: {store.get('detail')}")

    inc = data.get("incidents") or []
    if inc:
        lines.append("Incidents (count x recency):")
        lines.extend(f"  ! {w}" for w in inc)
    return "\n".join(lines)


def main() -> int:
    print(render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
