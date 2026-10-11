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
