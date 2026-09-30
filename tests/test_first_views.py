"""#563 (operator's choice: daily from Analytics): time to the first 100 views.

The 7-day engaged rate takes a week to land; how fast a video reaches its first 100
views is known in a day or two. Nothing stored could compute it: each video kept one
28-day total plus at most a 24h and a 7d snapshot. Each sync now asks YouTube Analytics
for views by day (one extra query per synced video), the series is merged by day so it
survives the moving 28-day window, and `first_views` is frozen once the threshold
(`FIRST_VIEWS_THRESHOLD`, default 100) is reached. A series that starts after the
publish day cannot say when the 100th view came, so it says nothing. `ops predictions`
prints the median and its correlation with the engaged rate; `ops backfill view-curve
--apply` fills past videos (network, so only on --apply).
"""

from __future__ import annotations

import json
import os
import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

PUBLISHED = datetime(2026, 9, 20, 22, 0, tzinfo=timezone.utc)  # 15:00 Pacific, 20th


class CurveTests(unittest.TestCase):
    def test_days_to_the_threshold(self):
        from analytics.view_curve import days_to_views

        daily = [["2026-09-20", 40], ["2026-09-21", 50], ["2026-09-22", 30]]
        got = days_to_views(daily, date(2026, 9, 20), 100)
        self.assertEqual(got, {"threshold": 100, "days": 2, "reached_on": "2026-09-22"})

    def test_reached_on_the_publish_day(self):
        from analytics.view_curve import days_to_views

        got = days_to_views([["2026-09-20", 150]], date(2026, 9, 20), 100)
        self.assertEqual(got["days"], 0)

    def test_never_reached(self):
        from analytics.view_curve import days_to_views

        self.assertIsNone(days_to_views([["2026-09-20", 10]], date(2026, 9, 20), 100))

    def test_a_missing_day_counts_as_none_and_days_before_publish_are_ignored(self):
        from analytics.view_curve import days_to_views

        daily = [["2026-09-19", 500], ["2026-09-20", 60], ["2026-09-23", 60]]
        self.assertEqual(days_to_views(daily, date(2026, 9, 20), 100)["days"], 3)

    def test_a_series_that_starts_after_publish_says_nothing(self):
        from analytics.view_curve import days_to_views

        self.assertIsNone(days_to_views([["2026-09-22", 500]], date(2026, 9, 20), 100))

    def test_merge_is_a_union_by_day(self):
        from analytics.view_curve import merge_daily

        old = [["2026-08-30", 5], ["2026-08-31", 7]]
        new = [["2026-08-31", 9], ["2026-09-01", 3]]
        self.assertEqual(
            merge_daily(old, new), [["2026-08-30", 5], ["2026-08-31", 9], ["2026-09-01", 3]]
        )


class SnapshotTests(unittest.TestCase):
    def test_it_is_frozen_once_reached(self):
        from analytics.youtube_metrics import merge_metric_snapshots

        first = merge_metric_snapshots(
            {}, {"views": 120, "daily_views": [["2026-09-20", 30], ["2026-09-21", 90]]},
            published_at=PUBLISHED, now=datetime(2026, 9, 23, tzinfo=timezone.utc),
        )  # fmt: skip
        self.assertEqual(first["first_views"]["days"], 1)
        # A later sync whose window no longer starts at publish keeps the frozen answer.
        later = merge_metric_snapshots(
            first, {"views": 900, "daily_views": [["2026-10-15", 3]]},
            published_at=PUBLISHED, now=datetime(2026, 10, 20, tzinfo=timezone.utc),
        )  # fmt: skip
        self.assertEqual(later["first_views"]["days"], 1)
        self.assertIn(["2026-09-21", 90], later["daily_views"])

    def test_the_threshold_can_be_set(self):
        from analytics.youtube_metrics import merge_metric_snapshots

        with patch.dict(os.environ, {"FIRST_VIEWS_THRESHOLD": "20"}):
            got = merge_metric_snapshots(
                {}, {"daily_views": [["2026-09-20", 30]]}, published_at=PUBLISHED
            )
        self.assertEqual(
            got["first_views"], {"threshold": 20, "days": 0, "reached_on": "2026-09-20"}
        )


class FetchTests(unittest.TestCase):
    def _service(self, day_rows):
        service = MagicMock()

        def query(**kwargs):
            call = MagicMock()
            if kwargs.get("dimensions") == "day":
                call.execute.return_value = {"rows": day_rows}
            elif kwargs.get("dimensions") == "video":
                call.execute.return_value = {
                    "columnHeaders": [{"name": "video"}, {"name": "views"}],
                    "rows": [["vid", 130]],
                }
            else:
                call.execute.return_value = {"rows": []}
            return call

        service.reports.return_value.query.side_effect = query
        return service

    def test_the_sync_asks_for_views_by_day(self):
        from analytics import youtube_metrics

        service = self._service([["2026-09-20", 60], ["2026-09-21", 70]])
        with (
            patch.dict(os.environ, {"YOUTUBE_ANALYTICS_SYNC": "true"}),
            patch.object(youtube_metrics, "get_youtube_analytics_service", return_value=service),
            patch("requests.get", side_effect=AssertionError("network")),
        ):
            got = youtube_metrics.fetch_video_metrics("vid", channel_id="tapin")
        self.assertEqual(got["daily_views"], [["2026-09-20", 60], ["2026-09-21", 70]])

    def test_a_failed_day_query_is_skipped(self):
        from analytics import youtube_metrics

        service = self._service([])
        with (
            patch.dict(os.environ, {"YOUTUBE_ANALYTICS_SYNC": "true"}),
            patch.object(youtube_metrics, "get_youtube_analytics_service", return_value=service),
        ):
            got = youtube_metrics.fetch_video_metrics("vid", channel_id="tapin")
        self.assertNotIn("daily_views", got)


class ReportTests(unittest.TestCase):
    def _logs(self, pairs):
        return [
            SimpleNamespace(
                content_run_id=i, metrics_json=json.dumps(
                    {"engaged_rate": rate, **({"first_views": {"days": d}} if d is not None else {})}
                ),
            )
            for i, (d, rate) in enumerate(pairs, 1)
        ]  # fmt: skip

    def _line(self, pairs):
        from analytics.view_curve import report_line

        with patch(
            "storage.repositories.publish_log.get_publish_log_repository",
            return_value=SimpleNamespace(list_timed_outcomes=lambda c: self._logs(pairs)),
        ):
            return report_line("tapin")

    def test_collecting_under_five(self):
        self.assertIn("collecting (n=2", self._line([(1, 0.3), (2, 0.2)]))

    def test_median_and_correlation(self):
        line = self._line([(0, 0.5), (1, 0.4), (2, 0.3), (3, 0.2), (5, 0.1), (None, 0.1)])
        self.assertIn("median 2 day(s)", line)
        self.assertIn("r=-", line)
        self.assertIn("1 not there yet", line)

    def test_ops_predictions_prints_it(self):
        from core.predictions import ledger

        with patch("analytics.view_curve.report_line", return_value="  time to 100 views: x"):
            with patch.object(ledger, "ledger_rows", return_value=[]):
                self.assertIn("  time to 100 views: x", ledger.report_lines("tapin"))


class BackfillTests(unittest.TestCase):
    def test_the_registry_has_it_and_a_dry_run_makes_no_call(self):
        from analytics import backfills

        entry = backfills.get_backfill("view-curve")
        row = SimpleNamespace(
            id=1, content_run_id=7, youtube_video_id="vid", published_at=PUBLISHED,
            metrics_json="{}",
        )  # fmt: skip
        with (
            patch("storage.repositories.publish_log.get_publish_log_repository") as repo,
            patch("analytics.youtube_metrics.fetch_daily_views") as fetch,
        ):
            repo.return_value.list_timed_outcomes.return_value = [row]
            tally = entry.run("tapin", False, False)
        fetch.assert_not_called()
        self.assertEqual(tally["would_update"], 1)

    def test_apply_fetches_from_the_publish_day(self):
        from analytics import backfills

        row = SimpleNamespace(
            id=1, content_run_id=7, youtube_video_id="vid", published_at=PUBLISHED,
            metrics_json='{"views": 300}',
        )  # fmt: skip
        with (
            patch("storage.repositories.publish_log.get_publish_log_repository") as repo,
            patch(
                "analytics.youtube_metrics.fetch_daily_views",
                return_value=[["2026-09-20", 80], ["2026-09-21", 40]],
            ) as fetch,
        ):
            repo.return_value.list_timed_outcomes.return_value = [row]
            tally = backfills.get_backfill("view-curve").run("tapin", True, False)
        self.assertEqual(fetch.call_args.kwargs["start"], "2026-09-20")
        saved = json.loads(repo.return_value.update.call_args.args[1]["metrics_json"])
        self.assertEqual(saved["first_views"]["days"], 1)
        self.assertEqual(saved["views"], 300)
        self.assertEqual(tally["updated"], 1)


if __name__ == "__main__":
    unittest.main()
