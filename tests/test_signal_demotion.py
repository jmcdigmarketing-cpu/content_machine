"""Wave 78 (#1073): a signal that feeds nothing runs one run in three.

Operator, 2026-10-10: "Run it less often". Measured on TapIn's last 20 recorded runs: `sports`
ran on 9 and `twitch` on 5, and neither was active once - no line in a prompt, nothing toward
a topic score - while every one of those runs waited on them.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch


def _row(signal, runs, active, fed):
    return {"signal": signal, "runs": runs, "active": active, "fed": fed, "cited": 0}


ROWS = [
    _row("news", 20, 10, 10),
    _row("trends", 20, 18, 0),  # active, feeds the score - never demoted
    _row("sports", 9, 0, 0),
    _row("twitch", 5, 0, 0),
    _row("earnings", 2, 0, 0),  # too few runs to judge
]


class IdleRuleTests(unittest.TestCase):
    def test_never_active_on_enough_runs_is_idle(self):
        from core.runs.signal_audit import idle_from_rows

        self.assertEqual(idle_from_rows(ROWS), {"sports": 9, "twitch": 5})

    def test_a_signal_that_is_ever_active_is_not_idle(self):
        from core.runs.signal_audit import idle_from_rows

        self.assertEqual(idle_from_rows([_row("trends", 20, 1, 0)]), {})
        self.assertEqual(idle_from_rows([_row("sports", 9, 1, 0)]), {})

    def test_every_third_run_is_a_full_turn(self):
        from core.runs.signal_audit import full_turn

        self.assertEqual([full_turn(n) for n in (133, 134, 135, 136)], [False, False, True, False])


class DemotedNowTests(unittest.TestCase):
    def setUp(self):
        from core.runs import signal_audit

        signal_audit.reset_cache()
        self.addCleanup(signal_audit.reset_cache)

    def _demoted(self, next_run, env=None):
        from core.runs import signal_audit

        with (
            patch.object(signal_audit, "idle_signals", return_value={"sports": 9, "twitch": 5}),
            patch.dict("os.environ", env or {}),
        ):
            return signal_audit.demoted_now("tapin", next_run=next_run)

    def test_two_runs_in_three_leave_the_idle_signals_out(self):
        self.assertEqual(self._demoted(133), {"sports", "twitch"})
        self.assertEqual(self._demoted(134), {"sports", "twitch"})

    def test_the_third_run_asks_them_again(self):
        self.assertEqual(self._demoted(135), set())

    def test_the_switch_turns_it_off(self):
        self.assertEqual(self._demoted(133, {"SIGNAL_DEMOTION": "false"}), set())

    def test_nothing_idle_skips_nothing(self):
        from core.runs import signal_audit

        with patch.object(signal_audit, "idle_signals", return_value={}):
            self.assertEqual(signal_audit.demoted_now("tapin", next_run=133), set())

    def test_the_idle_list_is_recomputed_when_a_run_is_recorded(self):
        from core.runs import signal_audit

        answers = iter([[_row("sports", 9, 0, 0)], [_row("sports", 10, 1, 1)]])
        with (
            patch.object(signal_audit, "load_runs", return_value=[]),
            patch.object(signal_audit, "contribution_rows", side_effect=lambda runs: next(answers)),
            patch.object(signal_audit, "_latest_run_id", side_effect=[140, 140, 141]),
        ):
            self.assertEqual(signal_audit.idle_signals("tapin"), {"sports": 9})
            self.assertEqual(signal_audit.idle_signals("tapin"), {"sports": 9})  # cached
            self.assertEqual(signal_audit.idle_signals("tapin"), {})  # it fed once: demotion over


class WhereItIsUsedTests(unittest.TestCase):
    def test_the_registry_skips_what_is_demoted(self):
        from apis import register_signals

        with (
            patch("core.runs.signal_audit.demoted_now", return_value={"sports"}),
            patch("core.runs.signal_skips.skipped_for", return_value={}),
            patch.dict("os.environ", {"CONTENT_SKIP_SIGNALS": ""}),
        ):
            self.assertEqual(register_signals._skip_signals("tapin"), {"sports"})

    def test_an_unreadable_audit_skips_nothing(self):
        from apis import register_signals

        with (
            patch("core.runs.signal_audit.demoted_now", side_effect=OSError("no traces")),
            patch("core.runs.signal_skips.skipped_for", return_value={}),
            patch.dict("os.environ", {"CONTENT_SKIP_SIGNALS": ""}),
        ):
            self.assertEqual(register_signals._skip_signals("tapin"), set())

    def test_the_audit_and_the_health_screen_say_which(self):
        from core.runs import signal_audit

        with (
            patch.object(signal_audit, "idle_signals", return_value={"sports": 9, "twitch": 5}),
            patch.object(
                signal_audit, "fed_counts", return_value={"news": (10, 20), "sports": (0, 9)}
            ),
        ):
            line = signal_audit.demotion_line("tapin")
            health = signal_audit.health_lines("tapin", ["news", "sports"])
        self.assertIn("Running 1 run in 3 until they feed a script", line)
        self.assertIn("sports 0/9, twitch 0/5", line)
        self.assertIn("SIGNAL_DEMOTION=false", line)
        self.assertEqual(health[-1], line)

    def test_an_empty_suite_store_demotes_nothing(self):
        """No recorded runs (the suite, a fresh clone): every signal runs."""
        from core.runs import signal_audit

        self.assertEqual(signal_audit.demoted_now("tapin"), set())
        self.assertEqual(signal_audit.demotion_line("tapin"), "")


if __name__ == "__main__":
    unittest.main()
