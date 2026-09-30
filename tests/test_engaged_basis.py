"""#920 (operator's choice: label every row, stop counting likes/views): one name, three scales.

`engaged_rate` in a publish-log row held three different quantities: the sync stores
YouTube Analytics' `averageViewPercentage / 100` (a retention share), the TapIn seed
import stores Studio's engaged-views rate, and `core/engagement.engaged_rate` fell back to
likes / views - roughly ten times smaller - when the key was missing. Every row now says
which measure it holds (`engaged_basis`); the likes/views fallback no longer counts as an
outcome; seeded history still does. `ops predictions` shows the mix.
"""

from __future__ import annotations

import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

SYNCED = json.dumps({"views": 900, "engaged_rate": 0.62, "average_view_percentage": 62.0})
SEEDED = json.dumps({"views": 500, "engaged_rate": 0.55, "source": "tapin_seed"})
LIKES_ONLY = json.dumps({"views": 1000, "likes": 40})


class BasisTests(unittest.TestCase):
    def test_each_row_says_what_it_holds(self):
        from core.engagement import engaged_basis

        self.assertEqual(engaged_basis(json.loads(SYNCED)), "avg_view_pct")
        self.assertEqual(engaged_basis(json.loads(SEEDED)), "engaged_views")
        self.assertEqual(engaged_basis(json.loads(LIKES_ONLY)), "likes_per_view")
        self.assertEqual(engaged_basis({"engaged_basis": "engaged_views", "engaged_rate": 0.4}),
                         "engaged_views")  # fmt: skip

    def test_likes_per_view_is_no_longer_an_outcome(self):
        from core.engagement import engaged_rate

        self.assertIsNone(engaged_rate(LIKES_ONLY))
        self.assertEqual(engaged_rate(SYNCED), 0.62)
        self.assertEqual(engaged_rate(SEEDED), 0.55)

    def test_the_sync_labels_its_rows(self):
        from analytics import youtube_metrics

        service = MagicMock()
        call = MagicMock()
        call.execute.return_value = {
            "columnHeaders": [{"name": "video"}, {"name": "views"}, {"name": "averageViewPercentage"}],
            "rows": [["v", 100, 71.0]],
        }  # fmt: skip
        service.reports.return_value.query.return_value = call
        with (
            patch.dict(os.environ, {"YOUTUBE_ANALYTICS_SYNC": "true"}),
            patch.object(youtube_metrics, "get_youtube_analytics_service", return_value=service),
        ):
            got = youtube_metrics.fetch_video_metrics("v", channel_id="tapin")
        self.assertEqual(got["engaged_basis"], "avg_view_pct")

    def test_the_seed_labels_its_rows(self):
        from pathlib import Path

        text = (Path(__file__).resolve().parents[1] / "analytics" / "seed_tapin.py").read_text(
            encoding="utf-8"
        )
        self.assertTrue('"engaged_basis": "engaged_views"' in text, "seeded rows are unlabeled")


class LineTests(unittest.TestCase):
    def test_ops_predictions_shows_the_mix(self):
        from core.engagement import basis_line

        logs = [SimpleNamespace(metrics_json=m) for m in (SYNCED, SYNCED, SEEDED, LIKES_ONLY)]
        with patch(
            "storage.repositories.publish_log.get_publish_log_repository",
            return_value=SimpleNamespace(list_timed_outcomes=lambda c: logs),
        ):
            line = basis_line("tapin")
        self.assertIn("average view % 2", line)
        self.assertIn("Studio engaged views 1", line)
        self.assertIn("likes/views 1 (not counted)", line)

    def test_it_reaches_ops_predictions(self):
        from core.predictions import ledger

        with (
            patch.object(ledger, "ledger_rows", return_value=[]),
            patch("core.engagement.basis_line", return_value="  outcomes by measure: x"),
        ):
            self.assertIn("  outcomes by measure: x", ledger.report_lines("tapin"))


if __name__ == "__main__":
    unittest.main()
