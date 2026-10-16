"""Wave 95 (#1216-#1217): an overnight run that stopped early, and the facts a run records.

- 2026-10-16: the overnight task woke with the PC at 4:30 PM, made run 156, began draft 2 of 3
  and died at 4:32 - Task Scheduler "Last Result -1073740940" (0xC0000374, heap corruption in
  ntdll.dll; no traceback in its log). `ops overnight-last` said "Overnight ran at 4:30 PM on
  Oct 16" and nothing more.
- Every run recorded `key_facts_count` 0 - the facts the operator pasted, not the facts it was
  written from - so run quality scored "too few facts" on all of them: `ops health` read
  authenticity RED (mean 49/100; the same drafts score 97), and `ops blocking` said "thin facts:
  0 verified line(s)" about run 155, written from 25.
"""

from __future__ import annotations

import faulthandler
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core import batch_generation as bg
from tests.test_batch_generation import BatchCase, _discovery, _pipeline_result

CRASHED = """Folder: \\ContentMachine
TaskName:                             \\ContentMachine\\OvernightDrafts
Next Run Time:                        10/17/2026 5:00:00 AM
Status:                               Ready
Last Run Time:                        10/16/2026 4:30:07 PM
Last Result:                          -1073740940
Task To Run:                          cmd /c cd /d "C:\\dev\\content_machine" && (mkdir output\\logs 2>nul & "python.exe" -m scripts.ops overnight --channel tapin --count 3 > output\\logs\\overnight-last.log 2>
Start Time:                           5:00:00 AM
"""


# ---- #1216: an overnight run that stopped early is said ----------------------------------------


class StopTests(unittest.TestCase):
    def test_the_result_and_the_task_are_read(self):
        from core.nightly_task import task_times

        times = task_times(CRASHED)
        self.assertEqual(times["result"], -1073740940)
        self.assertEqual(times["count"], 3)
        self.assertEqual(times["channel"], "tapin")

    def test_the_crash_of_oct_16_is_said(self):
        from core.nightly_task import stopped_line, task_times

        line = stopped_line(task_times(CRASHED), drafts_made=1)
        self.assertIn("4:30 PM on Oct 16", line)
        self.assertIn("stopped after 1 of 3 drafts", line)
        self.assertIn("heap corruption", line)
        self.assertIn("0xC0000374", line)
        self.assertIn("overnight-last.log", line)
        self.assertIn("py -m scripts.ops overnight --channel tapin --count 3", line)

    def test_a_finished_running_or_new_task_says_nothing(self):
        from core.nightly_task import stopped_line, task_times

        for code in ("0", "267009", "267011"):
            with self.subTest(code=code):
                times = task_times(CRASHED.replace("-1073740940", code))
                self.assertEqual(stopped_line(times, drafts_made=3), "")

    def test_a_code_with_no_name_is_still_said(self):
        from core.nightly_task import stopped_line, task_times

        line = stopped_line(task_times(CRASHED.replace("-1073740940", "1")), drafts_made=None)
        self.assertIn("stopped", line)
        self.assertIn("exit 1", line)
        line = stopped_line(task_times(CRASHED.replace("-1073740940", "2147942402")), drafts_made=0)
        self.assertIn("0x80070002", line)

    def test_drafts_are_counted_from_the_last_start(self):
        from core.batch_review import drafts_made_since

        with tempfile.TemporaryDirectory() as root:
            for name, made in (("156", "2026-10-16T16:32:23"), ("155", "2026-10-15T16:59:02")):
                os.makedirs(os.path.join(root, name))
                with open(os.path.join(root, name, "meta.json"), "w", encoding="utf-8") as f:
                    json.dump({"run_id": int(name), "created_at": made}, f)
            since = datetime(2026, 10, 16, 16, 30, 7)
            self.assertEqual(drafts_made_since("tapin", since, root=root), 1)

    def test_overnight_last_prints_it(self):
        from core import batch_review

        with (
            patch("core.nightly_task.overnight_timing_line", return_value="Overnight ran late"),
            patch("core.nightly_task.overnight_stop_line", return_value="Overnight stopped"),
        ):
            lines = batch_review._timing_lines()
        self.assertEqual(lines, ["  Overnight ran late", "  Overnight stopped"])

    def test_the_suite_never_queries_the_task_for_it(self):
        from core import nightly_task

        with patch.object(nightly_task, "run_schtasks", side_effect=AssertionError("queried")):
            self.assertEqual(nightly_task.overnight_stop_line(), "")

    def test_the_overnight_command_turns_on_the_crash_traceback(self):
        from scripts import ops

        args = SimpleNamespace(channel="tapin", count=3, file=None, facts_file=None)
        with (
            patch("core.nightly_task.enable_crash_traceback") as enable,
            patch("core.overnight.run_overnight", return_value=MagicMock()),
            patch("core.overnight.render_overnight", return_value="done"),
        ):
            ops.cmd_overnight(args)
        enable.assert_called_once()

    def test_the_worker_task_turns_it_on_into_its_log(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, "scripts", "worker_task.pyw"), encoding="utf-8") as f:
            self.assertIn("enable_crash_traceback(log)", f.read())

    def test_the_traceback_goes_to_the_stream_given(self):
        from core.nightly_task import enable_crash_traceback

        was = faulthandler.is_enabled()
        self.addCleanup(lambda: faulthandler.enable() if was else faulthandler.disable())
        with tempfile.TemporaryFile("w+") as stream:
            self.assertTrue(enable_crash_traceback(stream))
            self.assertTrue(faulthandler.is_enabled())
            faulthandler.disable()
        with patch.object(sys, "stderr", None):  # pythonw: no console
            self.assertFalse(enable_crash_traceback())


# ---- #1217: a run records the facts it was written from -------------------------------------------


FACTS = """- Titans allowed 3 sacks per game through five weeks
- Colts pass rush: 19 sacks, second in the AFC
- Kickoff Sunday Oct 18, 12:00 PM
"""


class FactTests(unittest.TestCase):
    def test_the_count_is_the_lines_used_plus_the_pasted(self):
        from core.facts.enrichment import used_fact_lines

        self.assertEqual(used_fact_lines(FACTS, ["Calvin Ridley is out"]), 4)
        self.assertEqual(used_fact_lines("", None), 0)

    def test_the_package_carries_it(self):
        import inspect

        from core import content_engine

        self.assertIn('"fact_lines": used_fact_lines(', inspect.getsource(content_engine))

    def test_run155_records_25_not_0(self):
        from core.run_features import build_features

        pkg = {"title": "Titans line vs Colts rush", "script": "Hook. Body.", "fact_lines": 25}
        features = build_features(
            topic="Tennessee Titans at Indianapolis Colts", channel_id="tapin", content_package=pkg
        )
        self.assertEqual(features["fact_lines"], 25)
        self.assertEqual(features["key_facts_count"], 0)  # still the pasted facts

    def _quality_fact_count(self, features):
        from core import run_quality

        report = SimpleNamespace(
            score=90, gate_score=100, verdict="ok", semantic_overlap=0.0, recurrence={}
        )
        with patch("core.authenticity.evaluate_authenticity", return_value=report) as ev:
            run_quality.build_quality(script="Hook. Body.", channel_id="tapin", features=features)
        return ev.call_args.kwargs["fact_count"]

    def test_quality_scores_substance_on_it(self):
        self.assertEqual(self._quality_fact_count({"fact_lines": 25, "key_facts_count": 0}), 25)

    def test_an_old_run_keeps_its_count(self):
        self.assertEqual(self._quality_fact_count({"key_facts_count": 4}), 4)

    def test_blocking_reads_it(self):
        from core.publish_blockers import fact_count_from_record

        new = SimpleNamespace(features_json=json.dumps({"fact_lines": 25, "key_facts_count": 0}))
        old = SimpleNamespace(features_json=json.dumps({"key_facts_count": 2}))
        self.assertEqual(fact_count_from_record(new), 25)
        self.assertEqual(fact_count_from_record(old), 2)


class BatchFactTests(BatchCase):
    def test_a_draft_takes_the_runs_count(self):
        result = _pipeline_result()
        result.features = {**result.features, "fact_lines": 25}
        report = SimpleNamespace(verdict="ok", checks=[])
        with (
            patch("core.pipeline.run_discovery", return_value=_discovery()),
            patch("core.pipeline.run_pipeline", return_value=result),
            patch("core.authenticity.evaluate_authenticity", return_value=report) as ev,
        ):
            out = bg.generate_draft("UFC 320", "tapin")
        self.assertEqual(ev.call_args.kwargs["fact_count"], 25)
        with open(os.path.join(out.path, "meta.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["fact_count"], 25)


if __name__ == "__main__":
    unittest.main()
