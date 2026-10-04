"""#951 (with #948): judge titles and thumbnails on what YouTube reports for the feed.

The sync read neither impressions nor click-through, so a title or thumbnail could not be judged
on what it controls. #948 said to add `impressions` / `impressionClickThroughRate` to the
Analytics query - the Analytics API has no such metrics. YouTube put them in the Reporting API
(bulk reports) on 2026-01-15: `channel_reach_basic_a1` gives date, channel_id, video_id,
`video_thumbnail_impressions` and `video_thumbnail_impressions_ctr` per day, one CSV a day once
a job exists.

The Shorts feed shows no thumbnail. Since 2025-03-31 a Shorts "view" counts every start or
replay and `engagedViews` keeps the old counting, so engagedViews / views is the share of starts
that were not swiped away ("stayed"); the Shorts-feed share of organic views comes from #954's
traffic sources.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

CSV = (
    "date,channel_id,video_id,video_thumbnail_impressions,video_thumbnail_impressions_ctr\n"
    "20261001,UC1,long1,1000,0.05\n"
    "20261001,UC1,long2,200,0.01\n"
)
CSV_2 = (
    "date,channel_id,video_id,video_thumbnail_impressions,video_thumbnail_impressions_ctr\n"
    "20261002,UC1,long1,3000,0.03\n"
)


class _Service:
    """A fake Reporting API service: jobs, reports and nothing on the network."""

    def __init__(self, jobs=None, reports=None):
        self._jobs = list(jobs or [])
        self._reports = list(reports or [])
        self.created: list[dict] = []
        self.listed: list[dict] = []

    def jobs(self):
        return self

    def list(self, **kw):
        self._call = ("list", kw)
        return self

    def create(self, body):
        self._call = ("create", body)
        return self

    def reports(self):
        outer = self

        class _Reports:
            def list(self, **kw):
                outer.listed.append(kw)
                outer._call = ("reports", kw)
                return outer

        return _Reports()

    def execute(self):
        kind, arg = self._call
        if kind == "list":
            return {"jobs": self._jobs}
        if kind == "create":
            self.created.append(arg)
            return {"id": "job-new", "reportTypeId": arg["reportTypeId"]}
        return {"reports": self._reports}


class _Stores(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        d = self._tmp.name
        self._patches = [
            patch("analytics.reach_report.REACH_TEMPLATE", os.path.join(d, "reach_{channel}.json")),
            patch("storage.repositories.publish_log.LOG_FILE", os.path.join(d, "publish_log.json")),
            patch(
                "core.success.goals.CHANNEL_VIEWS_TEMPLATE",
                os.path.join(d, "channel_views_{channel}.json"),
            ),
            patch("core.success.goals.GOALS_FILE", os.path.join(d, "goals.json")),
            patch("core.success.goals.FOCUS_FILE", os.path.join(d, "focus.json")),
            patch("core.success.goals.HISTORY_TEMPLATE", os.path.join(d, "hist_{channel}.json")),
        ]
        for p in self._patches:
            p.start()
        self.goals = os.path.join(d, "goals.json")

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        self._tmp.cleanup()

    def _video(self, vid, title, metrics, day=date(2026, 10, 1)):
        from storage.repositories.publish_log import get_publish_log_repository

        get_publish_log_repository().create(
            {
                "channel_id": "tapin",
                "youtube_video_id": vid,
                "status": "uploaded",
                "detail": title,
                "metrics_json": json.dumps(metrics),
                "published_at": datetime(day.year, day.month, day.day, 18, tzinfo=timezone.utc),
            }
        )


class EngagedViewsTests(unittest.TestCase):
    def test_engaged_views_are_their_own_best_effort_query(self):
        from analytics.youtube_metrics import _fetch_engaged_views

        class Service:
            def reports(self):
                return self

            def query(self, **kw):
                self.kw = kw
                return self

            def execute(self):
                return {
                    "columnHeaders": [{"name": "video"}, {"name": "engagedViews"}],
                    "rows": [["s1", 620]],
                }

        service = Service()
        self.assertEqual(_fetch_engaged_views("s1", service, "a", "b"), 620)
        self.assertEqual(service.kw["metrics"], "engagedViews")

    def test_a_rejected_metric_never_breaks_the_sync(self):
        from analytics.youtube_metrics import _fetch_engaged_views

        class Service:
            def reports(self):
                return self

            def query(self, **kw):
                return self

            def execute(self):
                raise RuntimeError("Unknown identifier (engagedViews)")

        self.assertIsNone(_fetch_engaged_views("s1", Service(), "a", "b"))


class FiguresTests(unittest.TestCase):
    def test_a_shorts_figures(self):
        from analytics.packaging import packaging_figures

        figures = packaging_figures(
            {
                "views": 1000,
                "engaged_views": 620,
                "views_by_source": {
                    "SHORTS": 410,
                    "YT_SEARCH": 30,
                    "ADVERTISING": 500,
                    "SUBSCRIBER": 60,
                },
            }
        )
        self.assertAlmostEqual(figures["stayed"], 0.62)
        self.assertAlmostEqual(figures["feed"], 0.82)  # 410 of 500 organic
        self.assertAlmostEqual(figures["search"], 0.06)
        self.assertTrue(figures["short"])

    def test_a_long_form_figures(self):
        from analytics.packaging import packaging_figures

        figures = packaging_figures(
            {
                "views": 542,
                "engaged_views": 542,
                "views_by_source": {"YT_SEARCH": 300, "RELATED_VIDEO": 242},
                "thumbnail_impressions": 4000,
                "thumbnail_ctr": 0.035,
            }
        )
        self.assertFalse(figures["short"])
        self.assertNotIn("stayed", figures)
        self.assertEqual(figures["impressions"], 4000)
        self.assertAlmostEqual(figures["ctr"], 0.035)


class ReachReportTests(_Stores):
    def test_the_job_is_created_once(self):
        from analytics import reach_report

        service = _Service()
        self.assertEqual(reach_report.ensure_job(service, "tapin"), "job-new")
        self.assertEqual(service.created[0]["reportTypeId"], "channel_reach_basic_a1")
        self.assertEqual(reach_report.ensure_job(service, "tapin"), "job-new")
        self.assertEqual(len(service.created), 1)

    def test_an_existing_job_is_reused(self):
        from analytics import reach_report

        service = _Service(jobs=[{"id": "job-old", "reportTypeId": "channel_reach_basic_a1"}])
        self.assertEqual(reach_report.ensure_job(service, "tapin"), "job-old")
        self.assertEqual(service.created, [])

    def test_the_csv_reads_per_video_per_day(self):
        from analytics.reach_report import parse_reach_csv

        self.assertEqual(
            parse_reach_csv(CSV),
            {"long1": {"2026-10-01": [1000, 0.05]}, "long2": {"2026-10-01": [200, 0.01]}},
        )

    def test_each_daily_report_is_downloaded_once(self):
        from analytics import reach_report

        reports = [
            {"id": "r1", "startTime": "2026-10-01T07:00:00Z", "downloadUrl": "https://x/r1"},
            {"id": "r2", "startTime": "2026-10-02T07:00:00Z", "downloadUrl": "https://x/r2"},
        ]
        service = _Service(jobs=[{"id": "job-old", "reportTypeId": "channel_reach_basic_a1"}],
                           reports=reports)  # fmt: skip
        reach_report.ensure_job(service, "tapin")
        texts = {"https://x/r1": CSV, "https://x/r2": CSV_2}
        with patch.object(reach_report, "_download", side_effect=lambda s, url: texts[url]) as get:
            self.assertEqual(reach_report.download_new(service, "tapin"), 2)
            self.assertEqual(reach_report.download_new(service, "tapin"), 0)
        self.assertEqual(get.call_count, 2)
        reach = reach_report.reach_for("long1", reach_report.load("tapin"))
        self.assertEqual(reach["thumbnail_impressions"], 4000)
        self.assertAlmostEqual(reach["thumbnail_ctr"], (50 + 90) / 4000)

    def test_the_numbers_reach_the_videos(self):
        from analytics import reach_report
        from storage.repositories.publish_log import get_publish_log_repository

        self._video("long1", "Long video", {"views": 542})
        reach_report._save("tapin", {"videos": {"long1": {"2026-10-01": [1000, 0.05]}}})
        self.assertEqual(reach_report.merge_into_metrics("tapin"), 1)
        row = get_publish_log_repository().list_uploaded_for_channel("tapin")[0]
        metrics = json.loads(row.metrics_json)
        self.assertEqual(metrics["thumbnail_impressions"], 1000)
        self.assertAlmostEqual(metrics["thumbnail_ctr"], 0.05)
        self.assertEqual(metrics["views"], 542)

    def test_a_disabled_api_says_what_to_turn_on(self):
        from analytics import reach_report

        class Disabled(_Service):
            def execute(self):
                raise RuntimeError("accessNotConfigured: YouTube Reporting API has not been used")

        with patch("youtube.oauth.get_youtube_reporting_service", return_value=Disabled()):
            line = reach_report.sync_reach("tapin")
        self.assertIn("YouTube Reporting API", line)
        self.assertIn("enable", line.lower())

    def test_no_sign_in_is_silent(self):
        from analytics import reach_report

        with patch("youtube.oauth.get_youtube_reporting_service", return_value=None):
            self.assertEqual(reach_report.sync_reach("tapin"), "")


class PackagingReportTests(_Stores):
    def test_the_report_reads_shorts_and_long_form(self):
        from analytics import packaging

        self._video(
            "s1",
            "A Short",
            {
                "views": 1000,
                "engaged_views": 620,
                "views_by_source": {"SHORTS": 410, "YT_SEARCH": 30},
            },
        )
        self._video(
            "l1",
            "A long video",
            {"views": 542, "views_by_source": {"YT_SEARCH": 300},
             "thumbnail_impressions": 4000, "thumbnail_ctr": 0.035},
        )  # fmt: skip
        with patch("core.experiments.assignment_for_run", return_value=None):
            text = "\n".join(packaging.packaging_lines("tapin"))
        self.assertIn('"A Short"', text)
        self.assertIn("stayed 62%", text)
        self.assertIn("feed 93%", text)
        self.assertIn('"A long video"', text)
        self.assertIn("CTR 3.5%", text)
        self.assertIn("4,000 impressions", text)

    def test_nothing_yet_says_what_to_run(self):
        from analytics import packaging

        text = "\n".join(packaging.packaging_lines("tapin"))
        self.assertIn("sync-metrics", text)

    def test_the_command(self):
        from analytics import packaging
        from scripts.ops import COMMANDS

        self.assertIn("packaging", COMMANDS)
        with patch.object(packaging, "packaging_lines", return_value=["Packaging - x"]):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = COMMANDS["packaging"][1](Namespace(channel="tapin"))
        self.assertEqual(code, 0)
        self.assertIn("Packaging", buf.getvalue())

    def test_the_scoreboard_names_the_best_videos_packaging(self):
        from core.success.goals import scoreboard_lines

        with open(self.goals, "w", encoding="utf-8") as f:
            json.dump({"tapin": {"metric": "views", "target": 10000, "by": "2026-12-31"}}, f)
        self._video(
            "s1",
            "A Short",
            {"views": 1000, "engaged_views": 620, "views_by_source": {"SHORTS": 410}},
        )
        self._video("s2", "Another Short", {"views": 10, "engaged_views": 2})
        text = "\n".join(scoreboard_lines("tapin", today=date(2026, 10, 4)))
        self.assertIn('best: "A Short" 1,000 views (stayed 62%', text)


class SyncWiringTests(_Stores):
    def test_the_sync_collects_the_reach_reports(self):
        from analytics import sync_metrics

        buf = io.StringIO()
        with (
            patch.dict(os.environ, {"YOUTUBE_ANALYTICS_SYNC": "true"}),
            patch.object(sync_metrics, "_probe_analytics_api", return_value=(True, "")),
            patch.object(sync_metrics, "refresh_publish_metrics", return_value=None),
            patch("analytics.youtube_metrics.fetch_lifetime_views", return_value={}),
            patch("analytics.youtube_metrics.fetch_ypp_numbers", return_value=None),
            patch("core.success.goals.sync_channel_views", return_value=0),
            patch(
                "analytics.reach_report.sync_reach", return_value="  Click-through: 1 new"
            ) as reach,
            redirect_stdout(buf),
        ):
            sync_metrics.sync_channel("tapin")
        reach.assert_called_once_with("tapin")
        self.assertIn("Click-through", buf.getvalue())

    def test_the_metrics_sync_stores_engaged_views(self):
        from analytics import youtube_metrics

        class Service:
            def reports(self):
                return self

            def query(self, **kw):
                self.kw = kw
                return self

            def execute(self):
                if self.kw.get("metrics") == "engagedViews":
                    return {
                        "columnHeaders": [{"name": "video"}, {"name": "engagedViews"}],
                        "rows": [["s1", 620]],
                    }
                if self.kw.get("dimensions") == "video":
                    return {
                        "columnHeaders": [{"name": "video"}, {"name": "views"}],
                        "rows": [["s1", 1000]],
                    }
                return {}

        with (
            patch.object(youtube_metrics, "_analytics_enabled", return_value=True),
            patch.object(youtube_metrics, "get_youtube_analytics_service", return_value=Service()),
        ):
            metrics = youtube_metrics.fetch_video_metrics("s1", channel_id="tapin")
        self.assertEqual(metrics["engaged_views"], 620)
        self.assertAlmostEqual(metrics["stayed_share"], 0.62)


class ReportingServiceTests(unittest.TestCase):
    def test_the_reporting_client_is_forbidden_in_the_suite(self):
        from youtube.oauth import get_youtube_reporting_service

        with patch.dict(os.environ, {"CONTENT_FORBID_LIVE_YOUTUBE": "1"}):
            self.assertIsNone(get_youtube_reporting_service("tapin"))


if __name__ == "__main__":
    unittest.main()
