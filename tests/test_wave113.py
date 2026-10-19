"""Wave 113 (2026-10-18): the six most pressing of the 22 shortfalls.

Measured first: Buffer measured five TikTok posts and every one read "not measured yet" - TikTok
calls the metric "Video Views" - and those viewers watched 1.24-1.68 s, inside the 2.15 s intro;
`ops status` told the operator to mark Buffer's sends by hand; metrics synced only when
`ops morning` ran; the YouTube quota ledger kept a daily total and nothing said what spent
9,485 units; a waiting draft was titled "Hot Dads & Horny Art"; week_compile cut 2.15 s from
every Short, including one rendered without the intro.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

NOW = datetime(2026, 10, 18, 23, 0, tzinfo=timezone.utc)

TIKTOK_NODE = {
    "id": "p1",
    "metricsUpdatedAt": "2026-10-18T20:00:00Z",
    "metrics": [
        {"name": "Reactions", "value": 3},
        {"name": "Comments", "value": 0},
        {"name": "Video Views", "value": 79},
        {"name": "Shares", "value": 1},
        {"name": "Reach", "value": 70},
        {"name": "Watch Time (min)", "value": 1.67},
        {"name": "Avg. Watch Time (sec)", "value": 1.24},
    ],
}
INSTAGRAM_NODE = {
    "id": "p2",
    "metricsUpdatedAt": "2026-10-18T20:00:00Z",
    "metrics": [
        {"name": "Reactions", "value": 2},
        {"name": "Views", "value": 129},
        {"name": "Reach", "value": 117},
        {"name": "Follows", "value": 1},
        {"name": "Saves", "value": 0},
    ],
}


class BufferMetricTests(unittest.TestCase):
    """B1 (#1418, #1329): what Buffer measured is read under every name it uses."""

    def test_tiktok_video_views_are_views(self):
        from publishing.buffer_api import parse_metrics_node

        row = parse_metrics_node(TIKTOK_NODE)
        self.assertEqual(row["views"], 79)
        self.assertEqual(row["likes"], 3)
        self.assertEqual(row["avg_watch_s"], 1.24)
        self.assertEqual(row["reach"], 70)

    def test_instagram_follows_and_likes(self):
        from publishing.buffer_api import parse_metrics_node

        row = parse_metrics_node(INSTAGRAM_NODE)
        self.assertEqual((row["views"], row["likes"], row["follows"]), (129, 2, 1))

    def test_a_stored_row_is_read_again_from_its_raw_metrics(self):
        from publishing import platform_metrics

        stored = {"rows": {"157": {"tiktok": {
            "measured": True, "views": None, "likes": None,
            "buffer": {"Video Views": 79, "Reactions": 0, "Avg. Watch Time (sec)": 1.24},
        }}}}  # fmt: skip
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "platform_metrics_{channel}.json")
            with open(path.format(channel="tapin"), "w", encoding="utf-8") as handle:
                json.dump(stored, handle)
            with patch.object(platform_metrics, "METRICS_TEMPLATE", path):
                row = platform_metrics.get_row("tapin", "157", "tiktok")
        self.assertEqual((row["views"], row["avg_watch_s"]), (79, 1.24))

    def test_the_feed_line_says_how_long_tiktok_viewers_watch(self):
        from publishing import platform_recommend

        rows = {"157": {"tiktok": {"measured": True, "views": 79, "avg_watch_s": 1.24}},
                "155": {"tiktok": {"measured": True, "views": 76, "avg_watch_s": 1.4}}}  # fmt: skip
        with (
            patch("publishing.platform_metrics.load", return_value={"rows": rows}),
            patch("publishing.crosspost._load", return_value={"posts": {}}),
            patch.object(platform_recommend, "learning_line", return_value=""),
            patch.object(platform_recommend, "_intro_seconds", return_value=2.15),
        ):
            lines = platform_recommend.feed_lines("tapin")
        line = next(ln for ln in lines if ln.startswith("TikTok"))
        self.assertIn("155 views", line)
        self.assertIn("1.3 s", line)
        self.assertIn("intro", line)


class BufferWeekLineTests(unittest.TestCase):
    """B1 (#1398): the status line counts Buffer's sends and asks for nothing by hand."""

    def test_the_line_counts_sends_and_asks_nothing(self):
        from publishing.crosspost import week_line

        store = {
            "runs": {"150": {"packed": (NOW - timedelta(days=1)).isoformat(), "posted": ""}},
            "posts": {
                "157": {"tiktok": {"state": "sent", "post_id": "a", "at": (NOW - timedelta(days=2)).isoformat(),
                                   "sent_at": (NOW - timedelta(days=2)).isoformat()},
                        "instagram": {"state": "sent", "post_id": "b", "at": (NOW - timedelta(days=2)).isoformat(),
                                      "sent_at": (NOW - timedelta(days=2)).isoformat()}},
                "164": {"tiktok": {"state": "scheduled", "post_id": "c", "at": (NOW - timedelta(hours=3)).isoformat()}},
            },
        }  # fmt: skip
        with patch("publishing.crosspost._load", return_value=store):
            line = week_line("tapin", now=NOW)
        self.assertNotIn("crosspost done", line)
        self.assertNotIn("packed", line)
        self.assertIn("1 posted", line)
        self.assertIn("1 scheduled", line)


class UnattendedSyncTests(unittest.TestCase):
    """B2 (#1489, #1490): the metrics sync runs once a day without the operator."""

    def _stamp(self, tmp, when):
        path = os.path.join(tmp, "metrics_synced.json")
        if when is not None:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"tapin": when.isoformat()}, handle)
        return path

    def test_a_stale_or_missing_stamp_syncs(self):
        from analytics import sync_metrics

        for age in (None, timedelta(hours=21)):
            with tempfile.TemporaryDirectory() as tmp:
                path = self._stamp(tmp, None if age is None else NOW - age)
                with (
                    patch.object(sync_metrics, "SYNC_STAMP_FILE", path),
                    patch.object(sync_metrics, "sync_channel", return_value=0) as sync,
                ):
                    ran = sync_metrics.maybe_sync("tapin", now=NOW)
            self.assertTrue(ran, age)
            sync.assert_called_once()

    def test_a_fresh_stamp_does_not(self):
        from analytics import sync_metrics

        with tempfile.TemporaryDirectory() as tmp:
            path = self._stamp(tmp, NOW - timedelta(hours=3))
            with (
                patch.object(sync_metrics, "SYNC_STAMP_FILE", path),
                patch.object(sync_metrics, "sync_channel", return_value=0) as sync,
            ):
                ran = sync_metrics.maybe_sync("tapin", now=NOW)
        self.assertFalse(ran)
        sync.assert_not_called()

    def test_a_finished_sync_stamps_itself(self):
        from analytics import sync_metrics

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "metrics_synced.json")
            with patch.object(sync_metrics, "SYNC_STAMP_FILE", path):
                sync_metrics.mark_synced("tapin", now=NOW)
                self.assertEqual(sync_metrics.last_synced("tapin"), NOW)

    def test_health_says_when_it_synced_and_that_youtube_lags(self):
        from analytics import sync_metrics

        with tempfile.TemporaryDirectory() as tmp:
            path = self._stamp(tmp, NOW - timedelta(hours=13))
            with patch.object(sync_metrics, "SYNC_STAMP_FILE", path):
                note = sync_metrics.sync_note("tapin", now=NOW)
        self.assertIn("13 h ago", note)
        self.assertIn("2-3 days", note)

    def test_a_failed_sync_is_not_retried_every_pass(self):
        from analytics import sync_metrics

        with tempfile.TemporaryDirectory() as tmp:
            path = self._stamp(tmp, None)
            with (
                patch.object(sync_metrics, "SYNC_STAMP_FILE", path),
                patch.object(sync_metrics, "sync_channel", return_value=1) as sync,
            ):
                first = sync_metrics.maybe_sync("tapin", now=NOW)
                again = sync_metrics.maybe_sync("tapin", now=NOW + timedelta(minutes=15))
                later = sync_metrics.maybe_sync("tapin", now=NOW + timedelta(hours=3))
        self.assertEqual((first, again, later), (True, False, True))
        self.assertEqual(sync.call_count, 2)

    def test_overnight_and_the_worker_call_it(self):
        import inspect

        from core import overnight
        from jobs import worker

        self.assertIn("maybe_sync", inspect.getsource(overnight.run_overnight))
        self.assertIn("_sync_metrics()", inspect.getsource(worker.main))
        with patch("analytics.sync_metrics.maybe_sync") as sync:
            worker._sync_metrics()
        sync.assert_called_with("tapin")


if __name__ == "__main__":
    unittest.main()
