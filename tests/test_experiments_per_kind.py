"""#919: one active experiment per kind, not per channel.

`data/experiments.json` kept one active lever per channel, so starting the #912
`post_time` test stopped a running hook or thumbnail test, and the reverse. Levers of
different kinds touch different things (the script prompt, the thumbnail prompt, the
publish time) and cannot confound each other's arm counts, so each kind now has its own
active slot. A file written before this still reads; `stop` with no lever stops them all
as before, `stop <lever>` stops that one's kind.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from core import experiments as ex


class _Store(unittest.TestCase):
    def setUp(self):
        import config.paths as paths

        self._tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._tmp.name, "experiments.json")
        self._patch = patch.object(paths, "EXPERIMENTS_FILE", self.path)
        self._patch.start()
        self._n = patch.object(ex, "_measured_n", return_value=0)
        self._n.start()

    def tearDown(self):
        self._n.stop()
        self._patch.stop()
        self._tmp.cleanup()


class KindTests(_Store):
    def test_two_kinds_run_together(self):
        ex.start_experiment("tapin", "hook_style")
        ex.start_experiment("tapin", "post_time")
        self.assertEqual(ex.next_arm("tapin", kind="script")[0], "hook_style")
        self.assertEqual(ex.next_arm("tapin", kind="post_time")[0], "post_time")
        levers = sorted(a["lever"] for a in ex.active_experiments("tapin"))
        self.assertEqual(levers, ["hook_style", "post_time"])

    def test_the_same_kind_is_replaced(self):
        ex.start_experiment("tapin", "hook_style")
        ex.start_experiment("tapin", "post_time")
        ex.start_experiment("tapin", "cta_style")
        self.assertEqual(ex.active_experiment("tapin", kind="script")["lever"], "cta_style")
        self.assertEqual(ex.active_experiment("tapin", kind="post_time")["lever"], "post_time")

    def test_stopping_one_lever_leaves_the_other(self):
        ex.start_experiment("tapin", "hook_style")
        ex.start_experiment("tapin", "post_time")
        ex.stop_experiment("tapin", "post_time")
        self.assertIsNone(ex.active_experiment("tapin", kind="post_time"))
        self.assertEqual(ex.active_experiment("tapin", kind="script")["lever"], "hook_style")
        ex.stop_experiment("tapin")
        self.assertEqual(ex.active_experiments("tapin"), [])

    def test_a_file_from_before_still_reads(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"active": {"tapin": {"lever": "thumbnail_style", "started_at": 1.0}},
                       "assignments": []}, f)  # fmt: skip
        self.assertEqual(
            ex.active_experiment("tapin", kind="thumbnail")["lever"], "thumbnail_style"
        )
        ex.start_experiment("tapin", "hook_style")
        self.assertEqual(
            ex.active_experiment("tapin", kind="thumbnail")["lever"], "thumbnail_style"
        )

    def test_the_report_shows_every_running_lever(self):
        ex.start_experiment("tapin", "hook_style")
        ex.start_experiment("tapin", "post_time")
        buf = io.StringIO()
        with redirect_stdout(buf), patch.object(ex, "_run_engagement", return_value={}):
            ex.display_report("tapin")
        self.assertIn("Experiment: hook_style", buf.getvalue())
        self.assertIn("Experiment: post_time", buf.getvalue())

    def test_the_cli_stops_one_lever(self):
        ex.start_experiment("tapin", "hook_style")
        ex.start_experiment("tapin", "post_time")
        with redirect_stdout(io.StringIO()):
            ex.main(["stop", "post_time", "--channel", "tapin"])
        self.assertEqual([a["lever"] for a in ex.active_experiments("tapin")], ["hook_style"])

    def test_the_start_message_says_what_feeds_it(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            ex.main(["start", "post_time", "--channel", "tapin"])
        self.assertIn("scheduled uploads now alternate", buf.getvalue())
        self.assertNotIn("batch-drafts", buf.getvalue())

    def test_dual_thumbnails_still_see_their_lever_beside_a_script_test(self):
        from core.thumbnail_pick import dual_thumbnail_enabled

        ex.start_experiment("tapin", "thumbnail_format")
        ex.start_experiment("tapin", "hook_style")
        with patch.dict(os.environ, {"THUMBNAIL_DUAL": ""}):
            self.assertTrue(dual_thumbnail_enabled("tapin"))


if __name__ == "__main__":
    unittest.main()
