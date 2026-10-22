"""Data-quality monitor (Pillar 1 — was Phase V).

Cheap validators over what the run ledger already captures — no new network
calls. Two families of checks:

- **Signal health across recent traces** (data/traces/): per-signal failure
  rate, the *current consecutive not-ok streak* (a signal silently dead for
  the last N runs), and signals that returned inactive/empty every time.
- **Join integrity**: rendered/published runs missing `quality_json` or
  `features_json`, and uploaded videos with no metrics yet (the run↔metrics
  join the learning loop depends on).

Read-only + fail-open; surfaced in `ops reliability` and standalone via
`py -m core.data_quality`. Thresholds warn — they never block anything.
"""

from __future__ import annotations

import json
from typing import Any

from core.logging import get_logger

logger = get_logger("core.data_quality")

# Statuses that mean "the signal did not deliver data" (inactive is a normal
# no-data outcome, not a failure; skipped/gated signals never appear in traces).
_FAIL_STATUSES = {
    "no_key",
    "quota_exceeded",
    "rate_limited",
    "auth_error",
    "upstream_error",
    "http_error",
    "unavailable",
    "error",
}

# A signal not-ok in this many consecutive most-recent runs is flagged stale.
STREAK_THRESHOLD = 3


def _signal_checks(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Failure rates + current not-ok streaks per signal, newest trace first."""
    rates: dict[str, dict[str, int]] = {}
    streaks: dict[str, int] = {}
    streak_open: dict[str, bool] = {}
    newest_failed: dict[str, Any] = {}
    # #1220: a signal that has not run in the newest few traces is not failing now. "anime" was
    # flagged for weeks from four game runs (136, 137, 146, 147) after #1170 kept it off games.
    ran_lately = {
        name
        for trace in traces[:STREAK_THRESHOLD]
        for name in (trace.get("signals") or {})
        if isinstance(trace.get("signals"), dict)
    }
    for trace in traces:  # traces come newest-first
        for name, sig in (trace.get("signals") or {}).items():
            if not isinstance(sig, dict):
                continue
            status = str(sig.get("status") or "")
            bucket = rates.setdefault(name, {"failed": 0, "seen": 0})
            bucket["seen"] += 1
            failed = status in _FAIL_STATUSES
            if failed:
                bucket["failed"] += 1
                newest_failed.setdefault(name, trace.get("run_id"))
            # Streak counts only while every newest trace so far failed.
            if streak_open.get(name, True):
                if failed:
                    streaks[name] = streaks.get(name, 0) + 1
                else:
                    streak_open[name] = False
    flagged_streaks = {
        name: count
        for name, count in streaks.items()
        if count >= STREAK_THRESHOLD and name in ran_lately
    }
    flagged_rates = {
        name: b
        for name, b in rates.items()
        if b["seen"] >= 3 and (b["failed"] / b["seen"]) >= 0.5 and name in ran_lately
    }
    return {
        "streaks": flagged_streaks,
        "high_failure": flagged_rates,
        "newest_failed": {
            name: newest_failed.get(name) for name in (*flagged_streaks, *flagged_rates)
        },
    }


def _join_checks(channel_id: str | None, limit: int = 25) -> dict[str, Any]:
    """Run↔quality/features/metrics join assertions over recent runs."""
    out: dict[str, Any] = {
        "runs_checked": 0,
        "missing_quality": 0,
        "missing_features": 0,
        "uploads_without_metrics": 0,
        # #1474 / #1395 (wave 120): the runs and videos behind each count
        "missing_quality_runs": [],
        "missing_features_runs": [],
        "public_without_run": [],
    }
    try:
        from config.channels import resolve_channel_id
        from storage.repositories.content_runs import get_content_run_repository

        channel = resolve_channel_id(channel_id)
        runs = get_content_run_repository().list_for_channel(channel)[:limit]
        for run in runs:
            if run.status not in ("drafted", "rendered"):
                continue
            out["runs_checked"] += 1
            for field, key in (
                ("quality_json", "missing_quality"),
                ("features_json", "missing_features"),
            ):
                try:
                    empty = not json.loads(getattr(run, field, None) or "{}")
                except Exception:
                    empty = True
                if empty:
                    out[key] += 1
                    out[f"{key}_runs"].append(int(run.id))
        from storage.repositories.publish_log import get_publish_log_repository

        for row in get_publish_log_repository().list_uploaded_for_channel(channel):
            try:
                metrics = json.loads(row.metrics_json or "{}")
            except Exception:
                metrics = {}
            if not metrics:
                out["uploads_without_metrics"] += 1
            if str(getattr(row, "privacy_status", "") or "").lower() == "public" and not getattr(
                row, "content_run_id", None
            ):
                out["public_without_run"].append(str(row.youtube_video_id))
    except Exception as exc:
        logger.debug("resolve_channel_id skipped: %s", exc)
    return out


def gather(channel_id: str | None = None, *, trace_limit: int = 20) -> dict[str, Any]:
    """Full data-quality snapshot (read-only, fail-open)."""
    try:
        from core.run_trace import list_traces

        traces = list_traces(limit=trace_limit)
    except Exception:
        traces = []
    return {
        "traces_seen": len(traces),
        "signals": _signal_checks(traces),
        "joins": _join_checks(channel_id),
    }


def warnings(data: dict[str, Any] | None = None, *, channel_id: str | None = None) -> list[str]:
    """The snapshot reduced to operator-facing warning lines ([] = healthy)."""
    data = data or gather(channel_id)
    out: list[str] = []
    sig = data.get("signals") or {}
    newest = sig.get("newest_failed") or {}
    for name, streak in sorted((sig.get("streaks") or {}).items()):
        run = newest.get(name)
        out.append(
            f"signal '{name}' not-ok in the last {streak} runs"
            + (f" (newest run {run})" if run else "")
        )
    for name, bucket in sorted((sig.get("high_failure") or {}).items()):
        if name in (sig.get("streaks") or {}):
            continue
        out.append(f"signal '{name}' failed {bucket['failed']}/{bucket['seen']} recent runs")
    joins = data.get("joins") or {}
    if joins.get("missing_quality"):
        out.append(
            f"{joins['missing_quality']}/{joins.get('runs_checked', 0)} recent runs "
            f"missing quality_json{_named(joins.get('missing_quality_runs'))} - pre-ledger or "
            "scoring failed"
        )
    if joins.get("missing_features"):
        out.append(
            f"{joins['missing_features']}/{joins.get('runs_checked', 0)} recent runs "
            f"missing features_json{_named(joins.get('missing_features_runs'))} - run "
            "backfill-features"
        )
    lost = joins.get("public_without_run") or []
    if lost:  # #1395: the learning reads runs; a public video with none is invisible to it
        shown = ", ".join(lost[:3]) + (f" and {len(lost) - 3} more" if len(lost) > 3 else "")
        out.append(
            f"{len(lost)} public video(s) have no run id ({shown}) - the learning cannot see them"
        )
    if joins.get("uploads_without_metrics"):
        out.append(
            f"{joins['uploads_without_metrics']} uploaded video(s) with no metrics yet "
            "(run sync-metrics)"
        )
    # Dead/stale research feeds starve the grounding corpus. Read from the last
    # persisted `ops feeds` run — no network here, the dashboard must stay fast.
    try:
        from core.feed_health import cached_warnings

        out.extend(cached_warnings())
    except Exception as exc:
        logger.debug("cached_warnings skipped: %s", exc)
    return out


def render(channel_id: str | None = None) -> str:
    data = gather(channel_id)
    lines = ["Data quality", "=" * 40]
    lines.append(f"Traces inspected: {data.get('traces_seen', 0)}")
    warn = warnings(data, channel_id=channel_id)
    if warn:
        # ASCII marker: cp1252 consoles (plain `py -m`) can't encode '⚠'.
        lines.extend(f"  ! {w}" for w in warn)
    else:
        lines.append("  no issues detected")
    return "\n".join(lines)


def main() -> int:
    print(render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def _named(run_ids: list[int] | None) -> str:
    """ " (run 171)" / " (runs 171, 165)" - #1474: the warning said how many, never which."""
    ids = list(run_ids or [])
    if not ids:
        return ""
    noun = "run" if len(ids) == 1 else "runs"
    return f" ({noun} {', '.join(str(i) for i in ids[:3])}{' ...' if len(ids) > 3 else ''})"
