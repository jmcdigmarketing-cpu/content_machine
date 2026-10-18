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

import json
import os
import re
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
    """{last, next, start, result, count, channel} from `schtasks /Query /V` - two datetimes,
    the daily (hour, minute), the last run's exit code (#1216) and what the task runs - each
    None (channel "") when it cannot be read."""
    out: dict[str, Any] = {
        "last": None,
        "next": None,
        "start": None,
        "result": None,
        "count": None,
        "channel": "",
    }
    for line in (text or "").splitlines():
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "last run time":
            out["last"] = _when(value)
        elif key == "next run time":
            out["next"] = _when(value)
        elif key == "last result":
            try:
                out["result"] = int(value, 0)
            except ValueError:
                out["result"] = None
        elif key == "task to run":
            count = re.search(r"--count\s+(\d+)", value)
            channel = re.search(r"--channel\s+([A-Za-z0-9_-]+)", value)
            out["count"] = int(count.group(1)) if count else None
            out["channel"] = channel.group(1) if channel else ""
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


def missed_line(times: dict[str, Any], *, now: datetime, wakes: bool | None = None) -> str:
    """What the operator should know about the last run, or "" when it ran on time (#1167).

    The task is set for 5:00 AM. On 2026-10-13 it ran at 4:45 PM and on 10-14 it did not run:
    Task Scheduler waits for the PC to be awake. Nothing said so, and the morning's drafts and
    renders were simply not there. #1289: ``wakes`` (the task's WakeToRun) names the cause - on
    2026-10-18 the operator had turned wake timers on and the task itself was still not allowed
    to wake the PC.
    """
    last, start = times.get("last"), times.get("start")
    if last is None or start is None:
        return ""
    due = now.replace(hour=start[0], minute=start[1], second=0, microsecond=0)
    if due > now:
        due -= timedelta(days=1)
    fix = "py -m scripts.ops schedule-drafts --wake"
    if wakes is False:
        why = f"the PC was asleep, and the task is not allowed to wake the PC: {fix}"
    elif wakes is True:
        why = (
            "the task may wake the PC and it did not wake - it was shut down, or wake timers "
            "are off (Power Options > Sleep > Allow wake timers): py -m scripts.ops schedule-drafts"
        )
    else:
        why = f"the PC was off or asleep then: {fix}"
    if last < due - timedelta(minutes=5):
        return (
            f"Overnight did not run at {_clock(due)} on {due:%b %d} - it last ran "
            f"{last:%b %d} {_clock(last)}. {why[0].upper()}{why[1:]}"
        )
    late = (last - due).total_seconds() / 3600
    if late >= 1:
        return (
            f"Overnight ran at {_clock(last)} on {last:%b %d}, {round(late)} hours after its "
            f"{_clock(due)} start - {why}"
        )
    return ""


# #1216: what "Last Result" says about a run that did not finish. 2026-10-16: the task woke
# with the PC at 4:30 PM, made one draft of three and died at 4:32 with 0xC0000374 (heap
# corruption in ntdll.dll, no traceback in its log); the morning said "Overnight ran at 4:30 PM".
_QUIET_RESULTS = frozenset({0, 0x41301, 0x41303})  # finished, running now, has not run yet
_RESULT_WORDS = {
    0xC0000374: "Python crashed: heap corruption",
    0xC0000005: "Python crashed: access violation",
    0xC00000FD: "Python crashed: stack overflow",
    0xC000013A: "it was stopped with Ctrl+C",
    0x41306: "it was ended - by hand, or at its 2-hour limit",
}
OVERNIGHT_LOG = os.path.join("output", "logs", "overnight-last.log")


def result_words(code: int) -> str:
    """A task's exit code in words, with the code."""
    unsigned = int(code) & 0xFFFFFFFF
    if unsigned in _RESULT_WORDS:
        return f"{_RESULT_WORDS[unsigned]} (0x{unsigned:08X})"
    if unsigned < 0x10000:
        return f"it stopped on an error (exit {unsigned})"
    return f"it stopped (0x{unsigned:08X})"


def stopped_line(times: dict[str, Any], *, drafts_made: int | None) -> str:
    """What the operator should know when the last run did not finish, else ""."""
    code = times.get("result")
    if code is None or (int(code) & 0xFFFFFFFF) in _QUIET_RESULTS:
        return ""
    last = times.get("last")
    count = int(times.get("count") or DEFAULT_COUNT)
    channel = str(times.get("channel") or "")
    started = f" at {_clock(last)} on {last:%b %d}" if last else ""
    made = f" after {drafts_made} of {count} drafts" if drafts_made is not None else ""
    again = "py -m scripts.ops overnight" + (f" --channel {channel}" if channel else "")
    return (
        f"Overnight started{started} and stopped{made} - {result_words(code)}. "
        f"Its output: {OVERNIGHT_LOG}. Run it again: {again} --count {count}"
    )


def _queried_times() -> dict[str, Any] | None:
    """`task_times` of the installed task. `NIGHTLY_TASK_QUERY=false` (the suite) skips it."""
    if os.getenv("NIGHTLY_TASK_QUERY", "true").strip().lower() in ("0", "false", "no", "off"):
        return None
    code, out = run_schtasks(query_verbose_argv())
    if code != 0 or not out:
        return None
    return task_times(out)


def overnight_timing_line(*, now: datetime | None = None) -> str:
    """`missed_line` for the installed task. `NIGHTLY_TASK_QUERY=false` (the suite) skips it."""
    times = _queried_times()
    if not times:
        return ""
    line = missed_line(times, now=now or datetime.now())
    return missed_line(times, now=now or datetime.now(), wakes=task_wakes()) if line else ""


def overnight_record_path() -> str:
    """Where `ops overnight` notes its start and finish (#1223). `OVERNIGHT_RECORD_FILE`
    moves it - the suite points it at a temp folder."""
    return os.getenv("OVERNIGHT_RECORD_FILE", "").strip() or os.path.join(
        REPO_ROOT, "data", "overnight_last.json"
    )


def record_overnight(
    channel_id: str, *, started: datetime, finished: datetime | None = None, drafts: Any = None
) -> None:
    """#1223: what `ops overnight` did - written at its start and again at its end, so a run that
    finished after the task's crash is known. Never raises."""
    payload = {
        "channel": channel_id,
        "started": started.isoformat(timespec="seconds"),
        "finished": finished.isoformat(timespec="seconds") if finished else "",
        "drafts": drafts,
    }
    try:
        path = overnight_record_path()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except Exception as exc:
        logger.debug("overnight record not written: %s", exc)


def _recorded(key: str) -> datetime | None:
    try:
        with open(overnight_record_path(), encoding="utf-8") as f:
            return datetime.fromisoformat(str(json.load(f).get(key) or ""))
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def _recorded_finish() -> datetime | None:
    return _recorded("finished")


def _recorded_start() -> datetime | None:
    return _recorded("started")


def overnight_stop_line(*, root: str | None = None, log_path: str | None = None) -> str:
    """`stopped_line` for the installed task (#1216). #1223: said only while no later run has
    finished, and the drafts counted from the task's start to the log's last write - on
    2026-10-16 the operator ran overnight by hand after the crash, and the line said "stopped
    after 4 of 3 drafts"."""
    times = _queried_times()
    if not times:
        return ""
    last = times.get("last")
    finished = _recorded_finish()
    if last is not None and finished is not None and finished >= last:
        return ""
    made = None
    if last is not None and times.get("channel"):
        until = None
        try:
            stamp = datetime.fromtimestamp(
                os.path.getmtime(log_path or os.path.join(REPO_ROOT, OVERNIGHT_LOG))
            )
            # A draft is saved a few seconds after its last log line: run 156 at 16:32:23, the
            # log's last write at 16:32:13. A minute of grace, and never into a later run.
            until = stamp + timedelta(minutes=1) if stamp >= last else None
        except OSError:
            until = None
        later = _recorded_start()  # the stopped run's own start is written within seconds
        if later is not None and later > last + timedelta(minutes=1):
            until = min(until, later) if until is not None else later
        try:
            from core.batch_review import drafts_made_since

            made = drafts_made_since(str(times["channel"]), last, until=until, root=root)
        except Exception as exc:
            logger.debug("overnight drafts uncounted: %s", exc)
    return stopped_line(times, drafts_made=made)


def enable_crash_traceback(stream: Any = None) -> bool:
    """#1216: Python's own traceback, every thread, when the process dies in native code. The
    2026-10-16 overnight died with 0xC0000374 and its log ended at a warning. ``stream`` is
    stderr by default - the task already sends stderr to its log. False when there is nowhere
    to write (`pythonw` has no stderr)."""
    import faulthandler

    target = stream if stream is not None else sys.stderr
    if target is None:
        return False
    try:
        target.fileno()
        faulthandler.enable(file=target, all_threads=True)
    except (AttributeError, OSError, ValueError, RuntimeError) as exc:
        logger.debug("crash traceback not enabled: %s", exc)
        return False
    return True


def wake_command() -> str:
    """The PowerShell that sets the task's WakeToRun."""
    folder, _, name = TASK_NAME.rpartition(chr(92))
    task_path = chr(92) + folder + chr(92)
    return (
        f"$t = Get-ScheduledTask -TaskPath '{task_path}' -TaskName '{name}'; "
        "$t.Settings.WakeToRun = $true; Set-ScheduledTask -InputObject $t"
    )


def wake_to_run(xml: str) -> bool | None:
    """#1289: the task's own WakeToRun from `schtasks /Query /XML` - absent means False (the
    2026-10-18 task: wake timers on, and the task still not allowed to wake the PC)."""
    text = xml or ""
    if "<Settings>" not in text and "<Settings " not in text:
        return None
    found = re.search(r"<WakeToRun>\s*(true|false)\s*</WakeToRun>", text, re.IGNORECASE)
    return bool(found) and found.group(1).lower() == "true"


def _query_enabled() -> bool:
    return os.getenv("NIGHTLY_TASK_QUERY", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def task_wakes() -> bool | None:
    """Whether the installed task may wake the PC; None when it cannot be read, or in the
    suite (`NIGHTLY_TASK_QUERY=false`)."""
    if not _query_enabled():
        return None
    code, out = run_schtasks([*query_argv()[:4], "/XML"])
    return wake_to_run(out) if code == 0 else None


_WAKE_INDEX = {0: "off", 1: "on", 2: "important only"}


def parse_wake_timers(text: str) -> dict[str, str]:
    """{ac, dc} from `powercfg /q SCHEME_CURRENT SUB_SLEEP RTCWAKE` - "on", "off" or
    "important only" - {} when it cannot be read."""
    out: dict[str, str] = {}
    for key, raw in re.findall(
        r"Current (AC|DC) Power Setting Index:\s*(0x[0-9a-fA-F]+)", text or ""
    ):
        out[key.lower()] = _WAKE_INDEX.get(int(raw, 16), raw)
    return out


def wake_timers() -> dict[str, str]:
    """The power plan's "Allow wake timers" (no administrator needed to read it)."""
    if not _query_enabled():
        return {}
    try:
        proc = subprocess.run(
            ["powercfg", "/q", "SCHEME_CURRENT", "SUB_SLEEP", "RTCWAKE"],
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
        )
    except Exception as exc:
        logger.debug("powercfg unread: %s", exc)
        return {}
    return parse_wake_timers(proc.stdout or "")


def _powershell(command: str) -> tuple[int, str]:
    if os.environ.get("CONTENT_SUITE") == "1" or not _query_enabled():
        return 1, "the suite never changes the operator's scheduled task"
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return 127, "PowerShell not found (Windows only)"
    except Exception as exc:
        return 1, f"PowerShell failed: {exc}"
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def set_wake() -> tuple[bool, str]:
    """#1289: set the task's WakeToRun and read it back. (True, "") when the task may now wake
    the PC; (False, what PowerShell said) otherwise. The operator runs it - it changes their
    scheduled task."""
    code, out = _powershell(wake_command())
    if task_wakes() is True:
        return True, ""
    return False, out or f"PowerShell exit {code}"


def wake_report(ok: bool, said: str, timers: dict[str, str]) -> list[str]:
    """What `schedule-drafts --wake` prints."""
    lines: list[str] = []
    if ok:
        lines.append(f"Overnight can now wake the PC at {DEFAULT_TIME.lstrip('0')} AM.")
    else:
        lines.append(f"The task could not be changed: {said[-300:]}")
        lines.append("Run this once in PowerShell as administrator:")
        lines.append(f"  {wake_command()}")
    if timers and "off" in timers.values():
        where = " and ".join(k.upper() for k, v in timers.items() if v == "off")
        lines.append(
            f"Wake timers are off on {where} power: Power Options > Change plan settings > "
            "Change advanced power settings > Sleep > Allow wake timers > Enable."
        )
    elif timers:
        lines.append("Wake timers: " + ", ".join(f"{k.upper()} {v}" for k, v in timers.items()))
    lines.append("A PC that is shut down cannot be woken - sleep it instead.")
    return lines


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
