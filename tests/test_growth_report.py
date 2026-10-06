"""#983: `ops growth` - where the views go, from the operator's own numbers.

Operator, 2026-10-06: "why are we still barely getting 500 views per post? better or more
advertising?" The sync keeps, per video, the organic 7-day views (#940), the share of starts
not swiped away (`stayed`, #951), the Shorts-feed share (#954), paid views (#954) and the
first-day verdict (#49); no report read them together. `analytics/growth.report` does, and
`levers` ranks the three largest gaps with the number behind each and one change it suggests.
Below 5 measured videos it says so instead of guessing.
"""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

TODAY = date(2026, 10, 6)


def _video(i, views7, stayed, *, paid=0, feed=0.9, days_ago=None):
    published = datetime(2026, 10, 6, 18, tzinfo=timezone.utc) - timedelta(days=days_ago or 9 + i)
    organic = {"SHORTS": int(1000 * feed), "YT_SEARCH": 1000 - int(1000 * feed)}
    if paid:
        organic["ADVERTISING"] = paid
    from analytics.view_curve import publish_day

    start = publish_day(published)
    daily = [[(start + timedelta(days=d)).isoformat(), views7 if d == 0 else 0] for d in range(8)]
    metrics = {"views": views7 + paid, "paid_views": paid, "stayed_share": stayed,
               "views_by_source": organic, "daily_views": daily}  # fmt: skip
    return SimpleNamespace(id=i, content_run_id=100 + i, youtube_video_id=f"v{i}",
                           detail=f"Video {i}", published_at=published,
                           metrics_json=json.dumps(metrics))  # fmt: skip


def _patched(rows):
    repo = SimpleNamespace(list_uploaded_for_channel=lambda c: rows)
    return (
        patch("analytics.growth._repo", return_value=repo),
        patch("analytics.growth._today", return_value=TODAY),
    )


class ReportTests(unittest.TestCase):
    def _report(self, rows):
        from analytics.growth import report

        a, b = _patched(rows)
        with a, b:
            return report("tapin")

    def test_the_numbers(self):
        rows = [_video(i, v, s) for i, (v, s) in enumerate(
            [(1200, .78), (900, .74), (800, .71), (450, .55), (400, .52), (300, .41)])]  # fmt: skip
        got = self._report(rows)
        self.assertEqual(got["n"], 6)
        self.assertEqual(got["median_views"], 625)
        self.assertEqual((got["best"]["views"], got["worst"]["views"]), (1200, 300))
        self.assertEqual(got["stayed_split"]["high_views"], 1050)  # top third by stayed
        self.assertEqual(got["stayed_split"]["low_views"], 350)
        self.assertAlmostEqual(got["feed_share"], 0.9)

    def test_cadence_counts_the_last_four_weeks(self):
        rows = [_video(i, 500, 0.6, days_ago=2 + 3 * i) for i in range(12)]
        self.assertAlmostEqual(self._report(rows)["per_week"], 2.25)  # 9 in 28 days

    def test_paid_share(self):
        rows = [_video(i, 500, 0.6) for i in range(5)] + [_video(9, 200, 0.6, paid=3800)]
        self.assertAlmostEqual(self._report(rows)["paid_share"], 3800 / (2700 + 3800), places=3)

    def test_too_few_says_collecting(self):
        from analytics.growth import render

        rows = [_video(i, 500, 0.6) for i in range(3)]
        a, b = _patched(rows)
        with a, b:
            text = render("tapin")
        self.assertIn("collecting", text)


class LeverTests(unittest.TestCase):
    def test_the_largest_gaps_lead_with_their_numbers(self):
        from analytics.growth import levers

        report = {"n": 8, "median_views": 500, "per_week": 2.0, "paid_share": 0.76,
                  "feed_share": 0.88,
                  "stayed_split": {"high_stayed": 0.75, "low_stayed": 0.48,
                                   "high_views": 1100, "low_views": 320}}  # fmt: skip
        got = levers(report)
        self.assertEqual(len(got), 3)
        keys = [lever["key"] for lever in got]
        self.assertEqual(set(keys), {"stayed", "cadence", "paid"})
        stayed = next(lever for lever in got if lever["key"] == "stayed")
        self.assertIn("1,100", stayed["line"])
        self.assertIn("320", stayed["line"])
        cadence = next(lever for lever in got if lever["key"] == "cadence")
        self.assertIn("2.0 a week", cadence["line"])

    def test_a_healthy_channel_gets_no_invented_levers(self):
        from analytics.growth import levers

        report = {"n": 8, "median_views": 5000, "per_week": 7.5, "paid_share": 0.0,
                  "feed_share": 0.95,
                  "stayed_split": {"high_stayed": 0.8, "low_stayed": 0.76,
                                   "high_views": 5200, "low_views": 4800}}  # fmt: skip
        self.assertEqual(levers(report), [])


class OpsTests(unittest.TestCase):
    def test_ops_growth_prints_it(self):
        from scripts.ops import COMMANDS

        rows = [_video(i, v, s) for i, (v, s) in enumerate(
            [(1200, .78), (900, .74), (800, .71), (450, .55), (400, .52), (300, .41)])]  # fmt: skip
        a, b = _patched(rows)
        buf = io.StringIO()
        with a, b, redirect_stdout(buf):
            code = COMMANDS["growth"][1](SimpleNamespace(channel="tapin"))
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("Growth - tapin", out)
        self.assertIn("median", out)
        self.assertIn("stayed", out)


if __name__ == "__main__":
    unittest.main()
