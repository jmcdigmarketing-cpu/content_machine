"""Replay a run offline from what it recorded (#386).

Traces keep four fields per signal, so a scoring or fact-formatting bug seen in a run
could only be chased by fetching the signals again - different answers, more credits.
`save_snapshot` (called by `core/run_trace.write_run_trace`) keeps the full signals
beside the trace as `data/traces/<run>.signals.json`: lists cut to 25 items, strings to
2,000 characters, the biggest `data` payloads dropped past ~400 KB, and secrets scrubbed
the way the trace is. `RUN_SIGNAL_SNAPSHOT=false` stops it (operator's choice: on).

`replay(run_id)` re-scores the snapshot with today's code - the composite against the
recorded one, the signal facts block, event coverage - and `ops replay <run>` prints it.
No network: everything it calls is pure given the signals.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger("core.runs.replay")

_MAX_ITEMS = 25
_MAX_CHARS = 2000
_MAX_BYTES = 400_000


def snapshot_enabled() -> bool:
    raw = (os.getenv("RUN_SIGNAL_SNAPSHOT") or "").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _snapshot_path(run_id: int) -> str:
    from core import run_trace

    return os.path.join(run_trace.TRACES_DIR, f"{int(run_id)}.signals.json")


def _cap(value: Any) -> Any:
    if isinstance(value, str):
        return value if len(value) <= _MAX_CHARS else value[:_MAX_CHARS]
    if isinstance(value, dict):
        return {str(k): _cap(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_cap(v) for v in list(value)[:_MAX_ITEMS]]
    if isinstance(value, int | float | bool) or value is None:
        return value
    return str(value)[:_MAX_CHARS]


def save_snapshot(run_id: int | None, signals: dict[str, Any] | None) -> str | None:
    """Write the run's signals for replay; the path, or None. Never raises."""
    if not run_id or not signals or not snapshot_enabled():
        return None
    try:
        from core.run_trace import _scrub_secrets, env_secret_values

        capped = {name: _cap(sig) for name, sig in signals.items() if isinstance(sig, dict)}
        # Past the byte budget, the biggest payloads go first; the verdict fields stay.
        while len(json.dumps(capped, default=str)) > _MAX_BYTES:
            sized = [
                (len(json.dumps(sig.get("data"), default=str)), name)
                for name, sig in capped.items()
                if sig.get("data") is not None
            ]
            if not sized:
                break
            _size, name = max(sized)
            capped[name] = {**capped[name], "data": None, "data_dropped": "snapshot size cap"}
        body = {"run_id": int(run_id), "signals": _scrub_secrets(capped, env_secret_values())}
        path = _snapshot_path(run_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(body, handle, indent=1, default=str)
        return path
    except Exception as exc:
        logger.debug("signal snapshot skipped for run %s: %s", run_id, exc)
        return None


def load_snapshot(run_id: int) -> dict[str, Any] | None:
    try:
        with open(_snapshot_path(run_id), encoding="utf-8") as handle:
            body = json.load(handle)
    except (OSError, ValueError):
        return None
    signals = body.get("signals") if isinstance(body, dict) else None
    return signals if isinstance(signals, dict) else None


@dataclass
class ReplayReport:
    run_id: int
    topic: str
    channel_id: str
    composite_recorded: float | None
    composite_now: float | None
    fact_lines: int
    fact_preview: list[str] = field(default_factory=list)
    event_covered: bool | None = None
    event_name: str = ""
    statuses: dict[str, str] = field(default_factory=dict)


def replay(run_id: int) -> ReplayReport | None:
    """Re-score a run's snapshot with today's code. None when there is no snapshot."""
    signals = load_snapshot(run_id)
    if signals is None:
        return None
    from apis.topic_scorer import composite_score
    from core.run_trace import read_trace
    from core.signal_facts import format_signal_facts

    trace = read_trace(run_id) or {}
    topic = str(trace.get("selected_topic") or trace.get("input_topic") or "")
    channel = str(trace.get("channel_id") or "")
    recorded = trace.get("composite_score")
    try:
        now: float | None = round(float(composite_score(signals, topic, channel or None)), 2)
    except Exception as exc:
        logger.debug("replay composite failed for run %s: %s", run_id, exc)
        now = None
    facts = [ln for ln in format_signal_facts(signals).splitlines() if ln.strip()]
    covered: bool | None = None
    name = ""
    try:
        from core.event_research import precheck

        check = precheck(topic, signals, [])
        if check is not None:
            covered, name = bool(check.get("covered")), str(check.get("name") or "")
    except Exception as exc:
        logger.debug("replay event coverage skipped: %s", exc)
    return ReplayReport(
        run_id=int(run_id),
        topic=topic,
        channel_id=channel,
        composite_recorded=round(float(recorded), 2) if isinstance(recorded, int | float) else None,
        composite_now=now,
        fact_lines=len(facts),
        fact_preview=facts[:5],
        event_covered=covered,
        event_name=name,
        statuses={n: str(s.get("status") or "") for n, s in signals.items() if isinstance(s, dict)},
    )


def report_lines(report: ReplayReport) -> list[str]:
    lines = [f"Replay of run {report.run_id} - {report.topic} ({report.channel_id}), offline"]
    rec, now = report.composite_recorded, report.composite_now
    if rec is None:
        lines.append(f"  composite: {now} today (none recorded)")
    elif now == rec:
        lines.append(f"  composite: {now} - unchanged")
    else:
        lines.append(f"  composite: {rec} recorded -> {now} today - changed")
    lines.append(f"  signal facts: {report.fact_lines} line(s)")
    lines.extend(f"    {ln[:110]}" for ln in report.fact_preview)
    if report.event_covered is not None:
        verdict = "covered" if report.event_covered else "NOT covered"
        lines.append(f"  event coverage: '{report.event_name}' {verdict}")
    active = sorted(n for n, s in report.statuses.items() if s == "ok")
    other = sorted(f"{n}={s}" for n, s in report.statuses.items() if s and s != "ok")
    lines.append(f"  signals ok: {', '.join(active) or '-'}")
    if other:
        lines.append(f"  others: {', '.join(other)}")
    return lines
