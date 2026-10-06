"""#959: the promotion ledger - what each ad campaign bought.

Operator, 2026-10-06, choosing to keep the ads until Oct 24 as a measured test: "maybe that's a
week 3-4 october question to stop the ads once we have a big enough sample size". A campaign is
an `ads` entry in the spend ledger (#980), now with the videos it promoted (`--video`) and how
many days it ran (`--days`, default 14). `analytics/promotions.report` reads stored metrics only:

- paid views in the window (#954's `daily_paid_views`) and the cost per paid view;
- subscribers gained by the promoted videos, the cost per subscriber, and subscribers per 1,000
  views against the channel's other videos;
- spillover: organic views a day on the other videos during the campaign, against the same
  number of days before it.

`verdict` says running (with its decision day), keep or stop, with the numbers behind it.
YouTube's stored numbers do not split subscribers by paid and organic - the report says so.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

START = date(2026, 10, 4)


def _daily(start: date, days: int, per_day: int) -> list[list]:
    return [[(start + timedelta(days=d)).isoformat(), per_day] for d in range(days)]


def _video(vid: str, *, views_per_day: int, paid_per_day: int = 0, subs: int = 0):
    first = START - timedelta(days=14)
    metrics = {
        "views": views_per_day * 35 + paid_per_day * 21,
        "daily_views": _daily(first, 35, views_per_day),
        "daily_paid_views": _daily(START, 21, paid_per_day) if paid_per_day else [],
        "subscribers_gained": subs,
    }
    return SimpleNamespace(youtube_video_id=vid, detail=f"Video {vid}", content_run_id=1,
                           metrics_json=json.dumps(metrics))  # fmt: skip


class LedgerTests(unittest.TestCase):
    def test_an_ads_entry_keeps_its_videos_and_days(self):
        from core.money import ledger

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ledger, "LEDGER_FILE", os.path.join(tmp, "l.json")):
                entry = ledger.add_entry(10, "first campaign", "ads", on=START,
                                         videos=["v1", "v2"], days=21)  # fmt: skip
                self.assertEqual(entry["videos"], ["v1", "v2"])
                self.assertEqual(entry["days"], 21)
                plain = ledger.add_entry(5, "credits", "credits", on=START)
                self.assertNotIn("videos", plain)

    def test_ops_spend_add_takes_video_and_days(self):
        from core.money import ledger
        from scripts.ops import COMMANDS

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ledger, "LEDGER_FILE", os.path.join(tmp, "l.json")):
                args = SimpleNamespace(target="add", amount=10.0, what="ads", kind="ads",
                                       monthly=False, date="2026-10-04", entry=None,
                                       video=["v1"], days=21)  # fmt: skip
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(COMMANDS["spend"][1](args), 0)
                self.assertEqual(ledger.entries()[0]["videos"], ["v1"])
                self.assertEqual(ledger.entries()[0]["days"], 21)


class ReportTests(unittest.TestCase):
    def _report(self, rows, entries, today):
        from analytics import promotions

        repo = SimpleNamespace(list_uploaded_for_channel=lambda c: rows)
        with (
            patch("analytics.promotions._repo", return_value=repo),
            patch("core.money.ledger.entries", return_value=entries),
        ):
            return promotions.report("tapin", today=today)

    def test_a_campaign_that_paid_off(self):
        rows = [
            _video("v1", views_per_day=30, paid_per_day=100, subs=40),
            _video("v2", views_per_day=20, subs=2),
        ]
        entries = [{"id": 1, "date": START.isoformat(), "amount": 10.0, "kind": "ads",
                    "what": "first", "videos": ["v1"], "days": 21}]  # fmt: skip
        got = self._report(rows, entries, START + timedelta(days=30))
        self.assertEqual(len(got), 1)
        camp = got[0]
        self.assertEqual(camp["paid_views"], 2100)
        self.assertAlmostEqual(camp["cost_per_paid_view"], 10 / 2100, places=6)
        self.assertEqual(camp["subscribers"], 40)
        self.assertAlmostEqual(camp["cost_per_subscriber"], 0.25)
        self.assertGreater(camp["subs_per_1k_promoted"], camp["subs_per_1k_others"])
        self.assertEqual(camp["state"], "done")

    def test_spillover_compares_the_other_videos_before_and_during(self):
        first = START - timedelta(days=14)
        other = _video("v2", views_per_day=0)
        daily = _daily(first, 14, 20) + _daily(START, 21, 30)  # 20/day before, 30/day during
        metrics = json.loads(other.metrics_json)
        metrics["daily_views"] = daily
        other.metrics_json = json.dumps(metrics)
        rows = [_video("v1", views_per_day=10, paid_per_day=50, subs=3), other]
        entries = [{"id": 1, "date": START.isoformat(), "amount": 10.0, "kind": "ads",
                    "what": "first", "videos": ["v1"], "days": 21}]  # fmt: skip
        camp = self._report(rows, entries, START + timedelta(days=30))[0]
        self.assertAlmostEqual(camp["others_before_per_day"], 20.0)
        self.assertAlmostEqual(camp["others_during_per_day"], 30.0)
        self.assertAlmostEqual(camp["spillover"], 0.5)

    def test_running_until_its_decision_day(self):
        rows = [_video("v1", views_per_day=30, paid_per_day=100, subs=4)]
        entries = [{"id": 1, "date": START.isoformat(), "amount": 10.0, "kind": "ads",
                    "what": "first", "videos": ["v1"], "days": 21}]  # fmt: skip
        camp = self._report(rows, entries, START + timedelta(days=5))[0]
        self.assertEqual(camp["state"], "running")
        self.assertEqual(camp["decide_on"], "2026-10-24")

    def test_only_ads_entries_are_campaigns(self):
        entries = [{"id": 1, "date": START.isoformat(), "amount": 22.0, "kind": "subscription",
                    "what": "ElevenLabs", "monthly": True}]  # fmt: skip
        self.assertEqual(self._report([], entries, START), [])


class VerdictTests(unittest.TestCase):
    def test_keep_when_paid_viewers_subscribe_at_least_as_well(self):
        from analytics.promotions import verdict

        got = verdict({"state": "done", "paid_views": 2100, "subs_per_1k_promoted": 7.0,
                       "subs_per_1k_others": 2.0, "spillover": 0.0})  # fmt: skip
        self.assertEqual(got["call"], "keep")

    def test_keep_when_organic_views_lifted(self):
        from analytics.promotions import verdict

        got = verdict({"state": "done", "paid_views": 2100, "subs_per_1k_promoted": 1.0,
                       "subs_per_1k_others": 2.0, "spillover": 0.3})  # fmt: skip
        self.assertEqual(got["call"], "keep")

    def test_stop_otherwise(self):
        from analytics.promotions import verdict

        got = verdict({"state": "done", "paid_views": 2100, "subs_per_1k_promoted": 0.5,
                       "subs_per_1k_others": 2.0, "spillover": 0.05})  # fmt: skip
        self.assertEqual(got["call"], "stop")
        self.assertIn("0.5", got["why"])

    def test_no_paid_views_stored_says_how_to_get_them(self):
        from analytics.promotions import verdict

        got = verdict({"state": "done", "paid_views": 0})
        self.assertEqual(got["call"], "no data")
        self.assertIn("backfill view-curve", got["why"])


class OpsTests(unittest.TestCase):
    def test_ops_promotions_prints_the_campaigns(self):
        from scripts.ops import COMMANDS

        camp = {"id": 1, "what": "first", "amount": 10.0, "start": "2026-10-04",
                "decide_on": "2026-10-24", "state": "running", "paid_views": 900,
                "cost_per_paid_view": 0.011, "subscribers": 4, "cost_per_subscriber": 2.5,
                "subs_per_1k_promoted": 3.0, "subs_per_1k_others": 2.0,
                "others_before_per_day": 20.0, "others_during_per_day": 25.0,
                "spillover": 0.25, "videos": ["v1"]}  # fmt: skip
        buf = io.StringIO()
        with patch("analytics.promotions.report", return_value=[camp]), redirect_stdout(buf):
            code = COMMANDS["promotions"][1](SimpleNamespace(channel="tapin"))
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("first", out)
        self.assertIn("2026-10-24", out)
        self.assertIn("not split", out)  # the honest limit


class ShownTests(unittest.TestCase):
    def test_status_and_growth_show_the_call(self):
        from analytics import growth
        from core.status import build_status_lines

        line = "Ads #1: stop - 0.5 vs 2.0 (ops promotions)"
        with patch("analytics.promotions.status_line", return_value=line):
            self.assertIn(line, build_status_lines("tapin"))
            with (
                patch("analytics.growth.report", return_value={"n": 6, "median_views": 500,
                      "best": {"title": "a", "views": 900}, "worst": {"title": "b", "views": 1},
                      "per_week": 3.0, "paid_share": 0.5}),
                patch("analytics.hook_learning.render_line", return_value=""),
            ):  # fmt: skip
                self.assertIn(line, growth.render("tapin"))


if __name__ == "__main__":
    unittest.main()
