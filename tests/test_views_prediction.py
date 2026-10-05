"""#945: a 7-day-views prediction, frozen beside the engaged-rate one.

Wave 55 (#938) made 7-day views the recommenders' target, but the engagement predictor -
frozen into quality, the grade and the ledger at publish - stayed on the engaged rate, so
nothing could say whether a script's quality predicts views. `predict_views_7d` fits the same
two inputs (hook score, authenticity gate) to log 7-day organic views, the ledger freezes it
at publish beside the engaged-rate prediction (never refitted, never backfilled - a claim
fitted after the outcome measures nothing), and `ops predictions` scores it as a ratio.
"""

from __future__ import annotations

import math
import unittest
from unittest.mock import patch

from tests.test_prediction_freeze import _Case

# log1p views per run, on the same runs as the engaged-rate fixture
VIEWS = {1: 100, 2: 200, 3: 400, 4: 800, 9: 5000}


class _ViewsCase(_Case):
    def setUp(self):
        super().setUp()
        self.views = {k: math.log1p(v) for k, v in VIEWS.items()}
        self.stack.enter_context(
            patch("core.engagement_predictor.run_views_map", side_effect=lambda c: self.views)
        )


class PredictTests(_ViewsCase):
    def test_it_fits_log_views_and_leaves_the_video_out(self):
        from core.engagement_predictor import predict_views_7d

        quality = {"hook_score": 80, "authenticity_score": 100}
        pred = predict_views_7d("tapin", quality=quality, exclude_run_id=9)
        self.assertEqual(pred.n, 4)
        self.assertGreater(pred.views, 800)  # higher hook and authenticity than all four
        self.assertAlmostEqual(pred.views, round(math.expm1(pred.log_views)))
        self.assertIn("views", pred.note)

    def test_too_few_measured_is_none(self):
        from core.engagement_predictor import predict_views_7d

        self.views = {1: 4.0}
        self.assertIsNone(predict_views_7d("tapin", quality={"hook_score": 50,
                                                             "authenticity_score": 60}))  # fmt: skip

    def test_the_engaged_rate_prediction_does_not_move(self):
        from core.engagement_predictor import predict_engaged_rate

        quality = {"hook_score": 80, "authenticity_score": 100}
        before = predict_engaged_rate("tapin", quality=quality, exclude_run_id=9)
        self.views = {}
        after = predict_engaged_rate("tapin", quality=quality, exclude_run_id=9)
        self.assertEqual(before, after)


class FreezeTests(_ViewsCase):
    def test_publish_freezes_both(self):
        from core.predictions.ledger import freeze

        entry = freeze(9, "tapin")
        self.assertEqual(entry["views_7d"]["n"], 4)
        stored = self._features(9)["prediction_ledger"]
        self.assertEqual(stored["views_7d"], entry["views_7d"])

    def test_a_later_fit_does_not_move_it(self):
        from core.predictions.ledger import freeze

        first = freeze(9, "tapin")["views_7d"]["log_views"]
        self.views[1] = math.log1p(90000)
        self.assertEqual(freeze(9, "tapin")["views_7d"]["log_views"], first)

    def test_a_backfill_does_not_invent_one(self):
        from core.predictions.ledger import freeze

        entry = freeze(9, "tapin", backfilled=True)
        self.assertNotIn("views_7d", entry)


class ScoreTests(_ViewsCase):
    def test_the_ledger_scores_it_against_the_real_views(self):
        from core.predictions import ledger

        for run_id in (1, 2, 3, 4, 9):
            ledger.freeze(run_id, "tapin")
        with patch.object(ledger, "_views_outcomes", return_value=self.views):
            rows = ledger.ledger_rows("tapin")
            lines = ledger.report_lines("tapin")
        scored = [r for r in rows if "views_pred_error" in r]
        self.assertEqual(len(scored), 5)
        row9 = next(r for r in rows if r["run_id"] == 9)
        frozen = self._features(9)["prediction_ledger"]["views_7d"]["log_views"]
        self.assertAlmostEqual(row9["views_pred_error"], self.views[9] - frozen)
        text = "\n".join(lines)
        self.assertIn("7-day views prediction", text)
        self.assertIn("typically off by x", text)


if __name__ == "__main__":
    unittest.main()
