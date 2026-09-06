"""Per-run trace files (Pillar 1 — Run Ledger).

One JSON per run in ``data/traces/<run_id>.json``, written from
``core/pipeline._finalize_run``. Captures what used to be in-process-only and
lost at exit: phase timings, per-signal status, the LLM call ledger
(tier/provider/tokens/cost from ``llm_router.get_usage()``), cache counters
since the post-discovery flush, the experiment arm, and the persisted quality
dict. Read back by ``ops traces`` / ``ops dossier`` (core/run_ledger.py) and
the data-quality monitor (core/data_quality.py).

Fail-open by contract: a broken trace write must never stall a run.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from config.paths import TRACES_DIR
from core.logging import get_logger

logger = get_logger("core.run_trace")

TRACE_VERSION = "v1"

# Keys whose values can hold API request/response bodies or secrets.
_REDACT_KEYS = frozenset(
    {
        "body",
        "request",
        "response",
        "payload",
        "prompt",
        "messages",
        "content",
        "api_key",
        "apikey",
        "authorization",
        "token",
        "secret",
        "password",
        "input_data",
        "raw",
        "stderr",
    }
)
_REDACTED = "[redacted]"


def redact_trace_value(value: Any, *, key: str = "") -> Any:
    """Drop API bodies / secrets from a trace subtree. Keeps status/cost/tokens."""
    if key.lower() in _REDACT_KEYS:
        return _REDACTED
    if isinstance(value, dict):
        return {str(k): redact_trace_value(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_trace_value(v, key=key) for v in value]
    return value


def _trace_path(run_id: int) -> str:
    return os.path.join(TRACES_DIR, f"{int(run_id)}.json")


def _slim_signals(signals: dict[str, Any] | None) -> dict[str, Any]:
    slim: dict[str, Any] = {}
    for name, sig in (signals or {}).items():
        if not isinstance(sig, dict):
            continue
        slim[name] = {
            "status": sig.get("status"),
            "connected": sig.get("connected"),
            "active": sig.get("active"),
            "score": sig.get("score"),
        }
    return slim


def _llm_calls() -> tuple[list[dict[str, Any]], float]:
    """This run's LLM ledger (already per-run — reset at discovery start)."""
    try:
        from core.cost_meter import llm_cost_from_usage
        from core.llm_router import get_usage

        calls = get_usage()
        priced = []
        total = 0.0
        for call in calls:
            cost = llm_cost_from_usage([call])
            priced.append({**call, "cost_usd": round(cost, 6)})
            total += cost
        return priced, round(total, 6)
    except Exception:
        return [], 0.0


def write_run_trace(
    *,
    run_id: int | None,
    channel_id: str,
    input_topic: str,
    selected_topic: str,
    status: str,
    timings: dict[str, Any] | None = None,
    signals: dict[str, Any] | None = None,
    features: dict[str, Any] | None = None,
    quality: dict[str, Any] | None = None,
    composite_score: float | None = None,
    menu_path: str | None = None,
    angle_intent: str | None = None,
) -> str | None:
    """Write the trace file; returns its path or None (fail-open)."""
    if not run_id:
        return None
    try:
        llm_calls, llm_cost = _llm_calls()
        try:
            from apis.cache_manager import session_cache_stats

            cache = session_cache_stats()
        except Exception:
            cache = {}
        experiment = None
        try:
            from core.experiments import assignment_for_run

            experiment = assignment_for_run(run_id)
        except Exception as exc:
            logger.debug("assignment_for_run skipped: %s", exc)

        trace = {
            "trace_version": TRACE_VERSION,
            "run_id": int(run_id),
            "at": time.time(),
            "channel_id": channel_id,
            "input_topic": input_topic,
            "selected_topic": selected_topic,
            "status": status,
            "timings": dict(timings or {}),
            "signals": _slim_signals(signals),
            "llm_calls": redact_trace_value(llm_calls),
            "llm_cost_usd": llm_cost,
            "cost": (features or {}).get("cost") or {},
            "cache_post_discovery": cache,
            "experiment": experiment,
            "quality": redact_trace_value(dict(quality or {})),
            "composite_score": composite_score,
        }
        if menu_path:
            trace["menu_path"] = str(menu_path)
        if angle_intent:
            trace["angle_intent"] = str(angle_intent)
        os.makedirs(TRACES_DIR, exist_ok=True)
        path = _trace_path(run_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(redact_trace_value(trace), f, indent=2, default=str)
        return path
    except Exception as exc:
        logger.debug("run trace skipped for run %s: %s", run_id, exc)
        return None


def read_trace(run_id: int) -> dict[str, Any] | None:
    """One trace by run id, or None."""
    try:
        with open(_trace_path(run_id), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def update_trace(run_id: int | None, patch: dict[str, Any]) -> bool:
    """Merge keys into an existing trace. Fail-open; False when there was nothing to update.

    The trace is written at `_finalize_run`, which both operator flows reach *before*
    rendering — so every rendered run's trace claimed `status="drafted"` and carried the
    pre-render cost. The render path uses this to correct both after the fact.
    """
    if not run_id or not patch:
        return False
    try:
        current = read_trace(run_id)
        if current is None:
            return False
        current.update(redact_trace_value(patch) if isinstance(patch, dict) else patch)
        with open(_trace_path(run_id), "w", encoding="utf-8") as f:
            json.dump(redact_trace_value(current), f, indent=2)
        return True
    except Exception as exc:
        logger.debug("trace update skipped for run %s: %s", run_id, exc)
        return False


def list_traces(limit: int = 20, *, channel_id: str | None = None) -> list[dict[str, Any]]:
    """Most-recent traces first (by run id), optionally filtered by channel."""
    try:
        names = os.listdir(TRACES_DIR)
    except Exception:
        return []
    run_ids = sorted(
        (int(n[:-5]) for n in names if n.endswith(".json") and n[:-5].isdigit()),
        reverse=True,
    )
    out: list[dict[str, Any]] = []
    for rid in run_ids:
        trace = read_trace(rid)
        if not trace:
            continue
        if channel_id and trace.get("channel_id") != channel_id:
            continue
        out.append(trace)
        if len(out) >= limit:
            break
    return out
