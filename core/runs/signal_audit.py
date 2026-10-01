"""Signal audit over recorded runs: frozen payloads (#588) and contribution (#575).

Both read #386's per-run snapshots (`data/traces/<run>.signals.json`), the trace's
topic and the run's finished script - nothing is fetched.

#588 - a signal served from a stale cache returns the same payload for every topic and
reads as healthy. `frozen_signals` hashes each run's payload and flags one that repeats
unchanged on `FROZEN_MIN_RUNS`+ runs across `FROZEN_MIN_TOPICS`+ topics. Popularity
signals (`core/signal_facts.DEMAND_SIGNALS`) are topic-blind by design: listed, marked
expected.

#575 - "active" is not "useful". `contribution_rows` counts per signal the runs it ran
on, was active on, fed fact lines into the prompt on (its own `format_signal_facts`
block) and was cited on (a named entity from those lines appears in the script). Zero
fed over `RETIRE_MIN_RUNS`+ runs makes a retirement candidate; retiring is the
operator's call (decisions §19), never automatic.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any

from core.logging import get_logger

logger = get_logger("core.runs.signal_audit")

FROZEN_MIN_RUNS = 3
FROZEN_MIN_TOPICS = 2
RETIRE_MIN_RUNS = 10
_NO_FACTS = "No structured facts from signals."


@dataclass
class RunSignals:
    run_id: int
    topic: str
    signals: dict[str, Any] = field(default_factory=dict)
    script: str = ""


def load_runs(limit: int = 60) -> list[RunSignals]:
    """The newest `limit` runs that have a signal snapshot, newest first."""
    from core import run_trace
    from core.runs.replay import load_snapshot

    ids: list[int] = []
    for path in glob.glob(os.path.join(run_trace.TRACES_DIR, "*.signals.json")):
        stem = os.path.basename(path).split(".", 1)[0]
        if stem.isdigit():
            ids.append(int(stem))
    try:
        from storage.repositories.content_runs import get_content_run_repository

        repo: Any = get_content_run_repository()
    except Exception as exc:
        logger.debug("content runs unavailable for the signal audit: %s", exc)
        repo = None
    runs: list[RunSignals] = []
    for run_id in sorted(ids, reverse=True)[:limit]:
        signals = load_snapshot(run_id)
        if not signals:
            continue
        trace = run_trace.read_trace(run_id) or {}
        script = ""
        if repo is not None:
            try:
                record = repo.get(run_id)
                script = str(getattr(record, "script", "") or "")
            except Exception as exc:
                logger.debug("script for run %s unavailable: %s", run_id, exc)
        runs.append(
            RunSignals(
                run_id=run_id,
                topic=str(trace.get("selected_topic") or trace.get("input_topic") or ""),
                signals=signals,
                script=script,
            )
        )
    return runs


def _payload_hash(signal: Any) -> str | None:
    if not isinstance(signal, dict) or not signal.get("data"):
        return None
    blob = json.dumps(signal["data"], sort_keys=True, default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


def frozen_signals(runs: list[RunSignals]) -> list[dict[str, Any]]:
    """[{signal, runs, topics, expected}] for payloads repeated across topics (#588)."""
    from core.signal_facts import DEMAND_SIGNALS

    groups: dict[tuple[str, str], list[RunSignals]] = {}
    for run in runs:
        for name, signal in (run.signals or {}).items():
            digest = _payload_hash(signal)
            if digest and not name.startswith("_"):
                groups.setdefault((name, digest), []).append(run)
    rows: list[dict[str, Any]] = []
    for (name, _digest), members in groups.items():
        topics = {m.topic.strip().lower() for m in members if m.topic.strip()}
        if len(members) >= FROZEN_MIN_RUNS and len(topics) >= FROZEN_MIN_TOPICS:
            rows.append(
                {
                    "signal": name,
                    "runs": sorted(m.run_id for m in members),
                    "topics": len(topics),
                    "expected": name in DEMAND_SIGNALS,
                }
            )
    rows.sort(key=lambda r: (r["expected"], -len(r["runs"]), r["signal"]))
    return rows


def _fed_lines(name: str, signal: dict[str, Any]) -> list[str]:
    from core.signal_facts import DEMAND_SECTION_HEADER, format_signal_facts

    try:
        block = format_signal_facts({name: signal})
    except Exception as exc:
        logger.debug("fact block for %s failed: %s", name, exc)
        return []
    if block.strip() == _NO_FACTS:
        return []
    return [ln for ln in block.splitlines() if ln.strip() and ln.strip() != DEMAND_SECTION_HEADER]


def contribution_rows(runs: list[RunSignals]) -> list[dict[str, Any]]:
    """[{signal, runs, active, fed, cited}] per signal, most-fed first (#575)."""
    from core.facts.grounding import mentions, specific_entities

    rows: dict[str, dict[str, Any]] = {}
    for run in runs:
        for name, signal in (run.signals or {}).items():
            if name.startswith("_") or not isinstance(signal, dict):
                continue
            row = rows.setdefault(
                name, {"signal": name, "runs": 0, "active": 0, "fed": 0, "cited": 0}
            )
            row["runs"] += 1
            if signal.get("active"):
                row["active"] += 1
            lines = _fed_lines(name, signal)
            if not lines:
                continue
            row["fed"] += 1
            if run.script and any(
                mentions(run.script, entity) for line in lines for entity in specific_entities(line)
            ):
                row["cited"] += 1
    return sorted(rows.values(), key=lambda r: (-r["fed"], -r["active"], r["signal"]))


def retirement_candidates(rows: list[dict[str, Any]]) -> list[str]:
    """Signals that ran on `RETIRE_MIN_RUNS`+ runs and never fed the prompt."""
    return sorted(r["signal"] for r in rows if r["runs"] >= RETIRE_MIN_RUNS and r["fed"] == 0)


def report_lines(runs: list[RunSignals] | None = None) -> list[str]:
    """`ops signal-audit`."""
    runs = load_runs() if runs is None else runs
    lines = [f"Signal audit over {len(runs)} recorded run(s) (#575 #588)"]
    if not runs:
        lines.append("  no signal snapshots yet (RUN_SIGNAL_SNAPSHOT, on by default, writes them)")
        return lines
    rows = contribution_rows(runs)
    lines.append("  contribution - runs / active / fed the prompt / cited in the script:")
    for r in rows:
        lines.append(
            f"    {r['signal']:<22} {r['runs']:>3} {r['active']:>4} {r['fed']:>4} {r['cited']:>4}"
        )
    candidates = retirement_candidates(rows)
    if candidates:
        lines.append(
            f"  never fed the prompt in {RETIRE_MIN_RUNS}+ runs (retirement candidates, "
            f"decisions §19): {', '.join(candidates)}"
        )
    frozen = frozen_signals(runs)
    if not frozen:
        lines.append("  frozen payloads: none")
    for f in frozen:
        note = "popularity signal, expected" if f["expected"] else "check its cache"
        lines.append(
            f"  frozen: {f['signal']} returned the same payload on {len(f['runs'])} runs "
            f"across {f['topics']} topics (runs {', '.join(map(str, f['runs'][:8]))}) - {note}"
        )
    return lines


def reliability_line() -> str:
    """One line for `ops reliability`: frozen non-popularity signals, or ""."""
    try:
        frozen = [f for f in frozen_signals(load_runs(limit=30)) if not f["expected"]]
    except Exception as exc:
        logger.debug("frozen-signal check skipped: %s", exc)
        return ""
    if not frozen:
        return ""
    names = ", ".join(f"{f['signal']} ({len(f['runs'])} runs)" for f in frozen)
    return f"Frozen signals (same payload across topics; py -m scripts.ops signal-audit): {names}"
