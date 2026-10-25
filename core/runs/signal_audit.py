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

from core import process_state
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
    seconds: dict[str, float] = field(default_factory=dict)


def load_runs(
    limit: int = 60, *, channel_id: str | None = None, with_scripts: bool = True
) -> list[RunSignals]:
    """The newest `limit` runs that have a signal snapshot, newest first.

    `channel_id` keeps that channel's runs only (#585: wave 51 mixed tapin and
    moneywise); `with_scripts=False` skips the script reads the "fed" count never needs.
    """
    from core import run_trace
    from core.runs.replay import load_snapshot

    ids: list[int] = []
    for path in glob.glob(os.path.join(run_trace.TRACES_DIR, "*.signals.json")):
        stem = os.path.basename(path).split(".", 1)[0]
        if stem.isdigit():
            ids.append(int(stem))
    runs: list[RunSignals] = []
    for run_id in sorted(ids, reverse=True):
        if len(runs) >= limit:
            break
        trace = run_trace.read_trace(run_id) or {}
        if channel_id and str(trace.get("channel_id") or "") != channel_id:
            continue
        signals = load_snapshot(run_id)
        if not signals:
            continue
        # #939: a content run has no `script` field, so "cited" was 0 everywhere. The final
        # script is kept beside the trace (#774); older runs fall back to the 2,000-char preview.
        script = (run_trace.full_script(run_id) or _script_preview(run_id)) if with_scripts else ""
        runs.append(
            RunSignals(
                run_id=run_id,
                topic=str(trace.get("selected_topic") or trace.get("input_topic") or ""),
                signals=signals,
                script=script,
                seconds=_seconds(trace),
            )
        )
    return runs


def _script_preview(run_id: int) -> str:
    try:
        from storage.repositories.content_runs import get_content_run_repository

        record = get_content_run_repository().get(run_id)
    except Exception as exc:
        logger.debug("script preview for run %s unavailable: %s", run_id, exc)
        return ""
    return str(getattr(record, "script_preview", "") or "")


def _seconds(trace: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for name, value in (trace.get("signal_seconds") or {}).items():
        try:
            out[str(name)] = float(value)
        except (TypeError, ValueError):
            continue
    return out


def _percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile: p50 of [1, 2, 9] is 2, p90 is 9."""
    ordered = sorted(values)
    rank = max(1, -(-int(q * 100) * len(ordered) // 100))
    return ordered[min(rank, len(ordered)) - 1]


def seconds_by_signal(runs: list[RunSignals]) -> dict[str, tuple[float, float]]:
    """{signal: (p50, p90)} over the runs that recorded its seconds (#591)."""
    samples: dict[str, list[float]] = {}
    for run in runs:
        for name, value in (run.seconds or {}).items():
            samples.setdefault(name, []).append(value)
    return {n: (_percentile(v, 0.5), _percentile(v, 0.9)) for n, v in samples.items() if v}


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


def domain_lines(runs: list[RunSignals]) -> list[str]:
    """#1370: per topic domain, what fed the prompt and what ran and fed nothing. On 10-24, over
    60 runs, ufc_context ran on all 9 NBA runs and fed nothing - the all-runs table hid it."""
    from apis.topic_scorer import infer_topic_domain

    groups: dict[str, list[RunSignals]] = {}
    for run in runs:
        groups.setdefault(infer_topic_domain(run.topic) or "neutral", []).append(run)
    lines: list[str] = []
    for domain, members in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        rows = contribution_rows(members)
        fed = [f"{r['signal']} {r['fed']}" for r in rows if r["fed"]][:5]
        idle = sorted((r for r in rows if not r["fed"]), key=lambda r: (-r["runs"], r["signal"]))
        count = f"{len(members)} run{'' if len(members) == 1 else 's'}"
        line = f"    {domain} ({count}): fed most - {', '.join(fed) or 'nothing'}"
        if idle:
            line += "; ran, never fed - " + ", ".join(f"{r['signal']} {r['runs']}" for r in idle)
        lines.append(line)
    return lines


def retirement_candidates(rows: list[dict[str, Any]]) -> list[str]:
    """Signals that ran on `RETIRE_MIN_RUNS`+ runs and never fed the prompt."""
    return sorted(r["signal"] for r in rows if r["runs"] >= RETIRE_MIN_RUNS and r["fed"] == 0)


def report_lines(
    runs: list[RunSignals] | None = None, *, channel_id: str | None = None
) -> list[str]:
    """`ops signal-audit`."""
    runs = load_runs(channel_id=channel_id) if runs is None else runs
    where = f" for {channel_id}" if channel_id else ""
    lines = [f"Signal audit{where} over {len(runs)} recorded run(s) (#575 #588)"]
    if not runs:
        lines.append("  no signal snapshots yet (RUN_SIGNAL_SNAPSHOT, on by default, writes them)")
        return lines
    rows = contribution_rows(runs)
    timing = seconds_by_signal(runs)
    header = "  contribution - runs / active / fed the prompt / cited in the script"
    lines.append(header + (" / seconds p50/p90:" if timing else ":"))
    for r in rows:
        line = (
            f"    {r['signal']:<22} {r['runs']:>3} {r['active']:>4} {r['fed']:>4} {r['cited']:>4}"
        )
        if r["signal"] in timing:
            p50, p90 = timing[r["signal"]]
            line += f"   {p50:.1f}s / {p90:.1f}s"
        lines.append(line)
    candidates = retirement_candidates(rows)
    if candidates:
        lines.append(
            f"  never fed the prompt in {RETIRE_MIN_RUNS}+ runs (retirement candidates, "
            f"decisions §19): {', '.join(candidates)}"
        )
    lines.append(
        "  by topic domain - what fed the prompt most, and what ran and fed nothing (#1370):"
    )
    lines += domain_lines(runs)
    if channel_id:
        demoted = demotion_line(channel_id)
        if demoted:
            lines.append(f"  {demoted}")
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


def _status(signal: Any) -> str:
    if not isinstance(signal, dict):
        return "absent"
    status = str(signal.get("status") or "")
    if status:
        return status
    return "ok" if signal.get("active") else "inactive"


def diff_runs(run_a: int, run_b: int) -> list[str]:
    """`ops signal-diff A B` (#586): per signal, what changed between two recorded runs.

    Status, payload (same / changed, by hash) and the fact lines it fed the prompt -
    all from #386's snapshots, nothing fetched.
    """
    from core.runs.replay import load_snapshot

    a, b = load_snapshot(run_a) or {}, load_snapshot(run_b) or {}
    lines = [f"Signal diff: run {run_a} -> run {run_b} (#586)"]
    for run_id, snap in ((run_a, a), (run_b, b)):
        if not snap:
            lines.append(f"  run {run_id}: no signal snapshot (runs before #386)")
    if not a or not b:
        return lines
    for name in sorted((set(a) | set(b)) - {n for n in set(a) | set(b) if n.startswith("_")}):
        sa, sb = a.get(name), b.get(name)
        before, after = _status(sa), _status(sb)
        parts = [f"{before} -> {after}"] if before != after else []
        ha, hb = _payload_hash(sa), _payload_hash(sb)
        if ha == hb:
            parts.append("same payload" if ha else "no payload")
        else:
            parts.append("payload changed")
            fa = set(_fed_lines(name, sa)) if isinstance(sa, dict) else set()
            fb = set(_fed_lines(name, sb)) if isinstance(sb, dict) else set()
            if fa != fb:
                parts.append(f"fact lines +{len(fb - fa)} / -{len(fa - fb)}")
        lines.append(f"  {name}: " + ", ".join(parts))
    return lines


# #585: the health block reads this on every discovery; the snapshots do not change
# within a session, so it is computed once per channel per process.
HEALTH_MIN_RUNS = 3
HEALTH_RUNS = 20
_fed_cache: dict[str, dict[str, tuple[int, int]]] = {}


def reset_cache() -> None:
    _fed_cache.clear()
    _idle_cache.clear()


def fed_counts(channel_id: str) -> dict[str, tuple[int, int]]:
    """{signal: (fed, runs)} over this channel's last `HEALTH_RUNS` recorded runs."""
    if channel_id not in _fed_cache:
        try:
            rows = contribution_rows(
                load_runs(HEALTH_RUNS, channel_id=channel_id, with_scripts=False)
            )
            _fed_cache[channel_id] = {r["signal"]: (r["fed"], r["runs"]) for r in rows}
        except Exception as exc:
            logger.debug("fed counts unavailable for %s: %s", channel_id, exc)
            _fed_cache[channel_id] = {}
    return _fed_cache[channel_id]


def health_lines(channel_id: str, names: list[str]) -> list[str]:
    """The health block's usefulness line for these signals, or [] while too few runs."""
    counts = fed_counts(channel_id)
    seen = [(n, counts[n]) for n in names if n in counts and counts[n][1] >= HEALTH_MIN_RUNS]
    if not seen:
        return []
    total = max(runs for _n, (_fed, runs) in seen)
    fed = sorted(((n, f, r) for n, (f, r) in seen if f), key=lambda x: (-x[1] / x[2], x[0]))
    never = sorted(n for n, (f, _r) in seen if not f)
    parts = [", ".join(f"{n} {f}/{r}" for n, f, r in fed)] if fed else []
    if never:
        parts.append("never: " + ", ".join(f"{n} 0/{counts[n][1]}" for n in never))
    out = [f"Fed the script (last {total} runs): " + " · ".join(p for p in parts if p)]
    demoted = demotion_line(channel_id)
    if demoted:
        out.append(demoted)
    return out


# ---- #1073: a signal that feeds nothing runs less often (operator, 2026-10-10) ------------
#
# "Feeds nothing" is measured, not listed: on `DEMOTE_MIN_RUNS` or more of the channel's last
# `HEALTH_RUNS` recorded runs the signal was never active and never put a line in the prompt.
# Never active also means it never moved the topic score (the composite reads active signals
# only), so no scoring signal can be caught by this. Such a signal is left out of two runs in
# three; on the third it runs, and the moment it is active once the demotion is over. Nothing
# is switched off, and no breaker or budget is involved - it is a skip, like `--skip`.

DEMOTE_MIN_RUNS = 5
DEMOTE_EVERY = 3
_idle_cache: dict[str, tuple[int, dict[str, int]]] = {}


def demotion_enabled() -> bool:
    return os.getenv("SIGNAL_DEMOTION", "true").strip().lower() not in ("0", "false", "no", "off")


def _latest_run_id() -> int:
    from core import run_trace

    newest = 0
    for path in glob.glob(os.path.join(run_trace.TRACES_DIR, "*.signals.json")):
        stem = os.path.basename(path).split(".", 1)[0]
        if stem.isdigit():
            newest = max(newest, int(stem))
    return newest


def idle_from_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    """{signal: runs} for the signals that ran enough and were never active and never fed."""
    return {
        str(r["signal"]): int(r["runs"])
        for r in rows
        if int(r["runs"]) >= DEMOTE_MIN_RUNS and not r["fed"] and not r["active"]
    }


def idle_signals(channel_id: str) -> dict[str, int]:
    """The channel's idle signals, recomputed when a new run has been recorded."""
    latest = _latest_run_id()
    cached = _idle_cache.get(channel_id)
    if cached is None or cached[0] != latest:
        try:
            rows = contribution_rows(
                load_runs(HEALTH_RUNS, channel_id=channel_id, with_scripts=False)
            )
            cached = (latest, idle_from_rows(rows))
        except Exception as exc:
            logger.debug("idle signals unavailable for %s: %s", channel_id, exc)
            cached = (latest, {})
        _idle_cache[channel_id] = cached
    return cached[1]


def full_turn(next_run: int) -> bool:
    """Every `DEMOTE_EVERY`-th run asks every signal, idle or not."""
    return next_run % DEMOTE_EVERY == 0


def demoted_now(channel_id: str, *, next_run: int | None = None) -> set[str]:
    """The idle signals to leave out of the run about to start; empty on a full turn."""
    if not demotion_enabled():
        return set()
    idle = idle_signals(channel_id)
    if not idle:
        return set()
    turn = next_run if next_run is not None else _latest_run_id() + 1
    return set() if full_turn(turn) else set(idle)


def demotion_line(channel_id: str) -> str:
    """One line for `ops signal-audit` and the health screen, or ""."""
    if not demotion_enabled():
        return ""
    idle = idle_signals(channel_id)
    if not idle:
        return ""
    names = ", ".join(f"{name} 0/{runs}" for name, runs in sorted(idle.items()))
    return (
        f"Running 1 run in {DEMOTE_EVERY} until they feed a script (#1073): {names}"
        "  [SIGNAL_DEMOTION=false runs them every time]"
    )


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


process_state.register_reset("core.runs.signal_audit", reset_cache)
