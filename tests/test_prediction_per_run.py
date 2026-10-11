"""#1062: each run's prediction beside what happened.

`ops predictions` summed errors per recommender ("collecting, n=2") and never showed one run:
what was predicted for it, what it got. With 7 frozen and 5 measured on 2026-10-10 the sums
say nothing yet, and the per-run lines are all there is to read.
"""

from __future__ import annotations

import math
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ENTRY = {
    "engaged_rate": {"rate": 0.30, "band": 0.08, "n": 12},
    "views_7d": {"log_views": math.log1p(210), "views": 210, "band": 0.9, "n": 12},
}


class PredictionLineTests(unittest.TestCase):
    def _line(self, entry, rate=None, log_views=None):
        from core.predictions import ledger

        return ledger.prediction_line(entry, rate=rate, log_views=log_views)

    def test_predicted_and_actual_side_by_side(self):
        line = self._line(ENTRY, rate=0.22, log_views=math.log1p(53))
        self.assertIn("predicted 30% engaged", line)
        self.assertIn("got 22%", line)
        self.assertIn("~210 views", line)
        self.assertIn("got 53", line)

    def test_inside_and_outside_the_band_are_said(self):
        self.assertIn("inside", self._line(ENTRY, rate=0.25))
        self.assertIn("outside", self._line(ENTRY, rate=0.10))

    def test_not_measured_yet_says_so(self):
        line = self._line(ENTRY)
        self.assertIn("predicted 30% engaged", line)
        self.assertIn("not measured yet", line)

    def test_no_prediction_is_empty(self):
        self.assertEqual(self._line({}), "")
        self.assertEqual(self._line(None), "")

    def test_a_backfilled_entry_is_marked(self):
        self.assertIn("fitted after", self._line({**ENTRY, "backfilled": True}, rate=0.3))


class PerRunLinesTests(unittest.TestCase):
    def test_the_report_lists_each_run_newest_first(self):
        from core.predictions import ledger

        runs = [SimpleNamespace(id=i, title=f"Video {i}") for i in (118, 131, 132)]
        entries = {118: ENTRY, 131: ENTRY, 132: None}
        with (
            patch.object(ledger, "_runs", return_value=runs),
            patch.object(ledger, "stored", side_effect=lambda rid: entries.get(int(rid))),
            patch.object(ledger, "_engaged_outcomes", return_value={118: 0.22}),
            patch.object(ledger, "_views_outcomes", return_value={118: math.log1p(53)}),
        ):
            lines = ledger.run_lines("tapin")
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("run 131"))
        self.assertIn("not measured yet", lines[0])
        self.assertIn("got 53", lines[1])
        self.assertIn("Video 118", lines[1])

    def test_ops_predictions_prints_them(self):
        from core.predictions import ledger

        with (
            patch.object(ledger, "ledger_rows", return_value=[]),
            patch.object(ledger, "_frozen_count", return_value=1),
            patch.object(
                ledger, "run_lines", return_value=["run 131 Video - predicted 30% engaged"]
            ),
            patch.object(ledger, "_time_to_100_line", return_value="", create=True),
        ):
            text = "\n".join(ledger.report_lines("tapin"))
        self.assertIn("Per run", text)
        self.assertIn("run 131 Video", text)


if __name__ == "__main__":
    unittest.main()
