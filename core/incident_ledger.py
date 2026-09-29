"""Integration incident ledger (morning candidate).

Persist signal/provider failures ranked by count x recency. Computed from run
traces (already persisted) — this module does not run inside the signal
ThreadPoolExecutor and does not write quota_state. Snapshot file is isolated
in tests via ``INCIDENTS_FILE``.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

from config.paths import DATA_DIR
from core.logging import get_logger

logger = get_logger("core.incident_ledger")

INCIDENTS_FILE = os.path.join(DATA_DIR, "incidents.json")

_FAIL = {
    "no_key",
    "quota_exceeded",
    "rate_limited",
    "auth_error",
    "upstream_error",
    "http_error",
    "unavailable",
    "error",
}


@dataclass
class Incident:
    key: str
    kind: str
    name: str
    count: int
    last_at: float
    score: float
    last_status: str = ""
    # #908: why - counts per reason (`reason_of`), and the newest detail as written.
    reasons: dict[str, int] = field(default_factory=dict)
    last_detail: str = ""


# Checked in order; the first match names the reason. HTTP codes match as whole numbers
# ("read 1500 bytes" is not a server error).
_REASONS = (
    ("deadline", re.compile(r"discovery deadline")),
    ("timeout", re.compile(r"timed out|timeout")),
    ("schema drift", re.compile(r"schema drift")),
    ("quota", re.compile(r"quota")),
    ("rate limit", re.compile(r"rate.?limit|\b429\b|too many requests")),
    ("auth", re.compile(r"\b40[13]\b|unauthori[sz]ed|forbidden|invalid (?:api )?key")),
    ("server error", re.compile(r"server error|\b50[0-4]\b")),
    ("no key", re.compile(r"^set [a-z_]+(?:_key|_id|_token)\b|no key")),
)


def reason_of(status: str, detail: str | None) -> str:
    """#908: one word for why a signal failed, from its status and detail.

    `None` means the trace predates #908 (no detail was kept) - said, never guessed.
    An empty detail on `unavailable` is a signal that never connected.
    """
    if detail is None:
        return "before #908"
    text = detail.lower()
    for reason, pattern in _REASONS:
        if pattern.search(text):
            return reason
    status = (status or "").lower()
    if status == "unavailable" and not text.strip():
        return "not connected"
    if status == "quota_exceeded":
        return "quota"
    if status == "rate_limited":
        return "rate limit"
    if status == "no_key":
        return "no key"
    return "other"


def _age_days(last_at: float, now: float) -> float:
    return max(0.0, (now - last_at) / 86400.0)


def rank_incidents(
    traces: list[dict[str, Any]],
    *,
    now: float | None = None,
) -> list[Incident]:
    """Rank failures: score = count / (1 + days since last). Newest traces first OK."""
    clock = float(now if now is not None else time.time())
    buckets: dict[str, dict[str, Any]] = {}
    for trace in traces:
        at = trace.get("at")
        try:
            ts = float(at) if at is not None else clock
        except (TypeError, ValueError):
            ts = clock
        for name, sig in (trace.get("signals") or {}).items():
            if not isinstance(sig, dict):
                continue
            status = str(sig.get("status") or "")
            if status not in _FAIL:
                continue
            key = f"signal:{name}"
            row = buckets.setdefault(
                key,
                {"kind": "signal", "name": name, "count": 0, "last_at": 0.0, "last_status": ""},
            )
            row["count"] += 1
            detail = sig.get("status_detail") if "status_detail" in sig else None
            reasons = row.setdefault("reasons", {})
            reason = reason_of(status, None if detail is None else str(detail))
            reasons[reason] = reasons.get(reason, 0) + 1
            if ts >= float(row["last_at"]):
                row["last_at"] = ts
                row["last_status"] = status
                row["last_detail"] = str(detail or "")
        for call in trace.get("llm_calls") or []:
            if not isinstance(call, dict):
                continue
            err = str(call.get("error") or call.get("status") or "")
            if not err or err.lower() in ("ok", "ok_status", ""):
                continue
            # Only count explicit failures, not successful priced calls.
            if not call.get("error") and str(call.get("status") or "").lower() in (
                "",
                "ok",
            ):
                continue
            if not call.get("error"):
                continue
            provider = str(call.get("provider") or call.get("model") or "llm")
            key = f"llm:{provider}"
            row = buckets.setdefault(
                key,
                {"kind": "llm", "name": provider, "count": 0, "last_at": 0.0, "last_status": ""},
            )
            row["count"] += 1
            if ts >= float(row["last_at"]):
                row["last_at"] = ts
                row["last_status"] = str(call.get("error") or "error")[:80]
    incidents = []
    for key, row in buckets.items():
        last_at = float(row["last_at"] or 0.0)
        score = float(row["count"]) / (1.0 + _age_days(last_at, clock))
        incidents.append(
            Incident(
                key=key,
                kind=str(row["kind"]),
                name=str(row["name"]),
                count=int(row["count"]),
                last_at=last_at,
                score=round(score, 4),
                last_status=str(row["last_status"]),
                reasons=dict(row.get("reasons") or {}),
                last_detail=str(row.get("last_detail") or ""),
            )
        )
    incidents.sort(key=lambda i: (-i.score, -i.count, i.key))
    return incidents


def persist(incidents: list[Incident], *, path: str | None = None) -> str | None:
    dest = path or INCIDENTS_FILE
    payload = {
        "at": time.time(),
        "incidents": [
            {
                "key": i.key,
                "kind": i.kind,
                "name": i.name,
                "count": i.count,
                "last_at": i.last_at,
                "score": i.score,
                "last_status": i.last_status,
                "reasons": dict(i.reasons),
                "last_detail": i.last_detail,
            }
            for i in incidents
        ],
    }
    try:
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        return dest
    except Exception as exc:
        logger.debug("incident ledger not written: %s", exc)
        return None


def render(incidents: list[Incident], *, limit: int = 8) -> str:
    if not incidents:
        return "Incidents: none in recent traces"
    lines = ["Incidents (count x recency)", "=" * 40]
    for row in incidents[:limit]:
        why = ""
        if row.reasons:
            parts = sorted(row.reasons.items(), key=lambda kv: (-kv[1], kv[0]))
            why = " (" + ", ".join(f"{reason} {n}" for reason, n in parts) + ")"
        lines.append(
            f"  {row.kind} {row.name}: n={row.count} score={row.score:.2f} "
            f"last={row.last_status or '?'}{why}"
        )
    return "\n".join(lines)


def gather_and_record(
    traces: list[dict[str, Any]] | None = None,
    *,
    limit: int = 40,
    persist_path: str | None = None,
) -> list[Incident]:
    if traces is None:
        try:
            from core.run_trace import list_traces

            traces = list_traces(limit=limit)
        except Exception as exc:
            logger.debug("incident traces skipped: %s", exc)
            traces = []
    incidents = rank_incidents(traces or [])
    persist(incidents, path=persist_path)
    return incidents
