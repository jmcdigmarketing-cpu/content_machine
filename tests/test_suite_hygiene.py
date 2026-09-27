"""#892: the suite may not write the operator's `data/` or `output/`, and `ops test` proves it.

A full run updated five `data/` files and two `output/` files: operator minutes from the
upload tests, channel memory from a pipeline test, the incident and reliability ledgers
from the vacuum test, subtitles from the caption tests. `tests/__init__.py` redirected
fifteen stores, not these, and nothing failed - CI starts with no `data/`, so nobody saw
it. `ops test` now snapshots both folders and fails, naming the files, when a run
changed any; CI's reversed leg runs through it.
"""

from __future__ import annotations

import argparse
import io
import os
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


class SnapshotTests(unittest.TestCase):
    def test_a_new_and_a_modified_file_are_reported_an_untouched_one_is_not(self):
        from core.suite_hygiene import changed, snapshot

        with tempfile.TemporaryDirectory() as root:
            data = os.path.join(root, "data")
            os.makedirs(data)
            kept = os.path.join(data, "kept.json")
            touched = os.path.join(data, "touched.json")
            for path in (kept, touched):
                with open(path, "w", encoding="utf-8") as f:
                    f.write("{}")
            before = snapshot([data])
            time.sleep(0.01)
            with open(touched, "w", encoding="utf-8") as f:
                f.write('{"x": 1}')
            with open(os.path.join(data, "new.json"), "w", encoding="utf-8") as f:
                f.write("{}")
            after = snapshot([data])
        self.assertEqual(
            sorted(os.path.basename(p) for p in changed(before, after)),
            ["new.json", "touched.json"],
        )

    def test_a_missing_folder_is_an_empty_snapshot(self):
        from core.suite_hygiene import snapshot

        self.assertEqual(snapshot(["/no/such/folder/anywhere"]), {})


class OpsTestGuardTests(unittest.TestCase):
    def _run(self, wrote: bool, rc: int = 0):
        from scripts import ops

        snaps = [{"data/a.json": 1.0}, {"data/a.json": 2.0 if wrote else 1.0}]
        out = io.StringIO()
        with (
            patch("core.suite_hygiene.snapshot", side_effect=snaps),
            patch.object(ops, "_run_module", return_value=rc),
            redirect_stdout(out),
        ):
            code = ops.cmd_test(argparse.Namespace(order="default", seed=None))
        return code, out.getvalue()

    def test_a_run_that_wrote_fails_and_names_the_file(self):
        code, text = self._run(wrote=True)
        self.assertEqual(code, 1)
        self.assertIn("data/a.json", text)

    def test_a_clean_run_keeps_its_own_exit_code(self):
        self.assertEqual(self._run(wrote=False)[0], 0)
        self.assertEqual(self._run(wrote=False, rc=1)[0], 1)


class RedirectTests(unittest.TestCase):
    """The stores the measured run wrote now point into the suite's temp folder."""

    def test_the_stores_are_redirected(self):
        import config.competitors as competitors
        import config.paths as paths
        from core import incident_ledger, operator_minutes
        from storage.repositories import channel_memory
        from video import subtitles

        real_data = os.path.join(paths.ROOT_DIR, "data")
        for value in (
            operator_minutes.MINUTES_FILE,
            incident_ledger.INCIDENTS_FILE,
            paths.RELIABILITY_HISTORY_FILE,
            competitors.competitors_data_path("tapin"),
            os.path.abspath(channel_memory.MEMORY_DIR),
        ):
            self.assertFalse(os.path.abspath(value).startswith(real_data), value)
        self.assertFalse(
            os.path.abspath(subtitles.SUBTITLE_DIR).startswith(
                os.path.join(paths.ROOT_DIR, "output")
            ),
            subtitles.SUBTITLE_DIR,
        )


if __name__ == "__main__":
    unittest.main()
