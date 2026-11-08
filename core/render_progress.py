"""Live render progress for CLI (stages + elapsed timer + FFmpeg %)."""

from __future__ import annotations

import os
import subprocess
import threading
import time
from collections.abc import Callable

from core.logging import get_logger

logger = get_logger("core.render_progress")

OnTick = Callable[[str], None] | None


class RenderProgress:
    """Prints stage updates and elapsed time to stdout."""

    def __init__(self, *, enabled: bool = True):
        self.enabled = enabled
        self._t0 = time.perf_counter()
        self._stage_t0 = self._t0

    def _elapsed(self) -> float:
        return time.perf_counter() - self._t0

    def _stage_elapsed(self) -> float:
        return time.perf_counter() - self._stage_t0

    def stage(self, message: str) -> None:
        if not self.enabled:
            return
        self._stage_t0 = time.perf_counter()
        total = self._elapsed()
        print(f"  [{total:5.1f}s] {message}", flush=True)

    def done(self, message: str) -> None:
        if not self.enabled:
            return
        print(f"  [{self._elapsed():5.1f}s] {message}", flush=True)

    def note(self, message: str) -> None:
        if not self.enabled:
            return
        print(f"           {message}", flush=True)


def is_render_progress_enabled() -> bool:
    return os.getenv("CONTENT_RENDER_PROGRESS", "1").lower() not in (
        "0",
        "false",
        "no",
    )


def ffmpeg_simple_run() -> bool:
    """Skip -progress pipe wrapper (avoids rare Windows pipe deadlocks)."""
    return os.getenv("FFMPEG_SIMPLE_RUN", "").lower() in ("1", "true", "yes")


STALLED = "ffmpeg stalled"


def stall_seconds() -> float:
    """#2020: ffmpeg's output time frozen this long is a hang (`FFMPEG_STALL_SECONDS`, default
    120). The operator, 11-07: renders from `ops all` stopped at ~80% and sat for 1,000 s+."""
    try:
        return max(1.0, float(os.getenv("FFMPEG_STALL_SECONDS", "120") or 120))
    except ValueError:
        return 120.0


def with_nostdin(cmd: list[str]) -> list[str]:
    """#2020: ffmpeg never reads the console. Interactive renders hung where overnight ones -
    run with no console - finished; an inherited console lets a key pressed at a review prompt
    reach ffmpeg ('c' makes it wait for a typed command)."""
    out = list(cmd)
    if out and "ffmpeg" in os.path.basename(str(out[0])).lower() and "-nostdin" not in out:
        out.insert(1, "-nostdin")
    return out


def _inject_progress_args(cmd: list[str]) -> list[str]:
    if "-progress" in cmd:
        return cmd
    out = cmd[-1]
    return [*cmd[:-1], "-progress", "pipe:1", "-nostats", out]


def _drain_stderr(proc: subprocess.Popen, bucket: list[str]) -> None:
    if not proc.stderr:
        return
    try:
        for line in proc.stderr:
            bucket.append(line)
    except Exception as exc:
        logger.debug("Stopped draining ffmpeg stderr: %s", exc)


def run_ffmpeg_with_progress(
    cmd: list[str],
    *,
    duration_sec: float,
    progress: RenderProgress | None = None,
) -> subprocess.CompletedProcess:
    """
    Run FFmpeg and stream progress (out_time_ms) until complete.

    Drains stderr on a background thread so the child process cannot block
    when stderr fills (common hang on Windows with -progress pipe:1).
    """
    cmd = list(cmd)
    if "ffmpeg" in cmd[0].lower() and "-loglevel" not in cmd:
        cmd.insert(1, "warning")
        cmd.insert(1, "-loglevel")

    cmd = with_nostdin(_inject_progress_args(cmd))

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    stderr_lines: list[str] = []
    stderr_thread = threading.Thread(
        target=_drain_stderr,
        args=(proc, stderr_lines),
        daemon=True,
    )
    stderr_thread.start()

    assert proc.stdout is not None
    last_pct = -1.0
    stage_start = time.perf_counter()
    last_progress_at = stage_start
    heartbeat_sec = 30.0
    # #2020: a watchdog, not the heartbeat - the heartbeat only runs when ffmpeg writes a line
    stall = stall_seconds()
    watch: dict[str, float] = {"moved": stage_start, "out_ms": -1.0, "pct": 0.0, "stalled": 0.0}
    finished = threading.Event()

    def _watchdog() -> None:
        while not finished.wait(min(1.0, stall / 4)):
            if time.perf_counter() - watch["moved"] > stall and proc.poll() is None:
                watch["stalled"] = 1.0
                try:
                    proc.kill()
                except Exception as exc:
                    logger.debug("stalled ffmpeg not killed: %s", exc)
                return

    threading.Thread(target=_watchdog, daemon=True).start()

    for line in proc.stdout:
        line = line.strip()
        now = time.perf_counter()
        if now - last_progress_at >= heartbeat_sec:
            elapsed = now - stage_start
            msg = f"FFmpeg still running ({elapsed:.0f}s elapsed)..."
            if progress and progress.enabled:
                progress.note(msg)
            last_progress_at = now

        if not line.startswith("out_time_ms="):
            continue
        try:
            out_ms = int(line.split("=", 1)[1])
        except ValueError:
            continue
        if out_ms > watch["out_ms"]:
            watch["out_ms"], watch["moved"] = float(out_ms), time.perf_counter()
            if duration_sec > 0:
                watch["pct"] = min(100.0, (out_ms / 1_000_000.0) / duration_sec * 100.0)
        if duration_sec <= 0:
            continue
        pct = min(100.0, (out_ms / 1_000_000.0) / duration_sec * 100.0)
        if int(pct) != int(last_pct):
            last_pct = pct
            last_progress_at = time.perf_counter()
            elapsed = last_progress_at - stage_start
            msg = f"FFmpeg encode: {pct:5.1f}% ({elapsed:.0f}s elapsed)"
            if progress and progress.enabled:
                progress.note(msg)
            else:
                print(f"\r  {msg}", end="", flush=True)

    proc.wait()
    finished.set()
    stderr_thread.join(timeout=5.0)
    stderr = "".join(stderr_lines)

    if progress is None or progress.enabled:
        print(flush=True)

    if watch["stalled"]:
        said = f"{STALLED} at {watch['pct']:.0f}% - no progress for {stall:.0f}s; killed"
        logger.warning("%s: %s", said, " ".join(str(part) for part in cmd)[:3000])
        if progress and progress.enabled:
            progress.note(said)
        return subprocess.CompletedProcess(
            args=cmd, returncode=1, stdout="", stderr=said + "\n" + stderr
        )

    return subprocess.CompletedProcess(
        args=cmd,
        returncode=proc.returncode or 0,
        stdout="",
        stderr=stderr,
    )
