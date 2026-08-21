"""ops postmortem --run-id (candidate 29).

Assembled from traces + quality that already exist: slowest phase, failed
signals, ungrounded claims, cost, a next-fix hint. Fail-open. Tests pass
dicts — never write data/traces.
"""

from __future__ import annotations

import json
from typing import Any

from core.logging import get_logger

logger = get_logger("core.postmortem")

_PHASE_KEYS = (
    "signals_and_variants",
    "variant_scoring",
    "research_brief",
    "content_package",
)


def _load_json(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _slowest_phase(timings: dict[str, Any]) -> tuple[str, float] | None:
    best: tuple[str, float] | None = None
    for key in _PHASE_KEYS:
        try:
            sec = float(timings.get(key))
        except (TypeError, ValueError):
            continue
        if best is None or sec > best[1]:
            best = (key, sec)
    return best


def _failed_signals(signals: dict[str, Any]) -> list[str]:
    out = []
    for name, sig in (signals or {}).items():
        if not isinstance(sig, dict):
            continue
        status = str(sig.get("status") or "")
        if status and status not in ("ok", "inactive", "skipped"):
            out.append(f"{name}:{status}")
    return sorted(out)


def _next_fix(failed: list[str], ungrounded: int, cost: dict[str, Any], slow: str | None) -> str:
    tts = float(cost.get("tts") or 0)
    if ungrounded:
        return "grounding: remaining ungrounded claims — paste operator facts, re-run"
    if any("quota" in f or "auth" in f for f in failed):
        return "quota/auth: check ops reliability breakers before the next paid call"
    if tts <= 0 and float(cost.get("total") or 0) <= 0:
        return "ledger: cost is $0 — was this a draft, or did render skip persist?"
    if slow == "signals_and_variants":
        return "discovery: slowest phase is signals — skip dead actors, cap workers"
    if failed:
        return f"signals: {failed[0]} — see ops incidents"
    return "no obvious defect in this trace — check grade + authenticity next"


def assemble(
    *,
    run_id: int,
    trace: dict[str, Any] | None = None,
    quality: dict[str, Any] | None = None,
    cost: dict[str, Any] | None = None,
) -> dict[str, Any]:
    t = dict(trace or {})
    q = quality if quality is not None else _load_json(t.get("quality"))
    c = cost if cost is not None else _load_json(t.get("cost") if "cost" in t else None)
    if not c:
        c = _load_json(
            (t.get("features") or {}).get("cost") if isinstance(t.get("features"), dict) else None
        )
    timings = t.get("timings") or {}
    slow = _slowest_phase(timings if isinstance(timings, dict) else {})
    failed = _failed_signals(t.get("signals") or {})
    ungrounded = int(q.get("ungrounded_count") or 0)
    slow_name = slow[0] if slow else None
    return {
        "run_id": run_id,
        "status": t.get("status") or "",
        "topic": t.get("selected_topic") or t.get("input_topic") or "",
        "slowest": {"phase": slow[0], "seconds": round(slow[1], 2)} if slow else None,
        "failed_signals": failed,
        "ungrounded_count": ungrounded,
        "cost_usd": float(c.get("total") or t.get("llm_cost_usd") or 0.0),
        "llm_cost_usd": float(t.get("llm_cost_usd") or c.get("llm") or 0.0),
        "next_fix": _next_fix(failed, ungrounded, c, slow_name),
    }


def from_store(run_id: int) -> dict[str, Any]:
    """Load trace + run row. Fail-open with a stub if missing."""
    trace: dict[str, Any] = {}
    quality: dict[str, Any] = {}
    cost: dict[str, Any] = {}
    try:
        from core.run_trace import load_trace

        loaded = load_trace(run_id)
        if isinstance(loaded, dict):
            trace = loaded
    except Exception as exc:
        logger.debug("postmortem trace skipped: %s", exc)
    try:
        from storage.repositories.content_runs import get_content_run_repository

        rec = get_content_run_repository().get(run_id)
        if rec is not None:
            quality = _load_json(rec.quality_json)
            features = _load_json(rec.features_json)
            cost = features.get("cost") if isinstance(features.get("cost"), dict) else {}
            trace.setdefault("status", rec.status)
            trace.setdefault("selected_topic", rec.selected_topic)
    except Exception as exc:
        logger.debug("postmortem run row skipped: %s", exc)
    return assemble(run_id=run_id, trace=trace, quality=quality, cost=cost)


def render(data: dict[str, Any]) -> str:
    lines = [
        f"Postmortem — run #{data.get('run_id')}",
        "=" * 48,
        f"  topic     : {data.get('topic') or 'n/a'}",
        f"  status    : {data.get('status') or 'n/a'}",
    ]
    slow = data.get("slowest")
    if slow:
        lines.append(f"  slowest   : {slow.get('phase')} ({slow.get('seconds')}s)")
    else:
        lines.append("  slowest   : n/a")
    failed = data.get("failed_signals") or []
    lines.append(f"  signals   : {', '.join(failed) if failed else '(all ok / none recorded)'}")
    lines.append(f"  ungrounded: {int(data.get('ungrounded_count') or 0)}")
    lines.append(f"  cost      : ${float(data.get('cost_usd') or 0):.4f}")
    lines.append(f"  next fix  : {data.get('next_fix')}")
    return "\n".join(lines)
