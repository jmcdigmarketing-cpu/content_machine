"""#944: one `ops all`, and every setup / review verb in a batch (operator, 2026-10-03).

The operator asked whether the setup and review commands were all in the `ops all-*`
batches. They were not: the four batches predated waves 47-54, so `scoreboard`,
`verdicts`, `winners`, `mailbag`, `review-week`, `predictions`, `weekly-report`,
`signal-audit` and `dedupe-seed` ran only when typed. The batch runner also stopped at
the first non-zero step - `sync-metrics` without `YOUTUBE_ANALYTICS_SYNC`, or one dead
feed, hid every report after it - and `ops list` described the batches in hand-written
text that could drift from what ran.

Now the batches are one table (`scripts/ops.BATCHES`), `ops list` prints it, report
batches keep going and name what failed, setup still stops, a step runs once per
invocation, and `ops all` runs checks, analytics and the weekly review (operator: one
`ops all` for everything).
"""

from __future__ import annotations

import io
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from unittest.mock import patch

REVIEW_AND_SETUP_VERBS = (
    "scoreboard",
    "verdicts",
    "winners",
    "mailbag",
    "review-week",
    "predictions",
    "weekly-report",
    "signal-audit",
    "dedupe-seed",
    "sync-metrics",
    "backfill",
)


def _args(**kw):
    from scripts.ops import build_parser

    args = build_parser().parse_args(["list"])
    for k, v in kw.items():
        setattr(args, k, v)
    return args


class _Recorder:
    """Replace every leaf step with a fake that records its name and arguments."""

    def __init__(self, fail: dict[str, int] | None = None):
        from scripts import ops

        self.calls: list[tuple[str, Namespace]] = []
        self.fail = fail or {}
        leaves = {s for b in ops.BATCHES for s in ops.batch_leaves(b)}
        fakes = {}
        for name in leaves:
            fakes[name] = (ops.COMMANDS[name][0], self._fake(name))
        self._patch = patch.dict(ops.COMMANDS, fakes)

    def _fake(self, name):
        def run(args):
            self.calls.append((name, args))
            return self.fail.get(name, 0)

        return run

    def __enter__(self):
        self._patch.start()
        return self

    def __exit__(self, *exc):
        self._patch.stop()

    @property
    def names(self):
        return [n for n, _a in self.calls]


class BatchTableTests(unittest.TestCase):
    def test_every_step_is_a_registered_verb(self):
        from scripts import ops

        for batch in ops.BATCHES:
            self.assertIn(batch, ops.COMMANDS)
            for leaf in ops.batch_leaves(batch):
                self.assertIn(leaf, ops.COMMANDS, f"{batch} names {leaf}")
                self.assertNotIn(leaf, ops.BATCHES)

    def test_every_review_and_setup_verb_is_in_a_batch(self):
        from scripts import ops

        batched = {s for b in ops.BATCHES for s in ops.batch_leaves(b)}
        self.assertEqual([v for v in REVIEW_AND_SETUP_VERBS if v not in batched], [])

    def test_ops_all_covers_checks_analytics_and_the_review(self):
        from scripts import ops

        leaves = set(ops.batch_leaves("all"))
        for batch in ("all-checks", "all-analytics", "all-review"):
            self.assertLessEqual(set(ops.batch_leaves(batch)), leaves, batch)

    def test_ops_list_prints_the_table(self):
        from scripts.ops import COMMANDS

        with redirect_stdout(io.StringIO()) as out:
            COMMANDS["list"][1](_args())
        text = out.getvalue()
        self.assertRegex(text, r"all-review\s+sync-metrics, mailbag, scoreboard")
        self.assertRegex(text, r"all\s+all-checks \+ all-analytics \+ all-review")


class BatchRunTests(unittest.TestCase):
    def setUp(self):
        # #971: these tests are about step order; a working sign-in is assumed (its own
        # behaviour is tests/test_signin_health.py).
        p = patch("youtube.oauth.sign_in_status", return_value="")
        p.start()
        self.addCleanup(p.stop)

    def test_ops_all_runs_each_step_once(self):
        from scripts.ops import COMMANDS

        with _Recorder() as rec, redirect_stdout(io.StringIO()):
            code = COMMANDS["all"][1](_args())
        self.assertEqual(code, 0)
        self.assertEqual(rec.names.count("sync-metrics"), 1)
        self.assertEqual(rec.names.count("scoreboard"), 1)
        self.assertIn("review-week", rec.names)
        self.assertIn("test", rec.names)

    def test_a_report_batch_keeps_going_and_names_what_failed(self):
        from scripts.ops import COMMANDS

        with _Recorder(fail={"sync-metrics": 1}) as rec, redirect_stdout(io.StringIO()) as out:
            code = COMMANDS["all-review"][1](_args())
        self.assertEqual(code, 1)
        self.assertIn("scoreboard", rec.names)
        self.assertIn("review-week", rec.names)
        self.assertIn("1 of 9 steps reported a problem: sync-metrics (exit 1)", out.getvalue())

    def test_setup_still_stops_at_the_first_failure(self):
        from scripts.ops import COMMANDS

        with _Recorder(fail={"init-db": 1}) as rec, redirect_stdout(io.StringIO()) as out:
            code = COMMANDS["all-setup"][1](_args())
        self.assertEqual(code, 1)
        self.assertEqual(rec.names, ["migrate-layout", "init-db"])
        self.assertIn("Stopped: 'init-db' exited with 1", out.getvalue())

    def test_steps_get_their_own_arguments(self):
        from scripts.ops import COMMANDS

        with _Recorder() as rec, redirect_stdout(io.StringIO()):
            COMMANDS["all"][1](_args(apply=True))
            COMMANDS["all-setup"][1](_args(apply=True))
        by_name = dict(rec.calls)
        self.assertEqual(by_name["backfill"].target, "view-curve")
        self.assertTrue(by_name["backfill"].apply)
        self.assertFalse(by_name["dedupe-seed"].apply)  # a dry run, whatever was typed
        self.assertTrue(by_name["review-week"]._batch)


class ReviewWeekInABatchTests(unittest.TestCase):
    def test_without_a_console_it_says_how_to_run_it(self):
        from scripts.ops import COMMANDS

        with (
            patch("sys.stdin.isatty", return_value=False),
            patch("core.success.review.run_review") as review,
            redirect_stdout(io.StringIO()) as out,
        ):
            code = COMMANDS["review-week"][1](_args(_batch=True))
        self.assertEqual(code, 0)
        review.assert_not_called()
        self.assertIn("py -m scripts.ops review-week", out.getvalue())

    def test_typed_directly_it_runs(self):
        from scripts.ops import COMMANDS

        with (
            patch("sys.stdin.isatty", return_value=False),
            patch("core.success.review.run_review") as review,
        ):
            COMMANDS["review-week"][1](_args())
        review.assert_called_once()


if __name__ == "__main__":
    unittest.main()
