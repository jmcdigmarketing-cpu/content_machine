"""#957: the engaged rate without the paid viewers.

`fetch_video_metrics`' `averageViewPercentage` covers every view, ads included, and an ad
viewer who skips at 3 seconds drags it down. `RECOMMEND_TARGET=engaged`, the engagement
predictor and the grade calibration all read it. For a video with paid views the sync now
asks one more question - views and minutes watched by traffic source - and keeps an
organic engaged rate beside the total one:

    organic % = total % x (organic minutes / organic views) / (all minutes / all views)

The video's length cancels out, so no duration is needed. A video with no paid views is
not asked (its two rates are the same), and a failed question loses nothing else.
`core.engagement.engaged_rate` reads the organic rate when there is one.
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from tests.test_paid_views import SOURCE_DAY

VIDEO = {
    "columnHeaders": [{"name": "video"}, {"name": "views"},
                      {"name": "averageViewPercentage"}],
    "rows": [["vid1", 4000, 40.0]],
}  # fmt: skip
SOURCE_WATCH = {
    "columnHeaders": [{"name": "insightTrafficSourceType"}, {"name": "views"},
                      {"name": "estimatedMinutesWatched"}],
    "rows": [["ADVERTISING", 3000, 1500.0], ["SHORTS", 900, 900.0], ["YT_SEARCH", 100, 100.0]],
}  # fmt: skip


class _Fake:
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


class FormulaTests(unittest.TestCase):
    def test_organic_minutes_per_view_against_all(self):
        from analytics.youtube_metrics import organic_engaged_rate

        watch = {"ADVERTISING": (3000, 1500.0), "SHORTS": (900, 900.0), "YT_SEARCH": (100, 100.0)}
        # all: 2500 min / 4000 views = 0.625; organic: 1000 / 1000 = 1.0 -> 0.40 * 1.6
        self.assertAlmostEqual(organic_engaged_rate(40.0, watch), 0.64)

    def test_no_organic_views_or_minutes_is_none(self):
        from analytics.youtube_metrics import organic_engaged_rate

        self.assertIsNone(organic_engaged_rate(40.0, {"ADVERTISING": (3000, 1500.0)}))
        self.assertIsNone(organic_engaged_rate(40.0, {}))
        self.assertIsNone(organic_engaged_rate(0.0, {"SHORTS": (10, 0.0)}))

    def test_it_never_passes_one(self):
        from analytics.youtube_metrics import organic_engaged_rate

        watch = {"ADVERTISING": (1000, 10.0), "SHORTS": (10, 100.0)}
        self.assertEqual(organic_engaged_rate(90.0, watch), 1.0)


class FetchTests(unittest.TestCase):
    def _fetch(self, answers):
        from analytics import youtube_metrics

        service = _Fake(answers)
        with (
            patch.object(youtube_metrics, "_analytics_enabled", return_value=True),
            patch.object(youtube_metrics, "get_youtube_analytics_service", return_value=service),
            patch.object(youtube_metrics, "_date_range", return_value=("2026-09-06", "2026-10-04")),
        ):
            return youtube_metrics.fetch_video_metrics("vid1", channel_id="tapin"), service

    def test_a_boosted_video_gets_an_organic_rate(self):
        metrics, service = self._fetch({"video": VIDEO, "day,insightTrafficSourceType": SOURCE_DAY,
                                        "insightTrafficSourceType": SOURCE_WATCH})  # fmt: skip
        self.assertAlmostEqual(metrics["organic_engaged_rate"], 0.64)
        self.assertEqual(metrics["engaged_rate"], 0.4)
        asked = [q for q in service.queries if q.get("dimensions") == "insightTrafficSourceType"]
        self.assertEqual(len(asked), 1)
        self.assertIn("estimatedMinutesWatched", asked[0]["metrics"])
        self.assertEqual(asked[0]["filters"], "video==vid1")

    def test_an_unboosted_video_is_not_asked(self):
        no_paid = dict(SOURCE_DAY, rows=[r for r in SOURCE_DAY["rows"] if r[1] != "ADVERTISING"])
        metrics, service = self._fetch({"video": VIDEO, "day,insightTrafficSourceType": no_paid,
                                        "insightTrafficSourceType": SOURCE_WATCH})  # fmt: skip
        self.assertNotIn("organic_engaged_rate", metrics)
        self.assertFalse(any(q.get("dimensions") == "insightTrafficSourceType"
                             for q in service.queries))  # fmt: skip

    def test_a_failed_question_loses_nothing_else(self):
        metrics, _service = self._fetch({"video": VIDEO, "day,insightTrafficSourceType": SOURCE_DAY,
                                         "insightTrafficSourceType": RuntimeError("400")})  # fmt: skip
        self.assertNotIn("organic_engaged_rate", metrics)
        self.assertEqual(metrics["paid_views"], 3700)
        self.assertEqual(metrics["engaged_rate"], 0.4)


class ReaderTests(unittest.TestCase):
    def test_the_organic_rate_is_read_first(self):
        from core.engagement import engaged_rate

        both = json.dumps({"views": 4000, "engaged_rate": 0.4, "organic_engaged_rate": 0.64})
        self.assertEqual(engaged_rate(both), 0.64)
        self.assertEqual(engaged_rate(json.dumps({"views": 4000, "engaged_rate": 0.4})), 0.4)

    def test_ops_predictions_counts_them(self):
        from types import SimpleNamespace

        from core.engagement import basis_line

        rows = [{"views": 4000, "engaged_rate": 0.4, "average_view_percentage": 40.0,
                 "organic_engaged_rate": 0.64},
                {"views": 900, "engaged_rate": 0.5, "average_view_percentage": 50.0}]  # fmt: skip
        logs = [SimpleNamespace(metrics_json=json.dumps(m)) for m in rows]
        with patch("storage.repositories.publish_log.get_publish_log_repository",
                   return_value=SimpleNamespace(list_timed_outcomes=lambda c: logs)):  # fmt: skip
            line = basis_line("tapin")
        self.assertIn("1 read without ad viewers", line)


if __name__ == "__main__":
    unittest.main()
