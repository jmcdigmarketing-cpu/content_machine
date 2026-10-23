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
import threading
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


POWER_STATES = {4: "asleep", 5: "hibernated", 6: "shut down"}  # Kernel-Power 42 TargetState
_POWER_QUERY = "*[System[Provider[@Name='Microsoft-Windows-Kernel-Power'] and (EventID=42)]]"


def parse_power_events(xml: str) -> list[tuple[datetime, int]]:
    """(local time, TargetState) of each Kernel-Power 42 event in `wevtutil qe /f:xml` output -
    4 is sleep, 5 hibernate, 6 shutdown (Fast Startup's included)."""
    from datetime import timezone

    out: list[tuple[datetime, int]] = []
    for event in re.findall(r"<Event[ >].*?</Event>", xml or "", re.S):
        stamp = re.search(r"SystemTime='(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)", event)
        state = re.search(r"<Data Name='TargetState'>(\d+)</Data>", event)
        if not stamp or not state:
            continue
        utc = datetime.strptime(stamp.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        out.append((utc.astimezone().replace(tzinfo=None), int(state.group(1))))
    return out


def power_events(count: int = 6) -> list[tuple[datetime, int]]:
    """The newest `count` sleep / hibernate / shutdown events (no administrator needed). [] in
    the suite (`NIGHTLY_TASK_QUERY=false`) or off Windows."""
    if not _query_enabled():
        return []
    try:
        proc = subprocess.run(
            ["wevtutil", "qe", "System", f"/q:{_POWER_QUERY}", f"/c:{int(count)}", "/rd:true",
             "/f:xml"],
            capture_output=True,
            text=True,
            timeout=20,
            stdin=subprocess.DEVNULL,
        )  # fmt: skip
    except Exception as exc:
        logger.debug("power events unread: %s", exc)
        return []
    return parse_power_events(proc.stdout or "") if proc.returncode == 0 else []


def power_off_before(
    due: datetime, events: list[tuple[datetime, int]]
) -> tuple[str, datetime] | None:
    """#1528 (wave 117): how the PC went off last before `due` - ("shut down", when) - or None.
    On 2026-10-19 at 8:49 PM it was shut down, and a shut-down PC cannot wake for the 5:00 task;
    from Sleep it woke on 10-19."""
    prior = [(when, state) for when, state in events if when <= due and state in POWER_STATES]
    if not prior:
        return None
    when, state = max(prior)
    return POWER_STATES[state], when


def _due(times: dict[str, Any], now: datetime) -> datetime | None:
    start = times.get("start")
    if start is None:
        return None
    due = now.replace(hour=start[0], minute=start[1], second=0, microsecond=0)
    return due - timedelta(days=1) if due > now else due


def _off_words(off: tuple[str, datetime]) -> str:
    kind, when = off
    return f"the PC was {kind} {when:%a} {_clock(when)}"


def missed_line(
    times: dict[str, Any],
    *,
    now: datetime,
    wakes: bool | None = None,
    off: tuple[str, datetime] | None = None,
) -> str:
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
    if off is not None and off[0] in ("shut down", "hibernated") and wakes is not False:
        # #1528: the event log says which - it had guessed "shut down, or wake timers are off"
        # with wake timers on.
        kind, when = off
        why = (
            f"the PC was {kind} at {when:%a} {_clock(when)} - a {kind.replace(' ', '-')} PC cannot "
            f"wake; Sleep keeps the {_clock(due)} start"
        )
    elif wakes is False:
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


def late_short(
    times: dict[str, Any], *, now: datetime, off: tuple[str, datetime] | None = None
) -> str:
    """#1380 (wave 117): the morning's words for a late or missed run, "" when it ran on time -
    `ops status` said only "Overnight: last started Tue 16:24" after the 10-19 shutdown."""
    last, due = times.get("last"), _due(times, now)
    if last is None or due is None:
        return ""
    cause = f" - {_off_words(off)} (Sleep keeps the {_clock(due)} start)" if off else ""
    if last < due - timedelta(minutes=5):
        return f"did not run at {_clock(due)} {due:%a}{cause}"
    late = (last - due).total_seconds() / 3600
    if late < 1:
        return ""
    return f"started {last:%a} {_clock(last)}, {round(late)} h after {_clock(due)}{cause}"


def _last_off(times: dict[str, Any], now: datetime) -> tuple[str, datetime] | None:
    due = _due(times, now)
    return power_off_before(due, power_events()) if due is not None else None


def overnight_late_short(*, now: datetime | None = None) -> str:
    """`late_short` for the installed task, with the event log's cause. "" in the suite."""
    times = _queried_times()
    if not times:
        return ""
    moment = now or datetime.now()
    if not late_short(times, now=moment):
        return ""
    return late_short(times, now=moment, off=_last_off(times, moment))


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


_FRAME = re.compile(r'^\s*File "([^"]+)", line (\d+),? in (\S+)\s*$', re.M)
_LIBRARY = re.compile(r"(?:site-packages|dist-packages)/|/lib/(?:python[\d.]*/)?[^/]+\.py$", re.I)


def _is_library(path: str) -> bool:
    return bool(_LIBRARY.search(path.replace("\\", "/")))


def _where(frame: tuple[str, str, str]) -> str:
    """ "C:\\dev\\content_machine\\video\\render.py" -> "video/render.py line 412 in _encode";
    a package's file keeps its package ("PIL/Image.py"), the standard library's its name."""
    path, line, func = frame
    parts = path.replace("\\", "/").split("/")
    stdlib = _is_library(path) and "-packages/" not in "/".join(parts)
    return f"{parts[-1] if stdlib else '/'.join(parts[-2:])} line {line} in {func}"


def crash_frame(text: str) -> str:
    """#1469 (S17): the Python line a crash was at, from what faulthandler (#1216) or a traceback
    left in the log - "video/render.py line 412 in _encode". When the top frame is a library's,
    the project's frame that called it follows. "" when the log has neither."""
    raw = text or ""
    exception = ""
    if "(most recent call first)" in raw:
        at = raw.rfind("Current thread")
        block = raw[at:] if at >= 0 else raw[raw.find("(most recent call first)") :]
        block = block.split("\n\n", 1)[0]
        frames = _FRAME.findall(block)
    elif "Traceback (most recent call last)" in raw:
        block = raw[raw.rfind("Traceback (most recent call last)") :]
        frames = list(reversed(_FRAME.findall(block)))
        tail = [ln for ln in block.splitlines()[1:] if ln.strip() and not ln.startswith(" ")]
        exception = tail[0].strip()[:80] if tail else ""
    else:
        return ""
    if not frames:
        return ""
    where = _where(frames[0])
    if _is_library(frames[0][0]):
        ours = next((f for f in frames[1:] if not _is_library(f[0])), None)
        if ours is not None:
            where += f", called from {_where(ours)}"
    return f"{exception} at {where}" if exception else where


def _crash_text(started: datetime | None, log_path: str) -> str:
    """The log of the run that stopped - the task's own while it is from that run, else the copy
    `keep_crash_log` made."""
    try:
        if started is None or datetime.fromtimestamp(os.path.getmtime(log_path)) >= started:
            with open(log_path, encoding="utf-8", errors="replace") as handle:
                return handle.read()[-200_000:]
    except OSError:
        pass
    if started is None:
        return ""
    kept = os.path.join(REPO_ROOT, CRASH_DIR, f"overnight-{started:%Y%m%d-%H%M}.log")
    try:
        with open(kept, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""


def stopped_line(times: dict[str, Any], *, drafts_made: int | None, crash_at: str = "") -> str:
    """What the operator should know when the last run did not finish, else "". #1469:
    `crash_at` is where the crash was (`crash_frame`)."""
    code = times.get("result")
    if code is None or (int(code) & 0xFFFFFFFF) in _QUIET_RESULTS:
        return ""
    last = times.get("last")
    count = int(times.get("count") or DEFAULT_COUNT)
    channel = str(times.get("channel") or "")
    started = f" at {_clock(last)} on {last:%b %d}" if last else ""
    made = f" after {drafts_made} of {count} drafts" if drafts_made is not None else ""
    again = "py -m scripts.ops overnight" + (f" --channel {channel}" if channel else "")
    where = f" at {crash_at}" if crash_at else ""
    return (
        f"Overnight started{started} and stopped{made} - {result_words(code)}{where}. "
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
    moment = now or datetime.now()
    if not missed_line(times, now=moment):
        return ""
    return missed_line(times, now=moment, wakes=task_wakes(), off=_last_off(times, moment))


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


# #1468 (S17): a beat each minute while overnight runs. A native crash kills the thread with
# the process, so the last beat is the time of death to within a minute - the 10-16 crash was
# known only from Task Scheduler's exit code and the log's last write, and a hand run had neither.
BEAT_SECONDS = 60.0
_BEAT_STALE_MINUTES = 3
_beat_lock = threading.Lock()
_beat_state: dict[str, Any] = {"step": "", "stop": None, "thread": None, "started": None}


def _now() -> datetime:
    return datetime.now()


def beat_enabled() -> bool:
    """`OVERNIGHT_BEAT=false` (the suite) writes no beat."""
    return os.getenv("OVERNIGHT_BEAT", "true").strip().lower() not in ("0", "false", "no", "off")


def beat_path() -> str:
    """`OVERNIGHT_BEAT_FILE`, else data/overnight_beat.json - not `core.human_presence`'s
    heartbeat, which an unattended run must never stamp."""
    return os.getenv("OVERNIGHT_BEAT_FILE", "").strip() or os.path.join(
        REPO_ROOT, "data", "overnight_beat.json"
    )


def beat_step(text: str) -> None:
    """What overnight is doing now - the next beat carries it ("rendering run 175")."""
    _beat_state["step"] = str(text or "")[:80]


def _write_beat() -> None:
    started = _beat_state.get("started")
    payload = {
        "started": started.isoformat(timespec="seconds") if started else "",
        "beat": _now().isoformat(timespec="seconds"),
        "step": _beat_state.get("step") or "",
    }
    try:
        path = beat_path()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        os.replace(tmp, path)
    except OSError as exc:
        logger.debug("overnight beat not written: %s", exc)


def start_beat(started: datetime, *, seconds: float | None = None) -> bool:
    """Write a beat now and every `seconds` until `stop_beat`. False when beats are off."""
    if not beat_enabled():
        return False
    stop_beat()
    interval = BEAT_SECONDS if seconds is None else max(0.001, float(seconds))
    stop = threading.Event()

    def _loop() -> None:
        while not stop.wait(interval):
            _write_beat()

    with _beat_lock:
        _beat_state.update(step="", started=started, stop=stop)
        _write_beat()  # the first beat before the run starts - a crash at once still leaves one
        thread = threading.Thread(target=_loop, name="overnight-beat", daemon=True)
        _beat_state["thread"] = thread
        thread.start()
    return True


def stop_beat() -> None:
    with _beat_lock:
        stop, thread = _beat_state.get("stop"), _beat_state.get("thread")
        _beat_state.update(stop=None, thread=None)
    if stop is not None:
        stop.set()
    if thread is not None:
        thread.join(timeout=5)


def last_beat() -> dict[str, Any] | None:
    try:
        with open(beat_path(), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _stale_beat(now: datetime | None = None) -> tuple[datetime, datetime, str] | None:
    """(started, last beat, step) of a run that stopped beating and never finished, else None."""
    started, finished = _recorded_start(), _recorded_finish()
    beat = last_beat() or {}
    if started is None or (finished is not None and finished >= started):
        return None
    if str(beat.get("started") or "") != started.isoformat(timespec="seconds"):
        return None  # no beat from this run (before #1468, or beats off)
    try:
        last = datetime.fromisoformat(str(beat.get("beat") or ""))
    except ValueError:
        return None
    if ((now or _now()) - last).total_seconds() < _BEAT_STALE_MINUTES * 60:
        return None  # still running
    return started, last, str(beat.get("step") or "")


def _beat_when(last: datetime, step: str) -> str:
    return f"{_clock(last)} on {last:%b %d}" + (f", {step}" if step else "")


def beat_gap_line(*, now: datetime | None = None) -> str:
    """#1468: "" while overnight is beating or finished, else its last sign of life - "Overnight's
    last sign of life was 4:32 AM on Oct 16, rendering run 175 (started 4:30 AM) - it never
    finished". Needs no Task Scheduler, so a hand run is covered."""
    gap = _stale_beat(now)
    if gap is None:
        return ""
    started, last, step = gap
    return (
        f"Overnight's last sign of life was {_beat_when(last, step)} "
        f"(started {_clock(started)}) - it never finished"
    )


def _recorded(key: str) -> datetime | None:
    try:
        with open(overnight_record_path(), encoding="utf-8") as f:
            return datetime.fromisoformat(str(json.load(f).get(key) or ""))
    except (OSError, ValueError, TypeError, AttributeError):
        return None


OVERDUE_HOURS = 26.0


def overdue_line(*, now: datetime | None = None) -> str:
    """#1372 (wave 115): "" while overnight has started in the last 26 hours, else what to say -
    a missed run was found only when someone looked."""
    started = _recorded_start()
    if started is None:
        return ""
    hours = ((now or datetime.now()) - started).total_seconds() / 3600
    if hours < OVERDUE_HOURS:
        return ""
    return (f"Overnight has not run for {hours:.0f} hours (last started {started:%a %H:%M}) - "
            "was the PC off at 5:00? py -m scripts.ops overnight-last")  # fmt: skip


def _recorded_finish() -> datetime | None:
    return _recorded("finished")


CRASH_DIR = os.path.join("output", "logs", "crashes")
_UNFINISHED_HOURS = 3.0  # the task's limit is 2 hours
_CRASH_LINES = 200


def keep_crash_log(
    *, now: datetime | None = None, log_path: str | None = None, crash_dir: str | None = None
) -> str:
    """#1466 (wave 119): the last 200 lines of a run that started and never finished, kept in
    output/logs/crashes - the task's `> overnight-last.log` empties the file at the next 5:00
    before Python runs, so the 10-16 crash's evidence was gone by morning. Called from each
    worker pass; once per run; "" when there is nothing to keep."""
    started, finished = _recorded_start(), _recorded_finish()
    if started is None or (finished is not None and finished >= started):
        return ""
    if ((now or datetime.now()) - started).total_seconds() < _UNFINISHED_HOURS * 3600:
        return ""  # it may still be running
    src = log_path or os.path.join(REPO_ROOT, OVERNIGHT_LOG)
    try:
        if datetime.fromtimestamp(os.path.getmtime(src)) < started:
            return ""  # the log is from before this run
        folder = crash_dir or os.path.join(REPO_ROOT, CRASH_DIR)
        dest = os.path.join(folder, f"overnight-{started:%Y%m%d-%H%M}.log")
        if os.path.exists(dest):
            return ""
        with open(src, encoding="utf-8", errors="replace") as handle:
            tail = handle.read().splitlines()[-_CRASH_LINES:]
        os.makedirs(folder, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as handle:
            handle.write("\n".join(tail) + "\n")
        return dest
    except OSError as exc:
        logger.debug("crash log not kept: %s", exc)
        return ""


def crash_count(*, days: int = 7, now: datetime | None = None, crash_dir: str | None = None) -> int:
    """#1463 (wave 119): overnight runs that never finished, in the last `days` - from the logs
    `keep_crash_log` kept."""
    folder = crash_dir or os.path.join(REPO_ROOT, CRASH_DIR)
    cutoff = (now or datetime.now()) - timedelta(days=days)
    count = 0
    try:
        names = os.listdir(folder)
    except OSError:
        return 0
    for name in names:
        found = re.fullmatch(r"overnight-(\d{8}-\d{4})\.log", name)
        if found and datetime.strptime(found.group(1), "%Y%m%d-%H%M") >= cutoff:
            count += 1
    return count


def _recorded_start() -> datetime | None:
    return _recorded("started")


def overnight_stop_line(*, root: str | None = None, log_path: str | None = None) -> str:
    """`stopped_line` for the installed task (#1216). #1223: said only while no later run has
    finished, and the drafts counted from the task's start to the log's last write - on
    2026-10-16 the operator ran overnight by hand after the crash, and the line said "stopped
    after 4 of 3 drafts"."""
    times = _queried_times()
    if not times:
        return beat_gap_line()  # #1468: a hand run, or no Task Scheduler to ask
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
    log = log_path or os.path.join(REPO_ROOT, OVERNIGHT_LOG)
    line = stopped_line(times, drafts_made=made, crash_at=crash_frame(_crash_text(last, log)))
    gap = _stale_beat()
    if line and gap:  # #1468: when it died, and what it was doing
        line += f" Its last sign of life was {_beat_when(gap[1], gap[2])}."
    return line or beat_gap_line()


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


def wake_doctor(*, now: datetime | None = None) -> tuple[bool, str]:
    """#1371 (wave 117): (ok, line) for `ops doctor` - may the task wake the PC, are wake timers
    on, and how the PC went off before the last 5:00. A shutdown passes but is named: the PC
    was shut down on 10-17, 10-18 and 10-19, and each of those mornings started late."""
    wakes = task_wakes()
    if wakes is None:
        return True, "n/a (the task is not readable here)"
    if wakes is False:
        return False, "the task may not wake the PC - py -m scripts.ops schedule-drafts --wake"
    timers = wake_timers()
    if timers.get("ac") == "off":
        return False, "wake timers are off (Power Options > Sleep > Allow wake timers)"
    line = "the task may wake the PC and wake timers are on"
    times = _queried_times()
    moment = now or datetime.now()
    off = _last_off(times, moment) if times else None
    if off is not None and off[0] != "asleep":
        kind, when = off
        line += (
            f"; before the last {_clock(_due(times or {}, moment) or moment)} start the PC was "
            f"{kind} {when:%a} {_clock(when)} - use Sleep, not Shut down"
        )
    return True, line


def tonight_text(
    drafts: int, renders: int, start: tuple[int, int] | None, *, paused: str = ""
) -> str:
    """#1337 (wave 117): what overnight will do, "" when nothing. The operator: an 8 PM toast.
    #1534 (wave 118): `paused` is `batch_review.shelf_pause` - on 10-20 the line said "renders up
    to 2" while 3 finished videos waiting held every render."""
    hour, minute = start or (5, 0)
    clock = _clock(datetime(2000, 1, 1, hour, minute))
    if paused:
        waiting = re.match(r"(\d+) finished videos", paused)
        why = f"{waiting.group(1)} finished videos wait for you" if waiting else "renders paused"
        if drafts <= 0:
            return f"Tonight at {clock}: no drafts, no renders - {why} (ops shelf)"
        return (
            f"Tonight at {clock}: drafts {drafts}, no renders - {why} (ops shelf); leave the PC "
            "asleep, not shut down"
        )
    if drafts <= 0 and renders <= 0:
        return ""
    return (
        f"Tonight at {clock}: drafts {drafts}, renders up to {renders} - leave the PC asleep, "
        "not shut down"
    )


def tonight_line(channel_id: str) -> str:
    """`tonight_text` for the channel, from what overnight itself decides: the drafts it may write
    (`overnight.draft_count` against the waiting drafts) and the renders it may make
    (`batch_review.overnight_render_limit`). Fail-open: ""."""
    try:
        from core.batch_review import overnight_render_limit, pending_drafts, shelf_pause
        from core.output_paths import channel_output_root
        from core.overnight import draft_count

        times = _queried_times() or {}
        count = int(times.get("count") or DEFAULT_COUNT)
        root = os.path.join(channel_output_root(channel_id), "drafts")  # read, never made here
        waiting = len(pending_drafts(channel_id, root=root)) if os.path.isdir(root) else 0
        drafts, _why = draft_count(waiting, count)
        renders, _more = overnight_render_limit(channel_id)
        paused = shelf_pause(channel_id) if renders > 0 else ""  # #1534
        return tonight_text(drafts, renders, times.get("start"), paused=paused)
    except Exception as exc:
        logger.debug("tonight line skipped: %s", exc)
        return ""


def worker_gap_text(last_pass: datetime | None, off: tuple[str, datetime] | None) -> str:
    """How the PC went off after the worker's last pass - "" when it did not."""
    if last_pass is None or off is None or off[1] < last_pass or off[0] == "asleep":
        return ""
    kind, when = off
    return (
        f"last ran {last_pass:%a} {_clock(last_pass)}; the PC was {kind} {when:%a} {_clock(when)} "
        "and it runs only while the PC is on"
    )


def worker_gap() -> str:
    """#1371: the worker's gap named from the event log. On 10-20 the doctor said "check
    data/logs/worker_task.log" - the PC had been shut down at 8:49 PM, 12 minutes after the last
    pass. "" in the suite."""
    try:
        from config import paths
        from jobs.worker_log import last_pass_at

        last = last_pass_at(paths.WORKER_TASK_LOG)
        events = power_events()
        later = [(w, s) for w, s in events if last is not None and w >= last and s in POWER_STATES]
        off = (POWER_STATES[min(later)[1]], min(later)[0]) if later else None
        return worker_gap_text(last, off)
    except Exception as exc:
        logger.debug("worker gap unread: %s", exc)
        return ""


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
        gap = worker_gap() if installed else ""
        if gap:  # #1371: the task runs only while the PC is on
            fix = f"the task is installed and {gap}"
        return False, f"{len(late)} upload(s) overdue and nothing has sent them - {fix}"
    if installed:
        return True, f"queued uploads are sent every {WORKER_EVERY_MINUTES} minutes"
    return True, (
        "nothing sends queued uploads unless a worker window is open "
        "(py -m scripts.ops worker-task --install)"
    )
