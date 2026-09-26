"""Operator minutes-per-run (candidate 65).

The CLI already meters APIs; this meters wall clock vs time spent waiting on
``input()``. In-memory only — never writes ``data/`` or quota stores. Starts
only when ``start_run()`` is called (interactive ``main.py``), so unittest
discover cannot accumulate wait time.
"""

from __future__ import annotations

import builtins
import time
from collections.abc import Callable
from typing import Any

from core import process_state
from core.logging import get_logger

logger = get_logger("core.operator_timer")

_Clock = Callable[[], float]


class OperatorTimer:
    def __init__(self, *, clock: _Clock | None = None) -> None:
        self._clock = clock or time.monotonic
        self.started_at: float | None = None
        self.wait_s = 0.0
        self._wait_open: float | None = None
        self._input_wrapped = False
        self._orig_input: Callable[..., str] | None = None

    def start(self) -> None:
        self.started_at = self._clock()
        self.wait_s = 0.0
        self._wait_open = None

    def begin_wait(self) -> None:
        if self.started_at is None or self._wait_open is not None:
            return
        self._wait_open = self._clock()

    def end_wait(self) -> None:
        if self._wait_open is None:
            return
        self.wait_s += max(0.0, self._clock() - self._wait_open)
        self._wait_open = None

    def snapshot(self, *, now: float | None = None) -> dict[str, float] | None:
        if self.started_at is None:
            return None
        wall = max(0.0, (now if now is not None else self._clock()) - self.started_at)
        wait = self.wait_s
        if self._wait_open is not None:
            wait += max(0.0, (now if now is not None else self._clock()) - self._wait_open)
        wait = min(wait, wall)
        return {
            "wall_s": round(wall, 3),
            "wait_s": round(wait, 3),
            "machine_s": round(max(0.0, wall - wait), 3),
        }


_timer = OperatorTimer()


def get_timer() -> OperatorTimer:
    return _timer


def start_run(*, clock: _Clock | None = None) -> OperatorTimer:
    """Begin a run clock. Optional ``clock`` is for tests (monotonic seconds)."""
    global _timer
    if clock is not None:
        _timer = OperatorTimer(clock=clock)
    _timer.start()
    return _timer


def snapshot() -> dict[str, float] | None:
    return _timer.snapshot()


def clear() -> None:
    """Drop the run clock (tests / process end). Does not unwrap input()."""
    _timer.started_at = None
    _timer.wait_s = 0.0
    _timer._wait_open = None


def format_line(data: dict[str, float] | None = None) -> str | None:
    snap = data if data is not None else snapshot()
    if not snap:
        return None
    wait_m = snap["wait_s"] / 60.0
    mach_m = snap["machine_s"] / 60.0
    wall_m = snap["wall_s"] / 60.0
    return (
        f"Operator time: {wall_m:.1f} min wall ({wait_m:.1f} min prompts, {mach_m:.1f} min machine)"
    )


def install_input_wrapper() -> None:
    """Count ``input()`` waits. Call from interactive main only, not at import."""
    if _timer._input_wrapped:
        return
    orig = builtins.input
    _timer._orig_input = orig

    def _wrapped(prompt: Any = "") -> str:
        _timer.begin_wait()
        try:
            return orig(prompt)
        finally:
            _timer.end_wait()

    builtins.input = _wrapped  # type: ignore[assignment]
    _timer._input_wrapped = True


process_state.register_reset("core.operator_timer", clear)  # #827
