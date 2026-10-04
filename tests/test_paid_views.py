"""#954: paid views apart from organic, everywhere the system learns. #947 rides along.

The operator's Studio screenshots (2026-10-04): 76.3% of the last 28 days' views came from
"YouTube advertising" - the first $10 campaign - and Shorts drew 4.2K views and 0 subscribers.
Every number the system learned from counted those views: the sync's `views` and
`daily_views`, the 7-day target, `comparable_views`, winners, the scoreboard's pace and the YPP
check. A boosted video read as a winner and best bet would chase its topic; YouTube says
promotion views, watch time and subscribers do not count toward YPP.

Now the sync asks for views by day and traffic source (one Analytics query per video) and keeps
the ADVERTISING days as `daily_paid_views`; everything that ranks or paces reads organic. The
YPP check reads YouTube's own channel numbers with ads excluded, Shorts views over 90 days and
long-form watch hours over 12 months, plus subscribers.

#947: the view-curve backfill called a video stale while `first_views` was missing, so a video
that never reached 100 views was fetched again on every `ops all`. Stale now means the fetched
days do not cover the first 7, or the paid series is missing.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

TODAY = date(2026, 10, 4)


def _at(day: date, hour: int = 18) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)


def _days(start: date, values: list[int]) -> list[list]:
    return [[(start + timedelta(days=i)).isoformat(), v] for i, v in enumerate(values)]


class _FakeReports:
    """`service.reports().query(**kw).execute()` answering by the query's dimensions."""

    def __init__(self, answers):
        self.answers = answers
        self.queries: list[dict] = []

    def reports(self):
        return self

    def query(self, **kw):
        self.queries.append(kw)
        self._last = kw
        return self

    def execute(self):
        answer = self.answers.get(self._last.get("dimensions"))
        if isinstance(answer, Exception):
            raise answer
        return answer or {}


SOURCE_DAY = {
    "columnHeaders": [{"name": "day"}, {"name": "insightTrafficSourceType"}, {"name": "views"}],
    "rows": [
        ["2026-09-10", "ADVERTISING", 3000],
        ["2026-09-10", "SHORTS", 50],
        ["2026-09-11", "ADVERTISING", 700],
        ["2026-09-11", "YT_SEARCH", 10],
    ],
}


class FetchTests(unittest.TestCase):
    def test_paid_days_and_sources_come_from_one_query(self):
        from analytics.youtube_metrics import _fetch_views_by_source_day

        service = _FakeReports({"day,insightTrafficSourceType": SOURCE_DAY})
        paid, sources = _fetch_views_by_source_day("vid1", service, "2026-09-06", "2026-10-04")
        self.assertEqual(paid, [["2026-09-10", 3000], ["2026-09-11", 700]])
        self.assertEqual(sources, {"ADVERTISING": 3700, "SHORTS": 50, "YT_SEARCH": 10})
        self.assertEqual(service.queries[0]["filters"], "video==vid1")

    def test_a_failed_query_is_none(self):
        from analytics.youtube_metrics import _fetch_views_by_source_day

        service = _FakeReports({"day,insightTrafficSourceType": RuntimeError("quota")})
        self.assertIsNone(_fetch_views_by_source_day("vid1", service, "a", "b"))

    def test_the_sync_stores_the_paid_series_and_what_it_covered(self):
        from analytics import youtube_metrics

        service = _FakeReports(
            {
                "video": {
                    "columnHeaders": [{"name": "video"}, {"name": "views"}],
                    "rows": [["vid1", 3760]],
                },
                "day,insightTrafficSourceType": SOURCE_DAY,
            }
        )
        with (
            patch.object(youtube_metrics, "_analytics_enabled", return_value=True),
            patch.object(youtube_metrics, "get_youtube_analytics_service", return_value=service),
            patch.object(youtube_metrics, "_date_range", return_value=("2026-09-06", "2026-10-04")),
        ):
            metrics = youtube_metrics.fetch_video_metrics("vid1", channel_id="tapin")
        self.assertEqual(metrics["daily_paid_views"], [["2026-09-10", 3000], ["2026-09-11", 700]])
        self.assertEqual(metrics["paid_views"], 3700)
        self.assertEqual(metrics["views_by_source"]["SHORTS"], 50)
        self.assertEqual(metrics["paid_since"], "2026-09-06")
        self.assertEqual(metrics["views_since"], "2026-09-06")


class TargetTests(unittest.TestCase):
    PUBLISHED = _at(date(2026, 9, 10))

    def _metrics(self, paid=True):
        metrics = {"daily_views": _days(date(2026, 9, 10), [1000, 1000, 900, 500, 200, 100, 100])}
        if paid:
            metrics["daily_paid_views"] = _days(
                date(2026, 9, 10), [1000, 950, 880, 480, 190, 100, 100]
            )
            metrics["paid_since"] = "2026-09-01"
        return metrics

    def test_seven_day_views_are_organic(self):
        from core.success.target import views_7d

        self.assertEqual(views_7d(self._metrics(), self.PUBLISHED), 100)

    def test_no_paid_series_yet_counts_none_as_paid(self):
        """Rows synced before #954 carry no paid series until the backfill fetches it."""
        from core.success.target import views_7d

        self.assertEqual(views_7d(self._metrics(paid=False), self.PUBLISHED), 3800)

    def test_the_target_ranks_on_organic_views(self):
        import math

        from core.success.target import TARGET_VIEWS, outcome

        value = outcome(json.dumps(self._metrics()), self.PUBLISHED, target_name=TARGET_VIEWS)
        self.assertAlmostEqual(value, math.log1p(100))


class MergeTests(unittest.TestCase):
    def test_a_later_sync_keeps_the_paid_series_and_the_widest_coverage(self):
        from analytics.view_curve import merge_view_curve

        existing = {
            "daily_views": [["2026-09-10", 1000]],
            "daily_paid_views": [["2026-09-10", 1000]],
            "paid_since": "2026-09-10",
            "views_since": "2026-09-10",
            "views_until": "2026-10-01",
        }
        fresh = {
            "daily_views": [["2026-10-02", 5]],
            "daily_paid_views": [],
            "paid_since": "2026-09-20",
            "views_since": "2026-09-20",
            "views_until": "2026-10-04",
        }
        merged = merge_view_curve(existing, dict(fresh), _at(date(2026, 9, 10)))
        self.assertEqual(merged["daily_paid_views"], [["2026-09-10", 1000]])
        self.assertEqual(merged["paid_since"], "2026-09-10")
        self.assertEqual(merged["views_since"], "2026-09-10")
        self.assertEqual(merged["views_until"], "2026-10-04")

    def test_a_sync_without_the_paid_query_keeps_what_was_there(self):
        from analytics.view_curve import merge_view_curve

        existing = {"daily_paid_views": [["2026-09-10", 7]], "paid_since": "2026-09-01"}
        merged = merge_view_curve(existing, {"daily_views": []}, _at(date(2026, 9, 10)))
        self.assertEqual(merged["daily_paid_views"], [["2026-09-10", 7]])
        self.assertEqual(merged["paid_since"], "2026-09-01")


class StaleTests(unittest.TestCase):
    """#947 with #954's paid series."""

    def _row(self, metrics, published=date(2026, 9, 1)):
        return SimpleNamespace(
            id=1,
            youtube_video_id="vid1",
            published_at=_at(published),
            metrics_json=json.dumps(metrics),
        )

    def _stale(self, row):
        from analytics import view_curve

        with patch.object(view_curve, "_today", return_value=TODAY):
            return view_curve._needs_curve(row)

    def test_a_small_video_with_its_first_week_is_not_stale(self):
        """Never reached 100 views, so no `first_views` - and nothing left to fetch."""
        metrics = {
            "daily_views": _days(date(2026, 9, 1), [3, 2, 1, 0, 4, 1, 2, 1]),
            "daily_paid_views": [],
            "paid_since": "2026-09-01",
            "views_since": "2026-09-01",
            "views_until": "2026-09-29",
        }
        self.assertFalse(self._stale(self._row(metrics)))

    def test_no_paid_series_is_stale(self):
        metrics = {
            "daily_views": _days(date(2026, 9, 1), [3] * 8),
            "first_views": {"days": 2},
        }
        self.assertTrue(self._stale(self._row(metrics)))

    def test_a_series_that_starts_late_is_stale(self):
        metrics = {
            "daily_views": _days(date(2026, 9, 6), [3] * 20),
            "daily_paid_views": [],
            "paid_since": "2026-09-06",
            "views_since": "2026-09-06",
            "views_until": "2026-10-04",
        }
        self.assertTrue(self._stale(self._row(metrics)))

    def test_a_video_under_a_week_old_is_left_to_the_sync(self):
        self.assertFalse(self._stale(self._row({}, published=TODAY - timedelta(days=3))))

    def test_the_backfill_fetches_the_paid_series_from_the_publish_day(self):
        from analytics import view_curve

        row = self._row({"daily_views": _days(date(2026, 9, 1), [3] * 8)})
        stored = {}
        repo = SimpleNamespace(
            list_timed_outcomes=lambda cid: [row],
            update=lambda rid, data: stored.update(data),
        )
        with (
            patch.object(view_curve, "_today", return_value=TODAY),
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=repo),
            patch(
                "analytics.youtube_metrics.fetch_daily_views",
                return_value=_days(date(2026, 9, 1), [3] * 29),
            ),
            patch(
                "analytics.youtube_metrics.fetch_daily_paid_views",
                return_value=[["2026-09-02", 2]],
            ),
        ):
            result = view_curve.backfill("tapin", apply=True, force=False)
        self.assertEqual(result["updated"], 1)
        metrics = json.loads(stored["metrics_json"])
        self.assertEqual(metrics["daily_paid_views"], [["2026-09-02", 2]])
        self.assertEqual(metrics["paid_since"], "2026-09-01")
        self.assertEqual(metrics["views_since"], "2026-09-01")
        row.metrics_json = stored["metrics_json"]
        self.assertFalse(self._stale(row))


class _Log(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        d = self._tmp.name
        self._patches = [
            patch("storage.repositories.publish_log.LOG_FILE", os.path.join(d, "publish_log.json")),
            patch(
                "core.success.goals.CHANNEL_VIEWS_TEMPLATE",
                os.path.join(d, "channel_views_{channel}.json"),
            ),
            patch("core.success.goals.GOALS_FILE", os.path.join(d, "goals.json")),
            patch("core.success.goals.FOCUS_FILE", os.path.join(d, "focus.json")),
            patch("core.success.goals.HISTORY_TEMPLATE", os.path.join(d, "hist_{channel}.json")),
            patch("core.ypp_readiness.YPP_TEMPLATE", os.path.join(d, "ypp_{channel}.json")),
        ]
        for p in self._patches:
            p.start()
        self.goals = os.path.join(d, "goals.json")

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        self._tmp.cleanup()

    def _video(self, vid, title, day, daily, paid=None, *, views=None):
        from storage.repositories.publish_log import get_publish_log_repository

        metrics = {
            "views": views if views is not None else sum(v for _d, v in daily),
            "engaged_rate": 0.4,
            "daily_views": daily,
            "daily_paid_views": paid or [],
            "paid_views": sum(v for _d, v in paid or []),
            "paid_since": day.isoformat(),
        }
        get_publish_log_repository().create(
            {
                "channel_id": "tapin",
                "youtube_video_id": vid,
                "status": "uploaded",
                "detail": title,
                "metrics_json": json.dumps(metrics),
                "published_at": _at(day),
            }
        )


class RankingTests(_Log):
    def _library(self):
        start = date(2026, 9, 10)
        self._video(
            "boost",
            "Boosted",
            start,
            _days(start, [1000, 1000, 900, 500, 200, 100, 100]),
            _days(start, [1000, 950, 880, 480, 190, 100, 100]),
        )
        self._video("org", "Organic", start, _days(start, [100, 80, 60, 60, 40, 30, 30]))
        for i in range(6):
            day = start - timedelta(days=i + 1)
            self._video(f"v{i}", f"Video {i}", day, _days(day, [20 + i] * 7))

    def test_a_boosted_video_ranks_on_its_organic_views(self):
        from core.success.videos import channel_videos, comparable_views

        self._library()
        ranked, heading, _unit = comparable_views(channel_videos("tapin"))
        self.assertIn("7 days", heading)
        self.assertEqual(ranked[0][0].title, "Organic")
        boosted = next(value for v, value in ranked if v.title == "Boosted")
        self.assertEqual(boosted, 100)

    def test_the_video_knows_its_paid_views(self):
        from core.success.videos import channel_videos

        self._library()
        video = next(v for v in channel_videos("tapin") if v.title == "Boosted")
        self.assertEqual(video.paid_views, 3700)
        self.assertEqual(video.organic_views, 100)

    def test_winners_say_which_views_were_paid(self):
        from core.success import winners

        self._library()
        with patch.object(winners, "_features", return_value={}):
            lines = winners.winners_lines("tapin")
            block = winners.winners_block("tapin")
        text = "\n".join(lines)
        self.assertIn("Organic", lines[1])
        self.assertIn("3,700 paid", text)
        self.assertNotIn("paid", block)


class ScoreboardTests(_Log):
    def test_the_scoreboard_counts_organic_and_names_paid(self):
        from core.success.goals import save_channel_paid_views, save_channel_views, scoreboard_lines

        with open(self.goals, "w", encoding="utf-8") as f:
            json.dump(
                {"tapin": {"metric": "views", "target": 10000, "since": "2026-09-01",
                           "by": "2026-12-31"}},
                f,
            )  # fmt: skip
        save_channel_views("tapin", _days(date(2026, 9, 1), [100] * 33))
        save_channel_paid_views("tapin", [["2026-09-10", 60], ["2026-09-11", 40]])
        text = "\n".join(scoreboard_lines("tapin", today=TODAY))
        self.assertIn("so far: 3,200 views", text)
        self.assertIn("+100 paid, not counted", text)


class YppTests(_Log):
    def test_youtube_numbers_with_ads_excluded(self):
        from core.ypp_readiness import inspect_ypp, save_ypp_numbers

        save_ypp_numbers(
            "tapin",
            {
                "as_of": "2026-10-04",
                "shorts_views_90d": 1104,
                "long_hours_365d": 41.2,
                "subscribers": 37,
            },
        )
        report = inspect_ypp("tapin", disclosure="d", cadence=SimpleNamespace(total=0, cap=5))
        check = next(c for c in report.checks if c.name == "ypp_threshold")
        self.assertFalse(check.ok)
        self.assertIn("37/1,000 subscribers", check.detail)
        self.assertIn("ads excluded", check.detail)
        self.assertIn("1,104", check.detail)

    def test_enough_hours_without_subscribers_is_not_ready(self):
        from core.ypp_readiness import inspect_ypp

        report = inspect_ypp(
            "tapin",
            disclosure="d",
            cadence=SimpleNamespace(total=0, cap=5),
            numbers={"shorts_views_90d": 0, "long_hours_365d": 4200.0, "subscribers": 640},
        )
        check = next(c for c in report.checks if c.name == "ypp_threshold")
        self.assertFalse(check.ok)

    def test_the_estimate_uses_watch_minutes_and_leaves_ads_out(self):
        from core.ypp_readiness import inspect_ypp

        report = inspect_ypp(
            "tapin",
            metrics_rows=[{"views": 3800, "paid_views": 3700, "estimated_minutes_watched": 120.0}],
            disclosure="d",
            cadence=SimpleNamespace(total=0, cap=5),
        )
        check = next(c for c in report.checks if c.name == "ypp_threshold")
        self.assertIn("100 Shorts views", check.detail)
        self.assertIn("~2h", check.detail)
        self.assertIn("estimate", check.detail)

    def test_the_numbers_fetch_leaves_out_ads_and_shorts_minutes(self):
        from analytics import youtube_metrics

        views = {
            "columnHeaders": [
                {"name": "insightTrafficSourceType"},
                {"name": "creatorContentType"},
                {"name": "views"},
            ],
            "rows": [
                ["ADVERTISING", "SHORTS", 3700],
                ["SHORTS", "SHORTS", 900],
                ["YT_SEARCH", "SHORTS", 204],
                ["YT_SEARCH", "VIDEO_ON_DEMAND", 542],
            ],
        }
        minutes = {
            "columnHeaders": [
                {"name": "insightTrafficSourceType"},
                {"name": "creatorContentType"},
                {"name": "estimatedMinutesWatched"},
            ],
            "rows": [
                ["ADVERTISING", "VIDEO_ON_DEMAND", 6000],
                ["YT_SEARCH", "VIDEO_ON_DEMAND", 1800],
                ["SHORTS", "SHORTS", 900],
                ["SUBSCRIBER", "LIVE_STREAM", 600],
            ],
        }

        class Service(_FakeReports):
            def execute(self):
                return minutes if self._last["metrics"] == "estimatedMinutesWatched" else views

        with (
            patch.object(youtube_metrics, "_analytics_enabled", return_value=True),
            patch.object(
                youtube_metrics, "get_youtube_analytics_service", return_value=Service({})
            ),
            patch.object(youtube_metrics, "_subscriber_count", return_value=37),
        ):
            numbers = youtube_metrics.fetch_ypp_numbers(channel_id="tapin", today=TODAY)
        self.assertEqual(numbers["shorts_views_90d"], 1104)
        self.assertEqual(numbers["shorts_paid_90d"], 3700)
        self.assertEqual(numbers["long_hours_365d"], 40.0)
        self.assertEqual(numbers["subscribers"], 37)


class SyncWiringTests(_Log):
    def test_the_sync_stores_youtubes_ypp_numbers(self):
        import io
        from contextlib import redirect_stdout

        from analytics import sync_metrics
        from core.ypp_readiness import load_ypp_numbers

        numbers = {"as_of": "2026-10-04", "shorts_views_90d": 1104, "subscribers": 37}
        buf = io.StringIO()
        with (
            patch.dict(os.environ, {"YOUTUBE_ANALYTICS_SYNC": "true"}),
            patch.object(sync_metrics, "_probe_analytics_api", return_value=(True, "")),
            patch.object(sync_metrics, "refresh_publish_metrics", return_value=None),
            patch("analytics.youtube_metrics.fetch_lifetime_views", return_value={}),
            patch("core.success.goals.sync_channel_views", return_value=0),
            patch("analytics.youtube_metrics.fetch_ypp_numbers", return_value=numbers),
            redirect_stdout(buf),
        ):
            sync_metrics.sync_channel("tapin")
        self.assertEqual(load_ypp_numbers("tapin"), numbers)
        self.assertIn("ads excluded", buf.getvalue())

    def test_the_channel_sync_keeps_the_paid_days(self):
        from core.success.goals import channel_paid_daily, sync_channel_views

        with (
            patch(
                "analytics.youtube_metrics.fetch_channel_daily_views",
                return_value=[["2026-10-01", 50]],
            ),
            patch("analytics.youtube_metrics.fetch_channel_uploads", return_value=None),
            patch(
                "analytics.youtube_metrics.fetch_channel_paid_daily_views",
                return_value=[["2026-10-01", 20]],
            ),
        ):
            sync_channel_views("tapin", today=TODAY)
        self.assertEqual(channel_paid_daily("tapin"), {date(2026, 10, 1): 20})


class LearningMemoryTests(unittest.TestCase):
    def test_performance_memory_gets_organic_views(self):
        from analytics import youtube_metrics

        fetched = {"views": 3800, "paid_views": 3700, "engaged_rate": 0.3, "likes": 4}
        repo = SimpleNamespace(
            list_uploaded_for_channel=lambda cid: [],
            find_by_idempotency=lambda key: None,
            update=lambda *a, **k: None,
        )
        with (
            patch.object(youtube_metrics, "fetch_video_metrics", return_value=fetched),
            patch.object(youtube_metrics, "get_publish_log_repository", return_value=repo),
            patch.object(youtube_metrics, "record_publish_outcome") as record,
        ):
            youtube_metrics.refresh_publish_metrics(
                content_run_id=5, youtube_video_id="vid1", channel_id="tapin", title="t"
            )
        self.assertEqual(record.call_args.kwargs["views"], 100)


if __name__ == "__main__":
    unittest.main()
