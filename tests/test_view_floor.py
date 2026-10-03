"""#564 (operator's choice: a views floor, off by default): near-empty videos out of the learning.

YouTube's API cannot tell the owner's views from anyone else's. What it can do is keep a
video with almost no audience out of the learning: on a 12-view video the operator's own
full watches decide its average view percentage, which is the engaged rate every
recommender learns from. `MIN_OUTCOME_VIEWS` (default 0 = off) drops videos under it from
every engaged-rate reader - `core/engagement.engaged_rate` (best bet, length, the
predictor and ledger, experiments) and post-time's own reader. `ops predictions` says how
many measured videos sit under 50 views, so the operator can decide.
"""

from __future__ import annotations

import json
import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

LOW = json.dumps({"views": 12, "engaged_rate": 0.92})
HIGH = json.dumps({"views": 800, "engaged_rate": 0.41})
NO_VIEWS = json.dumps({"engaged_rate": 0.33})


def _logs():
    when = datetime(2026, 9, 20, 17, tzinfo=timezone.utc)
    return [
        SimpleNamespace(content_run_id=i, metrics_json=m, published_at=when, detail="")
        for i, m in ((1, LOW), (2, HIGH), (3, NO_VIEWS))
    ]


class _Env(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(os.environ, {"MIN_OUTCOME_VIEWS": ""})
        self._env.start()
        self._repo = patch(
            "storage.repositories.publish_log.get_publish_log_repository",
            return_value=SimpleNamespace(list_timed_outcomes=lambda c: _logs()),
        )
        self._repo.start()

    def tearDown(self):
        self._repo.stop()
        self._env.stop()


class FloorTests(_Env):
    def test_off_by_default_nothing_changes(self):
        from core.engagement import engaged_rate

        self.assertEqual(engaged_rate(LOW), 0.92)

    def test_the_floor_drops_a_near_empty_video(self):
        from core.engagement import engaged_rate

        with patch.dict(os.environ, {"MIN_OUTCOME_VIEWS": "50"}):
            self.assertIsNone(engaged_rate(LOW))
            self.assertEqual(engaged_rate(HIGH), 0.41)
            self.assertEqual(engaged_rate(NO_VIEWS), 0.33)  # unknown views are kept

    def test_every_learner_sees_it(self):
        from analytics.post_timing import _collect_timed_samples
        from core.engagement_predictor import run_engagement_map
        from core.success.target import outcome  # #938: best bet and length read through it

        self.assertEqual(sorted(run_engagement_map("tapin")), [1, 2, 3])
        with patch.dict(os.environ, {"MIN_OUTCOME_VIEWS": "50"}):
            self.assertEqual(sorted(run_engagement_map("tapin")), [2, 3])
            for target in ("engaged", "views"):
                self.assertIsNone(outcome(LOW, target_name=target), target)
            self.assertEqual(len(_collect_timed_samples("tapin")), 2)


class LineTests(_Env):
    def test_it_says_how_many_are_under_fifty(self):
        from core.engagement import low_view_line

        line = low_view_line("tapin")
        self.assertIn("1 of 3 measured video(s) under 50 views", line)
        self.assertIn("MIN_OUTCOME_VIEWS off - they count", line)

    def test_it_says_when_they_are_left_out(self):
        from core.engagement import low_view_line

        with patch.dict(os.environ, {"MIN_OUTCOME_VIEWS": "100"}):
            self.assertIn(
                "1 of 3 measured video(s) under 100 views - left out", low_view_line("tapin")
            )

    def test_ops_predictions_prints_it(self):
        from core.predictions import ledger

        with patch.object(ledger, "ledger_rows", return_value=[]):
            text = "\n".join(ledger.report_lines("tapin"))
        self.assertIn("under 50 views", text)


if __name__ == "__main__":
    unittest.main()
