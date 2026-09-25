"""Script-lever A/B experiments — lifecycle, arm assignment, and attribution.

Wires the experimentation harness (core/experiment_levers.py arms +
core/experiment_stats.py Bayesian winner detection) into the pipeline. One
lever runs per channel at a time (e.g. `hook_style`); each generated draft
gets the least-used arm (round-robin by assignment count), the arm's prompt
directive shapes the script, and the assignment is remembered in
data/experiments.json. Once published videos accumulate engagement, the
report joins assignments to realized engaged-rates and calls the low-n-safe
Bayesian evaluator — "collecting" / "no clear winner" / "winner", never a
false positive from 3 videos.

Primary feeder: batch generation (`ops batch-drafts`) — unattended volume
with exactly one varied lever. Lifecycle CLI:

    py -m core.experiments status --channel tapin
    py -m core.experiments start hook_style --channel tapin
    py -m core.experiments stop --channel tapin

Storage is a small JSON sidecar (atomic write, fail-open) — no schema change.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import threading
import time
from typing import Any

from core import experiment_levers, experiment_stats
from core.logging import get_logger

logger = get_logger("core.experiments")

_lock = threading.RLock()


def _load() -> dict[str, Any]:
    from config.paths import EXPERIMENTS_FILE

    if not os.path.exists(EXPERIMENTS_FILE):
        return {"active": {}, "assignments": []}
    try:
        with open(EXPERIMENTS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"active": {}, "assignments": []}
        data.setdefault("active", {})
        data.setdefault("assignments", [])
        return data
    except Exception as exc:
        logger.debug("experiments read failed: %s", exc)
        return {"active": {}, "assignments": []}


def _save(data: dict[str, Any]) -> None:
    from config.paths import EXPERIMENTS_FILE, ensure_data_dir

    try:
        ensure_data_dir()
        directory = os.path.dirname(EXPERIMENTS_FILE) or "."
        fd, tmp = tempfile.mkstemp(suffix=".tmp", prefix="experiments_", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            os.replace(tmp, EXPERIMENTS_FILE)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception as exc:
        logger.debug("experiments write skipped: %s", exc)


def _measured_n(channel_id: str) -> int:
    """Published videos with an engaged-rate — the cadence n for MDE."""
    try:
        from core.engagement_predictor import run_engagement_map

        return len(run_engagement_map(channel_id))
    except Exception as exc:
        logger.debug("experiment MDE n skipped: %s", exc)
        return 0


def start_experiment(channel_id: str, lever: str) -> dict[str, Any]:
    """Activate `lever` for the channel (replaces any running experiment)."""
    if not experiment_levers.known(lever):
        raise ValueError(
            f"Unknown lever '{lever}' — known: {', '.join(experiment_levers.levers())}"
        )
    n_arms = len(experiment_levers.arms(lever))
    n = _measured_n(channel_id)
    # n=0 stays permissive on purpose: experiments GENERATE the samples, so a new
    # channel must be able to bootstrap one. n>0 means we have measurement history
    # and it says the lever cannot resolve. Caveat: `_measured_n` also returns 0
    # from its except branch, so a repository error reads as "new channel" here.
    if n > 0 and n < n_arms:
        raise ValueError(
            f"Cannot start {lever} ({n_arms} arms) with n={n} measured videos; "
            f"need at least {n_arms}"
        )
    record = {"lever": lever, "started_at": time.time()}
    with _lock:
        data = _load()
        data["active"][channel_id] = record
        _save(data)
    logger.info("Experiment started: %s on channel %s", lever, channel_id)
    return record


def stop_experiment(channel_id: str) -> None:
    with _lock:
        data = _load()
        if data["active"].pop(channel_id, None) is not None:
            _save(data)


def active_experiment(channel_id: str) -> dict[str, Any] | None:
    with _lock:
        rec = _load()["active"].get(channel_id)
    return rec if isinstance(rec, dict) and rec.get("lever") else None


def _assignments(channel_id: str, lever: str) -> list[dict[str, Any]]:
    with _lock:
        rows = _load()["assignments"]
    return [
        a
        for a in rows
        if isinstance(a, dict) and a.get("channel_id") == channel_id and a.get("lever") == lever
    ]


def next_arm(channel_id: str, kind: str | None = None) -> tuple[str, str, str] | None:
    """(lever, arm, prompt_directive) for the next draft, or None when no
    experiment is active. Least-assigned arm first (round-robin at parity).

    kind: filter to "script" or "thumbnail" levers — a consumer only receives
    directives it knows where to apply (script prompt vs Flux prompt)."""
    active = active_experiment(channel_id)
    if not active:
        return None
    lever = str(active["lever"])
    if kind is not None and experiment_levers.kind(lever) != kind:
        return None
    arms = experiment_levers.arms(lever)
    if not arms:
        return None
    counts = {arm: 0 for arm in arms}
    for a in _assignments(channel_id, lever):
        if a.get("arm") in counts:
            counts[a["arm"]] += 1
    arm = min(arms, key=lambda a: counts[a])  # ties resolve in declared order
    return lever, arm, experiment_levers.directive(lever, arm)


def assignment_for_run(run_id: int | None) -> dict[str, Any] | None:
    """The {lever, arm} that shaped a run, if any (read path for trace/dossier)."""
    if not run_id:
        return None
    with _lock:
        rows = _load()["assignments"]
    for a in rows:
        if isinstance(a, dict) and a.get("run_id") == int(run_id):
            return {"lever": str(a.get("lever", "")), "arm": str(a.get("arm", ""))}
    return None


def record_assignment(channel_id: str, run_id: int | None, lever: str, arm: str) -> None:
    """Remember which arm shaped a generated run (skips runs without an id)."""
    if not run_id:
        return
    with _lock:
        data = _load()
        data["assignments"].append(
            {
                "channel_id": channel_id,
                "run_id": int(run_id),
                "lever": lever,
                "arm": arm,
                "at": time.time(),
            }
        )
        _save(data)


def _run_engagement(channel_id: str) -> dict[int, float]:
    """run_id -> realized engaged_rate for published runs (same join as
    core/title_experiments)."""
    try:
        from core.engagement import engaged_rate
        from storage.repositories.publish_log import get_publish_log_repository

        logs = get_publish_log_repository().list_timed_outcomes(channel_id)
    except Exception as exc:
        logger.debug("experiments engagement load failed: %s", exc)
        return {}
    out: dict[int, float] = {}
    for log in logs:
        rate = engaged_rate(log.metrics_json)
        if rate is not None and log.content_run_id:
            out[int(log.content_run_id)] = float(rate)
    return out


def arm_outcomes(channel_id: str, lever: str) -> dict[str, list[float]]:
    """arm -> engaged-rates of its published, measured runs."""
    engagement = _run_engagement(channel_id)
    out: dict[str, list[float]] = {arm: [] for arm in experiment_levers.arms(lever)}
    for a in _assignments(channel_id, lever):
        rate = engagement.get(int(a.get("run_id") or 0))
        if rate is not None and a.get("arm") in out:
            out[a["arm"]].append(rate)
    return out


def experiment_report(channel_id: str) -> dict[str, Any]:
    """Active experiment + assignment counts + Bayesian evaluation."""
    active = active_experiment(channel_id)
    if not active:
        return {"active": None}
    lever = str(active["lever"])
    assigned = _assignments(channel_id, lever)
    counts: dict[str, int] = {arm: 0 for arm in experiment_levers.arms(lever)}
    for a in assigned:
        if a.get("arm") in counts:
            counts[a["arm"]] += 1
    return {
        "active": active,
        "lever": lever,
        "assigned": counts,
        "evaluation": experiment_stats.evaluate(arm_outcomes(channel_id, lever)),
    }


def display_report(channel_id: str, *, print_fn=print) -> None:
    report = experiment_report(channel_id)
    if not report.get("active"):
        levers = ", ".join(experiment_levers.levers())
        print_fn(f"  No experiment running. Start one: py -m core.experiments start <{levers}>")
        return
    lever = report["lever"]
    ev = report["evaluation"]
    print_fn(f"  Experiment: {lever} (status: {ev['status']})")
    for arm, count in report["assigned"].items():
        d = ev["arms"].get(arm) or {}
        measured = d.get("n", 0)
        line = f"    {arm:<16} assigned {count:>2}, measured {measured:>2}"
        if measured:
            line += f", avg {d['rate']:.0%}, P(best) {d['p_best']:.0%}"
        print_fn(line)
    if ev.get("winner"):
        print_fn(f"  Winner: {ev['winner']} — consider making it the default and stopping.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Script-lever A/B experiments")
    parser.add_argument("action", choices=["status", "start", "stop"])
    parser.add_argument("lever", nargs="?", help="Lever name (for start)")
    parser.add_argument("--channel", default="tapin")
    args = parser.parse_args(argv)

    if args.action == "start":
        if not args.lever:
            print(f"Lever required. Known: {', '.join(experiment_levers.levers())}")
            return 1
        try:
            start_experiment(args.channel, args.lever)
        except ValueError as exc:
            print(str(exc))
            return 1
        print(f"Started '{args.lever}' on {args.channel}. Feed it: py -m scripts.ops batch-drafts")
        return 0
    if args.action == "stop":
        stop_experiment(args.channel)
        print("Experiment stopped (assignments kept for the report).")
        return 0
    display_report(args.channel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
