"""Nightly drafts through Windows Task Scheduler (2026-09-16).

The operator wants drafts waiting every morning for `ops batch-review`. `ops overnight`
already makes them with no voice cost, honours the tray's pause flag and the quota gate, and
prints the weekly-target line (#764). This only schedules it:

    py -m scripts.ops schedule-drafts                     # is it installed?
    py -m scripts.ops schedule-drafts --install --channel tapin
    py -m scripts.ops schedule-drafts --remove

Installing changes the operator's Windows scheduler, so nothing here runs `--install` on its
own - the operator does.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta
from typing import Any

from core.logging import get_logger

logger = get_logger("core.nightly_task")

TASK_NAME = r"ContentMachine\OvernightDrafts"
DEFAULT_TIME = "05:00"
DEFAULT_COUNT = 3
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def task_command(
    channel_id: str,
    *,
    count: int = DEFAULT_COUNT,
    python: str | None = None,
    repo: str | None = None,
) -> str:
    """What the scheduler runs: `ops overnight` from the repo, so `.env` and `data/` resolve."""
    return (
        f'cmd /c cd /d "{repo or REPO_ROOT}" && "{python or sys.executable}" '
        f"-m scripts.ops overnight --channel {channel_id} --count {int(count)}"
    )


def install_argv(
    channel_id: str,
    *,
    at: str = DEFAULT_TIME,
    count: int = DEFAULT_COUNT,
    python: str | None = None,
    repo: str | None = None,
) -> list[str]:
    return [
        "schtasks",
        "/Create",
        "/SC",
        "DAILY",
        "/ST",
        at,
        "/TN",
        TASK_NAME,
        "/TR",
        task_command(channel_id, count=count, python=python, repo=repo),
        "/F",
    ]


def remove_argv() -> list[str]:
    return ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"]


def query_argv() -> list[str]:
    return ["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST"]


def query_verbose_argv() -> list[str]:
    return [*query_argv(), "/V"]


_WHEN_FORMATS = (
    "%m/%d/%Y %I:%M:%S %p",
    "%m/%d/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
)
_CLOCK_FORMATS = ("%I:%M:%S %p", "%H:%M:%S", "%I:%M %p", "%H:%M")


def _when(raw: str) -> datetime | None:
    for fmt in _WHEN_FORMATS:
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


def task_times(text: str) -> dict[str, Any]:
    """{last, next, start} from `schtasks /Query /V` - two datetimes and the daily (hour,
    minute) - each None when it cannot be read."""
    out: dict[str, Any] = {"last": None, "next": None, "start": None}
    for line in (text or "").splitlines():
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "last run time":
            out["last"] = _when(value)
        elif key == "next run time":
            out["next"] = _when(value)
        elif key == "start time" and out["start"] is None:
            for fmt in _CLOCK_FORMATS:
                try:
                    clock = datetime.strptime(value, fmt)
                except ValueError:
                    continue
                out["start"] = (clock.hour, clock.minute)
                break
    return out


def _clock(when: datetime) -> str:
    return when.strftime("%I:%M %p").lstrip("0")


def missed_line(times: dict[str, Any], *, now: datetime) -> str:
    """What the operator should know about the last run, or "" when it ran on time (#1167).

    The task is set for 5:00 AM. On 2026-10-13 it ran at 4:45 PM and on 10-14 it did not run:
    Task Scheduler waits for the PC to be awake. Nothing said so, and the morning's drafts and
    renders were simply not there.
    """
    last, start = times.get("last"), times.get("start")
    if last is None or start is None:
        return ""
    due = now.replace(hour=start[0], minute=start[1], second=0, microsecond=0)
    if due > now:
        due -= timedelta(days=1)
    fix = "py -m scripts.ops schedule-drafts --wake"
    if last < due - timedelta(minutes=5):
        return (
            f"Overnight did not run at {_clock(due)} on {due:%b %d} - it last ran "
            f"{last:%b %d} {_clock(last)}. The PC was off or asleep then: {fix}"
        )
    late = (last - due).total_seconds() / 3600
    if late >= 1:
        return (
            f"Overnight ran at {_clock(last)} on {last:%b %d}, {round(late)} hours after its "
            f"{_clock(due)} start - the PC was asleep at {_clock(due)}: {fix}"
        )
    return ""


def overnight_timing_line(*, now: datetime | None = None) -> str:
    """`missed_line` for the installed task. `NIGHTLY_TASK_QUERY=false` (the suite) skips it."""
    if os.getenv("NIGHTLY_TASK_QUERY", "true").strip().lower() in ("0", "false", "no", "off"):
        return ""
    code, out = run_schtasks(query_verbose_argv())
    if code != 0 or not out:
        return ""
    return missed_line(task_times(out), now=now or datetime.now())


def wake_lines() -> list[str]:
    """`schedule-drafts --wake`: the line that lets the task wake the PC. Printed, not run -
    it changes the operator's scheduled task."""
    folder, _, name = TASK_NAME.rpartition(chr(92))
    task_path = chr(92) + folder + chr(92)
    return [
        "Let the overnight task wake the PC - run this once in PowerShell:",
        f"  $t = Get-ScheduledTask -TaskPath '{task_path}' -TaskName '{name}'; "
        "$t.Settings.WakeToRun = $true; Set-ScheduledTask -InputObject $t",
        "Windows also needs wake timers on: Power Options > Change plan settings > Change "
        "advanced power settings > Sleep > Allow wake timers > Enable.",
    ]


def run_schtasks(argv: list[str]) -> tuple[int, str]:
    """(exit code, output). Never raises - a missing schtasks is a message, not a crash."""
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        return 127, "schtasks not found (Windows Task Scheduler is Windows-only)"
    except Exception as exc:
        logger.debug("schtasks failed: %s", exc)
        return 1, f"schtasks failed: {exc}"
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


# ---- #1130: queued uploads go out without a second window left running --------------------
#
# Every queue path ends "Run the worker: py -m jobs.worker --loop 30". Nothing starts it, so a
# video queued for 9:30 pm on 2026-10-10 was still pending the next morning. This schedules one
# worker pass every few minutes. Installing changes the operator's Windows scheduler, so - like
# the drafts task above - nothing here runs `--install` on its own.

WORKER_TASK = r"ContentMachine\UploadWorker"
WORKER_EVERY_MINUTES = 15
WORKER_SCRIPT = os.path.join("scripts", "worker_task.pyw")


def _windowless(python: str | None = None) -> str:
    """`pythonw.exe` beside the interpreter, so no console window opens every few minutes."""
    exe = python or sys.executable
    candidate = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return candidate if os.path.isfile(candidate) else exe


def worker_command(*, python: str | None = None, repo: str | None = None) -> str:
    """What the scheduler runs: the launcher that sets the folder and logs to a file."""
    return f'"{_windowless(python)}" "{os.path.join(repo or REPO_ROOT, WORKER_SCRIPT)}"'


def worker_install_argv(
    *, every: int = WORKER_EVERY_MINUTES, python: str | None = None, repo: str | None = None
) -> list[str]:
    return [
        "schtasks",
        "/Create",
        "/SC",
        "MINUTE",
        "/MO",
        str(max(1, int(every))),
        "/TN",
        WORKER_TASK,
        "/TR",
        worker_command(python=python, repo=repo),
        "/F",
    ]


def worker_remove_argv() -> list[str]:
    return ["schtasks", "/Delete", "/TN", WORKER_TASK, "/F"]


def worker_query_argv() -> list[str]:
    return ["schtasks", "/Query", "/TN", WORKER_TASK, "/FO", "LIST"]


def worker_installed() -> bool:
    code, _out = run_schtasks(worker_query_argv())
    return code == 0


def worker_doctor(channel_id: str) -> tuple[bool, str]:
    """(ok, line) for `ops doctor`: is anything sending uploads, and is one waiting."""
    from core.job_queue import list_active_jobs, overdue_uploads

    late = [j for j in overdue_uploads(list_active_jobs()) if j.channel_id == channel_id]
    installed = worker_installed()
    if late:
        fix = (
            "the task is installed - check data/logs/worker_task.log"
            if installed
            else "py -m scripts.ops worker-task --install"
        )
        return False, f"{len(late)} upload(s) overdue and nothing has sent them - {fix}"
    if installed:
        return True, f"queued uploads are sent every {WORKER_EVERY_MINUTES} minutes"
    return True, (
        "nothing sends queued uploads unless a worker window is open "
        "(py -m scripts.ops worker-task --install)"
    )
