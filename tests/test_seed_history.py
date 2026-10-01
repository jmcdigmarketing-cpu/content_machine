"""#927: seeded history was duplicated on every setup and taught post time its own slots.

Run 109's menu said gaming had "1 sample" (the best bet reads this machine's runs) and
"15 past gaming post(s) in this slot" (post time reads every publish-log outcome). The
second number came from the seed: `analytics/seed_tapin._historical_publish_at` gives
the 44 historical videos invented publish times placed on the channel's current slots,
so post time "confirmed" the schedule it already had - and `ops all-setup` /
`all-analytics` re-seed with no duplicate check, adding 44 publish-log rows and 44
performance rows each time.

Now: a re-seed adds nothing (operator: dedupe + keep seeds out of post time); post-time
learning skips seeded rows (their times are made up); engagement averages keep them;
`ops dedupe-seed` lists the duplicates already stored and `--apply` removes them.
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

VIDEOS = [
    {"title": "Topuria KO breakdown", "domain": "ufc", "views": 1200, "engaged_rate": 0.41},
    {"title": "GTA 6 trailer reaction", "domain": "gaming", "views": 800, "engaged_rate": 0.33},
]


class _Stores(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        d = self._tmp.name
        self.seed_path = os.path.join(d, "seed.json")
        with open(self.seed_path, "w", encoding="utf-8") as f:
            json.dump({"channel_id": "tapin", "videos": VIDEOS}, f)
        self._patches = [
            patch("storage.repositories.publish_log.LOG_FILE", os.path.join(d, "publish_log.json")),
            patch("storage.repositories.performance_memory.MEMORY_DIR", os.path.join(d, "perf")),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        self._tmp.cleanup()

    def _publish_rows(self):
        from storage.repositories import publish_log

        with open(publish_log.LOG_FILE, encoding="utf-8") as f:
            return json.load(f)

    def _perf_rows(self):
        from storage.repositories.performance_memory import get_performance_memory_repository

        return get_performance_memory_repository().load_all("tapin")

    def _legacy_seed(self, times):
        """What every seed before this fix did: create rows with no duplicate check."""
        from analytics import seed_tapin
        from storage.repositories.publish_log import JsonPublishLogRepository

        with (
            patch.object(seed_tapin, "_already_seeded", return_value=set()),
            patch.object(JsonPublishLogRepository, "find_by_idempotency", return_value=None),
        ):
            for _ in range(times):
                seed_tapin.seed_tapin(seed_path=self.seed_path)


class SeedTests(_Stores):
    def test_a_second_seed_adds_nothing(self):
        from analytics.seed_tapin import seed_tapin

        self.assertEqual(seed_tapin(seed_path=self.seed_path), 2)
        self.assertEqual(seed_tapin(seed_path=self.seed_path), 0)
        self.assertEqual(len(self._publish_rows()), 2)
        self.assertEqual(len(self._perf_rows()), 2)

    def test_a_seeded_row_is_recognised(self):
        from analytics.seed_tapin import seed_tapin
        from storage.repositories.publish_log import get_publish_log_repository, is_seeded

        seed_tapin(seed_path=self.seed_path)
        rows = get_publish_log_repository().list_timed_outcomes("tapin")
        self.assertTrue(rows and all(is_seeded(r) for r in rows))


class DedupeTests(_Stores):
    def test_duplicates_are_counted_then_removed(self):
        from storage.repositories.performance_memory import get_performance_memory_repository
        from storage.repositories.publish_log import get_publish_log_repository

        self._legacy_seed(3)
        self.assertEqual(len(self._publish_rows()), 6)
        logs = get_publish_log_repository()
        perf = get_performance_memory_repository()
        self.assertEqual(logs.remove_duplicate_seeds("tapin", apply=False), 4)
        self.assertEqual(len(self._publish_rows()), 6)  # a dry run changes nothing
        self.assertEqual(logs.remove_duplicate_seeds("tapin", apply=True), 4)
        self.assertEqual(len(self._publish_rows()), 2)
        self.assertEqual(perf.remove_duplicate_seeds("tapin", apply=True), 4)
        self.assertEqual(len(self._perf_rows()), 2)

    def test_the_ops_verb_is_a_dry_run_by_default(self):
        from scripts.ops import COMMANDS

        self._legacy_seed(2)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = COMMANDS["dedupe-seed"][1](Namespace(channel="tapin", apply=False))
        self.assertEqual(code, 0)
        self.assertIn("2 duplicate seeded publish-log row(s)", buf.getvalue())
        self.assertIn("--apply", buf.getvalue())
        self.assertEqual(len(self._publish_rows()), 4)


class ViewCurveTests(_Stores):
    def test_the_view_curve_backfill_skips_seeded_videos(self):
        """Same root: `ops backfill view-curve --apply` asked YouTube Analytics for the
        views by day of every fake `seed_tapin_N` id, duplicates included."""
        from analytics import view_curve
        from analytics.seed_tapin import seed_tapin

        seed_tapin(seed_path=self.seed_path)
        with patch("analytics.youtube_metrics.fetch_daily_views", return_value=[]) as fetch:
            report = view_curve.backfill("tapin", apply=True, force=False)
        fetch.assert_not_called()
        self.assertEqual(report["stale"], 0)


class JsonLogTests(_Stores):
    def test_a_datetime_update_keeps_the_log_readable(self):
        """#928: the uploader writes `published_at` as a datetime; the JSON log raised
        half-way through a file it had already truncated."""
        from storage.repositories.publish_log import get_publish_log_repository

        repo = get_publish_log_repository()
        row = repo.create({"channel_id": "tapin", "status": "pending", "content_run_id": 3})
        when = datetime(2026, 10, 1, 22, 0, tzinfo=timezone.utc)
        repo.update(row.id, {"status": "uploaded", "youtube_video_id": "v1", "published_at": when})
        rows = self._publish_rows()
        self.assertEqual(rows[0]["published_at"], when.isoformat())
        self.assertEqual(repo.list_timed_outcomes("tapin")[0].published_at, when)


class PostTimeTests(_Stores):
    def test_post_time_does_not_learn_from_seeded_times(self):
        from analytics.post_timing import _collect_timed_samples
        from analytics.seed_tapin import seed_tapin
        from storage.repositories.publish_log import get_publish_log_repository

        seed_tapin(seed_path=self.seed_path)
        get_publish_log_repository().create(
            {
                "content_run_id": 9,
                "channel_id": "tapin",
                "youtube_video_id": "abc123",
                "status": "uploaded",
                "metrics_json": json.dumps({"engaged_rate": 0.5, "domain": "ufc"}),
                "detail": "UFC 320 recap",
                "published_at": datetime(2026, 9, 20, 22, 0, tzinfo=timezone.utc),
            }
        )
        samples = _collect_timed_samples("tapin")
        self.assertEqual([round(rate, 2) for _d, _w, rate in samples], [0.5])


if __name__ == "__main__":
    unittest.main()
