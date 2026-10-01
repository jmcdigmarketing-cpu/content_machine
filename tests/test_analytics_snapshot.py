"""#570: keep what the recommenders read at each run, so history cannot be rewritten.

A later sync overwrites a video's live totals, and a later code change re-derives
every stored number (wave 50 changed what `engaged_rate` means for some rows). Nothing
kept what a run's recommendations were made from. `write_run_trace` now writes
`data/traces/<run>.analytics.json` beside the signal snapshot: each timed outcome's
raw metrics and the engaged rate today's code derives from them. `ops analytics-diff
<run>` compares it with now and says, per video, whether the data moved or only the
code that reads it. `RUN_ANALYTICS_SNAPSHOT=false` turns it off.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import datetime, timezone
from unittest.mock import patch

WHEN = datetime(2026, 9, 20, 22, 0, tzinfo=timezone.utc)


class _Stores(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        d = self._tmp.name
        self.traces = os.path.join(d, "traces")
        self._patches = [
            patch("storage.repositories.publish_log.LOG_FILE", os.path.join(d, "log.json")),
            patch("core.run_trace.TRACES_DIR", self.traces),
        ]
        for p in self._patches:
            p.start()
        from storage.repositories.publish_log import get_publish_log_repository

        self.repo = get_publish_log_repository()
        self.ids = {}
        for vid, rate, views in (("vidA", 0.42, 900), ("vidB", 0.30, 400)):
            row = self.repo.create(
                {
                    "content_run_id": None,
                    "channel_id": "tapin",
                    "youtube_video_id": vid,
                    "status": "uploaded",
                    "metrics_json": json.dumps(
                        {"engaged_rate": rate, "engaged_basis": "avg_view_pct", "views": views}
                    ),
                    "detail": vid,
                    "published_at": WHEN,
                }
            )
            self.ids[vid] = row.id

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        self._tmp.cleanup()

    def _trace(self, run_id=7):
        from core.run_trace import write_run_trace

        return write_run_trace(
            run_id=run_id,
            channel_id="tapin",
            input_topic="UFC 320",
            selected_topic="UFC 320",
            status="ok",
        )

    def _snapshot(self, run_id=7):
        with open(os.path.join(self.traces, f"{run_id}.analytics.json"), encoding="utf-8") as f:
            return json.load(f)


class SnapshotTests(_Stores):
    def test_the_trace_keeps_what_the_recommenders_read(self):
        self._trace()
        snap = self._snapshot()
        rows = {r["video_id"]: r for r in snap["rows"]}
        self.assertEqual(set(rows), {"vidA", "vidB"})
        self.assertEqual(rows["vidA"]["raw"]["views"], 900)
        self.assertAlmostEqual(rows["vidA"]["engaged_rate"], 0.42)
        self.assertEqual(snap["channel_id"], "tapin")

    def test_it_can_be_turned_off(self):
        with patch.dict(os.environ, {"RUN_ANALYTICS_SNAPSHOT": "false"}):
            self._trace()
        self.assertFalse(os.path.exists(os.path.join(self.traces, "7.analytics.json")))


class DiffTests(_Stores):
    def test_a_resync_is_data_and_a_new_reader_is_code(self):
        from core.runs.analytics_snapshot import diff_lines

        self._trace()
        self.repo.update(
            self.ids["vidA"],
            {
                "metrics_json": json.dumps(
                    {"engaged_rate": 0.55, "engaged_basis": "avg_view_pct", "views": 1500}
                )
            },
        )
        real = __import__("core.engagement", fromlist=["engaged_rate"]).engaged_rate

        def reader(metrics, **kw):
            value = real(metrics, **kw)
            return None if value is None else (value + 0.05 if "0.3" in str(metrics) else value)

        with patch("core.engagement.engaged_rate", side_effect=reader):
            text = "\n".join(diff_lines(7))
        self.assertIn("vidA: data changed - engaged 42% -> 55%", text)
        self.assertIn("vidB: code changed - engaged 30% -> 35%", text)

    def test_added_and_gone_videos_are_named(self):
        from core.runs.analytics_snapshot import diff_lines

        self._trace()
        self.repo.create(
            {
                "content_run_id": None,
                "channel_id": "tapin",
                "youtube_video_id": "vidC",
                "status": "uploaded",
                "metrics_json": json.dumps({"engaged_rate": 0.2, "views": 50}),
                "published_at": WHEN,
            }
        )
        text = "\n".join(diff_lines(7))
        self.assertIn("1 video(s) measured since", text)

    def test_the_ops_verb(self):
        from scripts.ops import COMMANDS

        self._trace()
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = COMMANDS["analytics-diff"][1](
                Namespace(channel="tapin", target="7", run_id=None)
            )
        self.assertEqual(code, 0)
        self.assertIn("unchanged since run 7", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
