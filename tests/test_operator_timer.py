"""Operator minutes-per-run — in-memory only, no data/ writes."""

from __future__ import annotations

import unittest

from core.operator_timer import OperatorTimer, format_line, start_run


class _FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


class TestOperatorTimer(unittest.TestCase):
    def test_wait_is_subtracted_from_machine(self):
        clock = _FakeClock()
        timer = OperatorTimer(clock=clock)
        timer.start()
        clock.t = 10.0
        timer.begin_wait()
        clock.t = 40.0
        timer.end_wait()
        clock.t = 50.0
        snap = timer.snapshot()
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertAlmostEqual(snap["wall_s"], 50.0)
        self.assertAlmostEqual(snap["wait_s"], 30.0)
        self.assertAlmostEqual(snap["machine_s"], 20.0)

    def test_format_line_minutes(self):
        line = format_line({"wall_s": 120.0, "wait_s": 60.0, "machine_s": 60.0})
        self.assertIsNotNone(line)
        assert line is not None
        self.assertIn("2.0 min wall", line)
        self.assertIn("1.0 min prompts", line)
        self.assertIn("1.0 min machine", line)

    def test_snapshot_none_before_start(self):
        timer = OperatorTimer()
        self.assertIsNone(timer.snapshot())

    def test_start_run_resets(self):
        clock = _FakeClock()
        try:
            start_run(clock=clock)
            clock.t = 5.0
            from core.operator_timer import snapshot

            snap = snapshot()
            self.assertIsNotNone(snap)
            assert snap is not None
            self.assertAlmostEqual(snap["wall_s"], 5.0)
        finally:
            from core.operator_timer import clear

            clear()


if __name__ == "__main__":
    unittest.main()
