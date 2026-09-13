"""#725: run the suite with the clock shifted and report tests whose result changes.

A test pinned `now` to 2026-09-09 while the code under test read the real clock; it
went red three days later, after the wave that wrote it had reported green. That
shape is invisible on the day a test is written. Shifting every clock the code can
read -- `datetime.now/utcnow/today`, `date.today`, `time.time` -- and diffing the
failures against an unshifted run finds it the day it is written instead.

Both runs go through the same harness (`shifted_clock(0)` for the base), so any
side effect of swapping the classes cancels out and only the offset shows. Each run
is a subprocess: the swap has to be in place before test modules import `datetime`.

The first, throwaway harness shifted `date.today()` twice, because CPython's
`date.today()` calls `time.time()`, which was patched too. `ShiftedDate.today` below
derives from the real `datetime.now()` instead.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as _dt
import io
import json
import os
import subprocess
import sys
import time as _time
import unittest
from collections.abc import Iterable, Iterator

from config.paths import ROOT_DIR

_WORKER_TIMEOUT_S = 1800


@contextlib.contextmanager
def shifted_clock(days: int) -> Iterator[None]:
    """Every clock reads `days` ahead inside the block; originals restored after.

    Only lookups made *inside* the block see it: a module that already bound
    `from datetime import date` keeps the real class. `compare` avoids that by
    entering the block before anything is imported.
    """
    off = _dt.timedelta(days=days)
    real_datetime, real_date, real_time = _dt.datetime, _dt.date, _time.time

    class ShiftedDateTime(_dt.datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            r = real_datetime.now(tz) + off
            return cls(r.year, r.month, r.day, r.hour, r.minute, r.second, r.microsecond, r.tzinfo)

        @classmethod
        def utcnow(cls):  # type: ignore[override]
            r = real_datetime.now(_dt.timezone.utc).replace(tzinfo=None) + off
            return cls(r.year, r.month, r.day, r.hour, r.minute, r.second, r.microsecond)

        @classmethod
        def today(cls):  # type: ignore[override]
            return cls.now()

    class ShiftedDate(_dt.date):
        @classmethod
        def today(cls):  # type: ignore[override]
            d = (real_datetime.now() + off).date()
            return cls(d.year, d.month, d.day)

    _dt.datetime = ShiftedDateTime  # type: ignore[misc]
    _dt.date = ShiftedDate  # type: ignore[misc]
    _time.time = lambda: real_time() + off.total_seconds()
    try:
        yield
    finally:
        _dt.datetime = real_datetime  # type: ignore[misc]
        _dt.date = real_date  # type: ignore[misc]
        _time.time = real_time


def changed_tests(*, base_bad: Iterable[str], ahead_bad: Iterable[str]) -> list[str]:
    """Tests whose result differs between the two runs, in either direction."""
    return sorted(set(base_bad) ^ set(ahead_bad))


def _worker(days: int) -> dict[str, object]:
    with shifted_clock(days):
        suite = unittest.defaultTestLoader.discover("tests", top_level_dir=".")
        with (
            open(os.devnull, "w", encoding="utf-8") as sink,
            contextlib.redirect_stdout(sink),
            contextlib.redirect_stderr(sink),
        ):
            result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    bad = sorted(test.id() for test, _ in result.failures + result.errors)
    return {"days": days, "ran": result.testsRun, "bad": bad}


def _run_worker(days: int) -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "core.clock_ahead", "--worker", str(days)],
        capture_output=True,
        text=True,
        timeout=_WORKER_TIMEOUT_S,
        cwd=str(ROOT_DIR),
        check=False,
    )
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith("{"):
            return json.loads(line)
    raise RuntimeError(f"clock-ahead worker at +{days}d printed no result: {proc.stderr[-400:]}")


def compare(days: int) -> list[str]:
    """Run the suite at +0 and +`days`; return tests whose result changed."""
    base = _run_worker(0)
    ahead = _run_worker(days)
    return changed_tests(base_bad=base["bad"], ahead_bad=ahead["bad"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=int, required=True, help="days to shift this run")
    args = parser.parse_args(argv)
    print(json.dumps(_worker(args.worker)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
