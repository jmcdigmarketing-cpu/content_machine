"""What the upload worker's scheduled task did on its last pass (#1402, wave 115).

`scripts/worker_task.pyw` appends each pass to `config.paths.WORKER_TASK_LOG`; the morning
(`ops status`) reads the last one. Kept apart from `jobs.worker` so reading it does not import the
pipeline.
"""

from __future__ import annotations

import re
from datetime import datetime

_PASS_STALE_HOURS = 2.0  # the task runs every 15 minutes while the PC is on


def summarize_pass(lines: list[str]) -> str:
    """#1402: one pass of the worker in a few words."""
    text = "\n".join(lines)
    sent = sum(1 for ln in lines if re.match(r"^Job \d+ (uploaded|scheduled)", ln.strip()))
    if sent:
        return f"{sent} sent"
    low = text.lower()
    if "the youtube sign-in has ended" in low:  # #1439: held for the sign-in, not failed
        return "uploads held - the YouTube sign-in has ended"
    # "for the quota reset": #1526 (wave 116) - the pass names the uploads it holds.
    if any(k in low for k in ("upload blocked today", "waiting for youtube quota", "quota reset")):
        return "uploads blocked by quota until the reset"
    if "failed" in text.lower():
        return "a job failed - see data/logs/worker_task.log"
    return "nothing waiting"


def _last_pass(path: str) -> tuple[datetime, list[str]] | None:
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            tail = handle.readlines()[-400:]
    except OSError:
        return None
    starts = [i for i, ln in enumerate(tail) if ln.startswith("--- ") and "worker pass" in ln]
    if not starts:
        return None
    head = tail[starts[-1]]
    try:
        when = datetime.fromisoformat(head.split()[1])
    except (IndexError, ValueError):
        return None
    return when, [ln.rstrip("\n") for ln in tail[starts[-1] + 1 :]]


def last_pass_at(path: str) -> datetime | None:
    """When the scheduled worker last ran (wave 117, #1371's gap), or None."""
    found = _last_pass(path)
    return found[0] if found else None


def last_pass_line(path: str, *, now: datetime | None = None) -> str:
    """#1402 (wave 115): "last pass 17:22 - uploads blocked by quota until the reset", from the
    scheduled task's log; it says how long ago when that is over 2 hours. "" without a log."""
    found = _last_pass(path)
    if found is None:
        return ""
    when, body = found
    line = f"last pass {when:%H:%M} - {summarize_pass(body)}"
    age = ((now or datetime.now()) - when).total_seconds() / 3600
    if age > _PASS_STALE_HOURS:
        line += f" ({age:.0f} h ago - the PC was off, or the UploadWorker task is)"
    return line
