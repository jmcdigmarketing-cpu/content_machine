"""Wave 97 (#1223, #1222): the morning's overnight line and `ops blocking`, read on 2026-10-16.

- #1216's line, after the operator ran overnight by hand at 5:00 PM: "Overnight started at 4:30
  PM on Oct 16 and stopped after 4 of 3 drafts". It counted the hand run's three drafts with the
  crashed run's one, and still said "stopped" after the hand run finished. Task Scheduler's result
  belongs to the 4:30 run alone.
- `ops blocking` described run 139, rendered and then pulled on 10-13 ("thin facts: 0"); after run
  155 rendered it said "authenticity review (need ok)" - the trace's own copy of the scores, from
  before the 10-16 re-score. The run's record says ok.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_stops_and_facts import CRASHED


def _write(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)


# ---- #1223: the stop line counts the run that stopped, and is quiet once a later run finished ----


class StopRecordTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self.record = os.path.join(self.tmp, "overnight_last.json")
        self.log = os.path.join(self.tmp, "overnight-last.log")
        self.drafts = os.path.join(self.tmp, "drafts")
        for run, made in (
            (156, "2026-10-16T16:32:23"),
            (157, "2026-10-16T17:01:53"),
            (158, "2026-10-16T17:04:57"),
            (159, "2026-10-16T17:07:23"),
        ):
            os.makedirs(os.path.join(self.drafts, str(run)))
            _write(os.path.join(self.drafts, str(run), "meta.json"), {"created_at": made})
        with open(self.log, "w", encoding="utf-8") as f:
            f.write("16:32:13 [WARNING] Quote attribution: 1 quoted sentence lacks a source\n")
        died = datetime(2026, 10, 16, 16, 32, 13).timestamp()  # run 156 saved at 16:32:23
        os.utime(self.log, (died, died))
        env = patch.dict(os.environ, {"OVERNIGHT_RECORD_FILE": self.record})
        env.start()
        self.addCleanup(env.stop)

    def _line(self):
        from core import nightly_task

        with patch.object(
            nightly_task, "_queried_times", return_value=nightly_task.task_times(CRASHED)
        ):
            return nightly_task.overnight_stop_line(root=self.drafts, log_path=self.log)

    def test_the_hand_run_that_finished_quiets_it(self):
        _write(self.record, {"channel": "tapin", "started": "2026-10-16T17:00:21",
                             "finished": "2026-10-16T17:10:41", "drafts": 3})  # fmt: skip
        self.assertEqual(self._line(), "")

    def test_drafts_are_counted_to_the_logs_last_write(self):
        _write(self.record, {"channel": "tapin", "started": "2026-10-16T16:30:08",
                             "finished": "", "drafts": None})  # fmt: skip
        line = self._line()
        self.assertIn("stopped after 1 of 3 drafts", line)
        self.assertNotIn("4 of 3", line)

    def test_with_no_record_it_still_says_it(self):
        self.assertIn("stopped after 1 of 3 drafts", self._line())

    def test_a_later_run_that_also_died_bounds_the_count(self):
        os.utime(self.log, None)  # the hand run kept writing the log until now
        _write(self.record, {"channel": "tapin", "started": "2026-10-16T17:00:21",
                             "finished": "", "drafts": None})  # fmt: skip
        self.assertIn("stopped after 1 of 3 drafts", self._line())

    def test_ops_overnight_writes_start_and_finish(self):
        from scripts import ops

        args = SimpleNamespace(channel="tapin", count=3, file=None, facts_file=None)
        with (
            patch("core.nightly_task.enable_crash_traceback"),
            patch("core.overnight.run_overnight", return_value=SimpleNamespace(drafted=3)),
            patch("core.overnight.render_overnight", return_value="done"),
        ):
            ops.cmd_overnight(args)
        with open(self.record, encoding="utf-8") as f:
            record = json.load(f)
        self.assertEqual(record["channel"], "tapin")
        self.assertTrue(record["started"])
        self.assertTrue(record["finished"])
        self.assertEqual(record["drafts"], 3)

    def test_a_run_that_dies_leaves_no_finish(self):
        from scripts import ops

        args = SimpleNamespace(channel="tapin", count=3, file=None, facts_file=None)
        with (
            patch("core.nightly_task.enable_crash_traceback"),
            patch("core.overnight.run_overnight", side_effect=RuntimeError("native crash")),
            self.assertRaises(RuntimeError),
        ):
            ops.cmd_overnight(args)
        with open(self.record, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["finished"], "")


class SuiteRecordTests(unittest.TestCase):
    def test_the_suite_never_writes_the_real_record(self):
        from core.nightly_task import overnight_record_path

        self.assertTrue(os.environ.get("OVERNIGHT_RECORD_FILE"))
        self.assertNotIn(os.path.join("data", "overnight_last.json"), overnight_record_path())


# ---- #1222: `ops blocking` reads the run on the shelf, with the run's own scores ------------------


class BlockingTests(unittest.TestCase):
    def test_a_pulled_run_is_skipped(self):
        from core.review_booth import last_reviewable_trace

        traces = [
            {"run_id": 139, "status": "rendered", "channel_id": "tapin"},
            {"run_id": 130, "status": "rendered", "channel_id": "tapin"},
        ]
        pulled = "pulled - Pulled 2026-10-13: states a result for a game not yet played"
        with (
            patch("core.run_trace.list_traces", return_value=traces),
            patch(
                "core.stale_renders.gone_reason",
                side_effect=lambda r, _c: pulled if r == 139 else "",
            ),
        ):
            self.assertEqual(last_reviewable_trace("tapin")["run_id"], 130)

    def test_the_runs_record_wins_over_the_trace_copy(self):
        from core.publish_blockers import last_run_context

        trace = {"run_id": 155, "status": "rendered",
                 "quality": {"authenticity_verdict": "review", "authenticity_gate_score": 40}}  # fmt: skip
        record = SimpleNamespace(
            features_json=json.dumps({"fact_lines": 25}),
            quality_json=json.dumps({"authenticity_verdict": "ok", "authenticity_gate_score": 100}),
            mp4_path="",
        )
        repo = SimpleNamespace(get=lambda _run: record)
        with (
            patch("core.review_booth.last_reviewable_trace", return_value=trace),
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),
        ):
            context = last_run_context("tapin")
        self.assertEqual(context["quality"]["authenticity_verdict"], "ok")
        self.assertEqual(context["quality"]["authenticity_gate_score"], 100)
        self.assertEqual(context["fact_count"], 25)


if __name__ == "__main__":
    unittest.main()
