"""Wave 141 (2026-11-01) - the next five (decision 93), S01 the shortfall it takes.

#1944 (S01) where a long video's views come from - by traffic source, with minutes; #1929 the
Cyber Monday deals long video, drafted Sat Nov 28; #1942 a false hand post left on the
operator's word says so, and S10 stops counting it; #1934 (S09) the privacy sync keeps how many
records it corrected a day; #1935 (S15) a pass mark - the menu within 15 points of the views -
and three gaming ideas in five while gaming leads.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests.test_organic_engaged import VIDEO, _Fake

NOW = datetime(2026, 11, 1, 18, 0, tzinfo=timezone.utc)


# ---- #1944 (S01): where long views come from ------------------------------------------------------

LONG_DAY = {
    "columnHeaders": [{"name": "day"}, {"name": "insightTrafficSourceType"}, {"name": "views"}],
    "rows": [["2026-10-22", "YT_SEARCH", 30], ["2026-10-23", "RELATED_VIDEO", 10]],
}
LONG_WATCH = {
    "columnHeaders": [{"name": "insightTrafficSourceType"}, {"name": "views"},
                      {"name": "estimatedMinutesWatched"}],
    "rows": [["YT_SEARCH", 30, 90.0], ["RELATED_VIDEO", 10, 20.0]],
}  # fmt: skip


def _row(run_id, metrics, *, privacy="public"):
    return SimpleNamespace(content_run_id=run_id, privacy_status=privacy, youtube_video_id=f"v{run_id}",
                           metrics_json=json.dumps(metrics), published_at=NOW - timedelta(days=5))  # fmt: skip


def _run(run_id, features):
    return SimpleNamespace(id=run_id, features_json=json.dumps(features))


class LongSourcesTests(unittest.TestCase):
    def _fetch(self, answers):
        from analytics import youtube_metrics

        service = _Fake(answers)
        with (
            patch.object(youtube_metrics, "_analytics_enabled", return_value=True),
            patch.object(youtube_metrics, "get_youtube_analytics_service", return_value=service),
            patch.object(youtube_metrics, "_date_range", return_value=("2026-10-04", "2026-11-01")),
        ):
            return youtube_metrics.fetch_video_metrics("vid1", channel_id="tapin")

    def test_a_video_off_the_shorts_feed_keeps_minutes_by_source(self):
        metrics = self._fetch({"video": VIDEO, "day,insightTrafficSourceType": LONG_DAY,
                               "insightTrafficSourceType": LONG_WATCH})  # fmt: skip
        self.assertEqual(metrics["minutes_by_source"], {"YT_SEARCH": 90.0, "RELATED_VIDEO": 20.0})
        self.assertNotIn("organic_engaged_rate", metrics)  # nothing paid

    def _line(self, rows, runs):
        from core.success import scorecard

        repo = MagicMock()
        repo.list_uploaded_for_channel.return_value = rows
        runs_repo = MagicMock()
        runs_repo.get.side_effect = lambda rid: runs.get(int(rid))
        with (
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=repo),
            patch("storage.repositories.content_runs.get_content_run_repository",
                  return_value=runs_repo),
        ):  # fmt: skip
            return scorecard.long_sources_line("tapin")

    def test_the_line_names_the_sources_of_long_views_only(self):
        rows = [
            _row(172, {"views": 4, "views_by_source": {"YT_SEARCH": 1, "YT_CHANNEL": 3},
                       "minutes_by_source": {"YT_SEARCH": 0.5, "YT_CHANNEL": 1.5}}),
            _row(202, {"lifetime_views": 0}),
            _row(215, {"views": 948, "views_by_source": {"SHORTS": 847, "YT_SEARCH": 11}}),
            _row(230, {"views": 50, "views_by_source": {"ADVERTISING": 40, "RELATED_VIDEO": 10}}),
        ]  # fmt: skip
        runs = {172: _run(172, {"compilation": {"week": "x"}}), 202: _run(202, {"compilation": {"week": "y"}}),
                215: _run(215, {}), 230: _run(230, {"long_form": True})}  # fmt: skip
        line = self._line(rows, runs)
        self.assertIn("channel page 3", line)
        self.assertIn("search 1", line)
        self.assertIn("suggested 10", line)
        self.assertNotIn("Shorts feed", line)  # run 215 is a Short
        self.assertNotIn("ADVERTISING", line)  # paid views are not a source here
        self.assertIn("14 organic views", line)
        self.assertIn("run 202", line)  # a long video nobody watched is named
        self.assertIn("3 long videos", line)

    def test_no_long_video_is_no_line(self):
        self.assertEqual(self._line([_row(215, {"views": 9})], {215: _run(215, {})}), "")

    def test_ops_ypp_and_s01_print_it(self):
        import inspect

        from core import ypp_readiness
        from core.success import shortfalls as sf

        self.assertIn("long_sources_line(", inspect.getsource(ypp_readiness))
        with (
            patch("core.success.scorecard.long_minutes", return_value=[0.4]),
            patch("core.success.scorecard.long_sources_line",
                  return_value="where long views came from: search 1"),
        ):  # fmt: skip
            got = sf.reading("S01", "tapin", now=NOW)
        self.assertIn("search 1", got.today)


# ---- #1929: the Cyber Monday deals long video ------------------------------------------------------


class CyberMondayTests(unittest.TestCase):
    def test_the_row_is_a_long_video_on_nov_28(self):
        from core.series.countdown import series_rows

        rows = {r["id"]: r for r in series_rows("tapin")}
        row = rows["cyber-monday-deals"]
        self.assertEqual((row["kind"], row["on"]), ("long", "2026-11-28"))
        self.assertIn("Cyber Monday", row["names"])

    def test_it_is_drafted_on_the_day_from_that_weeks_deal_headlines(self):
        from core.series import dated

        when = datetime(2026, 11, 27, 14, tzinfo=timezone.utc)
        lines = [{"title": "Cyber Monday 2026: the PS5 Pro and Switch 2 deals worth it", "source": "IGN",
                  "published": when}]  # fmt: skip
        with (
            patch.dict(os.environ, {"SERIES_DATED": "true"}),
            patch.object(dated, "channel_day", return_value=date(2026, 11, 28)),
            patch("core.batch_generation.series_drafted", return_value=False),
        ):
            ideas = dated.dated_ideas("tapin", now=datetime(2026, 11, 28, 15, tzinfo=timezone.utc),
                                      headlines=lambda *_a: list(lines))  # fmt: skip
        deals = [i for i in ideas if "Cyber Monday" in i.topic]
        self.assertEqual(len(deals), 1)
        self.assertEqual(deals[0].draft_kind, "long")

    def test_it_carries_up_to_three_links(self):
        from core.description_extras import affiliate_lines, is_deals

        self.assertTrue(is_deals("Cyber Monday 2026 gaming deals worth buying"))
        script = (
            "A PS5 bundle at its lowest, the Xbox Series X down too, and the Switch 2's first cut."
        )
        with patch.dict(os.environ, {"AFFILIATE_AMAZON_TAG": "tapin-20"}):
            got = affiliate_lines("tapin", "Cyber Monday 2026: the gaming deals worth buying",
                                  "Cyber Monday 2026 gaming deals worth buying", long_form=True,
                                  script=script)  # fmt: skip
        self.assertEqual(len([line for line in got if "tag=tapin-20" in line]), 3)


# ---- #1942: a false hand post left on your word ---------------------------------------------------


def _store():
    return {"posts": {
        "216": {"title": "GTA 6: 20 days to launch", "tiktok": {"state": "sent", "post_id": "P216"}},
        "220": {"title": "GTA 6: 19 days to launch",
                "tiktok": {"state": "manual", "post_id": "P216", "at": "2026-10-31T19:00:00+00:00"}},
    }}  # fmt: skip


class LeftOnYourWordTests(unittest.TestCase):
    def test_unclaim_marks_what_it_leaves(self):
        from publishing import crosspost

        data = _store()
        with (
            patch.object(crosspost, "_load", return_value=data),
            patch.object(crosspost, "_save") as save,
            patch.object(crosspost, "_public_times", return_value={}),
        ):
            lines = crosspost.unclaim("tapin", apply=True, now=NOW)
        self.assertTrue(any("left" in line for line in lines), lines)
        state = data["posts"]["220"]["tiktok"]
        self.assertIn("countdown", state["left"])
        save.assert_called_once()
        with (
            patch.object(crosspost, "_load", return_value=_store()),
            patch.object(crosspost, "_save") as dry,
            patch.object(crosspost, "_public_times", return_value={}),
        ):
            crosspost.unclaim("tapin", apply=False, now=NOW)
        dry.assert_not_called()

    def test_s10_does_not_count_one_you_left(self):
        from core.success import shortfalls as sf

        left = _store()
        left["posts"]["220"]["tiktok"]["left"] = "a countdown Short whose day has passed"
        with patch("publishing.crosspost._load", return_value=left):
            got = sf.reading("S10", "tapin", now=NOW)
        self.assertEqual(got.status, sf.MET)
        self.assertIn("1 left on your word", got.today)
        with patch("publishing.crosspost._load", return_value=_store()):
            self.assertEqual(sf.reading("S10", "tapin", now=NOW).status, sf.NOT_YET)


# ---- #1934 (S09): the privacy sync counts what it corrected --------------------------------------


class PrivacyCountTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        target = os.path.join(self.tmp.name, "privacy_sync.json")
        patcher = patch("config.paths.PRIVACY_SYNC_FILE", target)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_day_adds_up_and_reads_back(self):
        from analytics import privacy_sync as ps

        ps.record_corrections(2, day=date(2026, 10, 30))
        ps.record_corrections(1, day=date(2026, 10, 30))
        ps.record_corrections(0, day=date(2026, 10, 31))
        got = ps.corrections(days=14, today=date(2026, 11, 1))
        self.assertEqual(got, {"corrected": 3, "since": "2026-10-30", "days": 2})

    def _sync(self, apply):
        from analytics import privacy_sync as ps

        row = SimpleNamespace(id=1, content_run_id=5, youtube_video_id="v1", privacy_status="private",
                              published_at=NOW - timedelta(days=3))  # fmt: skip
        repo = MagicMock()
        repo.list_uploaded_for_channel.return_value = [row]
        with (
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=repo),
            patch("storage.repositories.publish_log.is_seeded", return_value=False),
            patch.object(ps, "fetch_status", return_value={"v1": {"privacy": "public"}}),
            patch.object(ps, "_publish_runs", return_value=[]),
            patch.object(ps, "_read_back_edits", return_value=[]),
        ):
            return ps.sync_privacy("tapin", service=object(), apply=apply)

    def test_an_applied_sync_records_its_corrections(self):
        from analytics import privacy_sync as ps

        self._sync(apply=False)
        self.assertEqual(ps.corrections(days=14)["corrected"], 0)
        report = self._sync(apply=True)
        self.assertEqual(len(report["changed"]), 1)
        self.assertEqual(ps.corrections(days=14)["corrected"], 1)

    def test_s09_reads_it(self):
        from core.success import shortfalls as sf

        with patch("analytics.privacy_sync.corrections",
                   return_value={"corrected": 2, "since": "2026-10-20", "days": 12}):  # fmt: skip
            self.assertEqual(sf.reading("S09", "tapin", now=NOW).status, sf.NOT_YET)
        with patch("analytics.privacy_sync.corrections",
                   return_value={"corrected": 0, "since": "2026-11-01", "days": 1}):  # fmt: skip
            got = sf.reading("S09", "tapin", now=NOW)
        self.assertEqual(got.status, sf.WAITING)
        self.assertIn("0 records corrected", got.today)
        with patch("analytics.privacy_sync.corrections",
                   return_value={"corrected": 0, "since": "2026-10-15", "days": 14}):  # fmt: skip
            self.assertEqual(sf.reading("S09", "tapin", now=NOW).status, sf.MET)


# ---- #1935 (S15): the menu against the views; three gaming ideas in five --------------------------


class MenuMixTests(unittest.TestCase):
    def test_three_gaming_ideas_of_five_while_gaming_leads(self):
        from core import best_bet

        self.assertEqual(best_bet.GAMING_FLOOR, 3)

    def test_s15_names_the_widest_gap(self):
        from core.success import shortfalls as sf

        offered = Counter(ufc=45, gaming=32, nba=26, nfl=17, soccer=11)
        views = {"gaming": 3878, "ufc": 754, "nba": 587, "nfl": 403, "soccer": 124}
        with (
            patch("core.predictions.ledger.menu_mix", return_value=(offered, Counter(), 30)),
            patch.object(sf, "_domain_views", return_value=views),
        ):
            got = sf.reading("S15", "tapin", now=NOW)
        self.assertEqual(got.status, sf.NOT_YET)
        self.assertIn("gaming 24%", got.today)
        self.assertIn("67% of organic views", got.today)
        self.assertIn("43 points", got.today)
        even = Counter(gaming=60, ufc=15, nba=10, nfl=10, soccer=5)
        with (
            patch("core.predictions.ledger.menu_mix", return_value=(even, Counter(), 30)),
            patch.object(sf, "_domain_views", return_value=views),
        ):
            self.assertEqual(sf.reading("S15", "tapin", now=NOW).status, sf.MET)

    def test_views_by_domain_over_28_days(self):
        from core.success import shortfalls as sf

        rows = [{"run_id": 1, "views": 300, "paid": 0, "published": NOW - timedelta(days=3)},
                {"run_id": 2, "views": 150, "paid": 50, "published": NOW - timedelta(days=10)},
                {"run_id": 3, "views": 900, "paid": 0, "published": NOW - timedelta(days=40)}]  # fmt: skip
        kinds = {1: ("gaming", "Shorts"), 2: ("ufc", "Shorts"), 3: ("gaming", "Shorts")}
        with (
            patch("analytics.growth._rows", return_value=rows),
            patch("analytics.growth._kind", side_effect=lambda rid: kinds[rid]),
        ):
            got = sf._domain_views("tapin", NOW)
        self.assertEqual(got, {"gaming": 300, "ufc": 100})

    def test_a_chapter_short_takes_its_parents_domain(self):
        from analytics import growth

        features = {
            191: {"parent_run_id": 185, "chapter_index": 2},
            185: {"domain": "gaming", "technical_qc": {"video_duration": 600}},
            172: {"compilation": {"week": "x"}},
        }
        with patch.object(growth, "_features", side_effect=lambda rid: features.get(int(rid), {})):
            self.assertEqual(growth._kind(191), ("gaming", "Shorts"))
            self.assertEqual(growth._kind(172), ("", "Shorts"))  # a compilation has no one domain

    def test_s11_waits_on_youtube_once_the_job_runs(self):
        from core.success import shortfalls as sf

        job = (True, "click-through: report job running since 2026-11-01, no daily file yet "
                     "(YouTube writes the first within about two days)")  # fmt: skip
        with (
            patch.object(sf, "_public_rows", return_value=[]),
            patch("analytics.reach_report.status", return_value=job),
        ):
            got = sf.reading("S11", "tapin", now=NOW)
        self.assertEqual(got.status, sf.WAITING)
        self.assertIn("report job running since 2026-11-01", got.today)
        off = (False, "click-through: the YouTube Reporting API is off")
        with (
            patch.object(sf, "_public_rows", return_value=[]),
            patch("analytics.reach_report.status", return_value=off),
        ):
            self.assertEqual(sf.reading("S11", "tapin", now=NOW).status, sf.YOURS)

    def test_the_menu_line_reads_the_same_counts(self):
        import inspect

        from core.predictions import ledger

        self.assertIn("menu_mix(", inspect.getsource(ledger.menu_mix_line))


if __name__ == "__main__":
    unittest.main()
