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
