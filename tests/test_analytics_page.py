"""#984: an analytics page in the app.

`ops growth` (#983), the hook-learning line (#985), the scoreboard (#934) and the prediction
ledger (#113) were terminal-only. The app gets an Analytics page, second in the sidebar:

- four tiles from `analytics.growth.report`: median 7-day views, the stayed split, posts a week
  and the paid share;
- a bar per video of its organic 7-day views, shaded by its stayed-share third (light = bottom,
  dark = top, grey = not synced), with a legend and a tooltip per bar;
- the hook line, the scoreboard lines and the prediction-ledger line.

`desktop.analytics_page.analytics_data` gathers it (each reader fail-open) so the page only
draws; under 5 measured videos it says "collecting" with the backfill command.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from tests.qt_support import requires_qt

REPORT = {
    "n": 6, "videos": 6, "median_views": 625,
    "best": {"title": "A", "views": 1200}, "worst": {"title": "B", "views": 300},
    "stayed_split": {"high_stayed": 0.76, "low_stayed": 0.48, "high_views": 1050,
                     "low_views": 350},
    "feed_share": 0.9, "per_week": 2.0, "paid_share": 0.76,
}  # fmt: skip
VIDEOS = [
    {"title": f"Video {i}", "views7": v, "stayed": s}
    for i, (v, s) in enumerate([(1200, 0.78), (900, 0.74), (800, 0.71), (450, 0.55),
                                (400, 0.52), (300, None)])
]  # fmt: skip


def _patches(report=REPORT, videos=VIDEOS):
    return [
        patch("analytics.growth.report", return_value=report),
        patch("analytics.growth.videos", return_value=videos),
        patch("analytics.hook_learning.render_line", return_value="Hook vs stayed: collecting"),
        patch("analytics.growth.intro_line", return_value="Intro: 51% with vs 62% without"),
        patch("core.success.goals.scoreboard_lines", return_value=["Goal: 10k views"]),
        patch("core.predictions.ledger.summary_line", return_value="Predictions: 3 scored"),
    ]


class DataTests(unittest.TestCase):
    def _data(self, **kw):
        from desktop.analytics_page import analytics_data

        ps = _patches(**kw)
        for p in ps:
            p.start()
        try:
            return analytics_data("tapin")
        finally:
            for p in ps:
                p.stop()

    def test_tiles(self):
        tiles = dict(self._data()["tiles"])
        self.assertEqual(tiles["Median 7-day views"], "625")
        self.assertEqual(tiles["Posts a week"], "2.0")
        self.assertEqual(tiles["Paid share"], "76%")
        self.assertIn("1,050", tiles["Stayed: top vs bottom third"])

    def test_bars_are_shaded_by_stayed_third(self):
        bars = self._data()["bars"]
        self.assertEqual(len(bars), 6)
        self.assertEqual(bars[0]["band"], 2)  # highest stayed -> top third
        self.assertEqual(bars[4]["band"], 0)
        self.assertIsNone(bars[5]["band"])  # not synced

    def test_lines(self):
        lines = self._data()["lines"]
        self.assertIn("Hook vs stayed: collecting", lines)
        self.assertIn("Goal: 10k views", lines)
        self.assertIn("Predictions: 3 scored", lines)
        self.assertIn("Intro: 51% with vs 62% without", lines)  # #988

    def test_collecting_below_five(self):
        data = self._data(report={**REPORT, "n": 3}, videos=VIDEOS[:3])
        self.assertIn("collecting", data["note"])
        self.assertIn("backfill view-curve", data["note"])

    def test_a_failing_reader_is_said(self):
        from desktop.analytics_page import analytics_data

        with (
            patch("analytics.growth.report", side_effect=RuntimeError("db gone")),
            patch("analytics.growth.videos", return_value=[]),
            patch("analytics.hook_learning.render_line", return_value=""),
            patch("core.success.goals.scoreboard_lines", return_value=[]),
            patch("core.predictions.ledger.summary_line", return_value=""),
        ):
            data = analytics_data("tapin")
        self.assertIn("unavailable", data["note"])


class GrowthVideosTests(unittest.TestCase):
    def test_videos_lists_measured_rows_oldest_first(self):
        from datetime import datetime, timezone

        from analytics import growth

        rows = [
            {"title": "new", "published": datetime(2026, 10, 1, tzinfo=timezone.utc),
             "views7": 500, "stayed": 0.6},
            {"title": "young", "published": datetime(2026, 10, 5, tzinfo=timezone.utc),
             "views7": None, "stayed": None},
            {"title": "old", "published": datetime(2026, 9, 1, tzinfo=timezone.utc),
             "views7": 900, "stayed": 0.7},
        ]  # fmt: skip
        with patch("analytics.growth._rows", return_value=rows):
            got = growth.videos("tapin")
        self.assertEqual([v["title"] for v in got], ["old", "new"])


@requires_qt
class PageTests(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        if QApplication.instance() is None:
            QApplication([])

    def test_analytics_is_second_in_the_sidebar(self):
        from desktop.shell import PAGES

        self.assertEqual(PAGES[1], ("Analytics", "analytics"))

    def test_the_page_draws_tiles_bars_and_lines(self):
        from desktop.shell import build_page

        ps = _patches()
        for p in ps:
            p.start()
        try:
            page = build_page("analytics", "tapin")
        finally:
            for p in ps:
                p.stop()
        text = page.page_text()
        self.assertIn("625", text)
        self.assertIn("Hook vs stayed", text)
        self.assertEqual(page.chart.bar_count(), 6)
        self.assertIn("Video 0", page.chart.tip_for(0))
        self.assertIn("1,200", page.chart.tip_for(0))
        page.resize(900, 700)
        self.assertFalse(page.grab().isNull())
        page.close()


if __name__ == "__main__":
    unittest.main()
