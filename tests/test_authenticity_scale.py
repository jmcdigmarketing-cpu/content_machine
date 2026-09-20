"""#813: #804 split the authenticity number in two; two readers kept the old one.

`authenticity_score` used to be the binary 40/35/25 sum — it was the gate AND
the grade, and it read 100 on 22 of 38 recorded runs. Wave 26 made it a
continuous 0-100 grade and moved the binary sum to `authenticity_gate_score`,
bumping GRADE_VERSION v3 -> v4 so report-card letters re-grade.

`channel_health` (absolute 55/72 thresholds) and `engagement_predictor` (a
least-squares fit) were calibrated on the binary series and were never told.
Both now resolve through `authenticity_gate_value`, which reads the gate key
when it exists and falls back to `authenticity_score` for pre-v4 rows — where
that field *is* the binary sum. One consistent series either side.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from core import channel_health
from core.run_quality import authenticity_gate_value


def _run(run_id: int, quality: dict) -> MagicMock:
    r = MagicMock()
    r.id = run_id
    r.quality_json = json.dumps(quality)
    return r


class TestAuthenticityGateValue(unittest.TestCase):
    def test_v4_row_resolves_to_the_gate_not_the_grade(self):
        quality = {"authenticity_score": 62, "authenticity_gate_score": 100}
        self.assertEqual(authenticity_gate_value(quality), 100.0)

    def test_pre_v4_row_resolves_to_its_own_score(self):
        self.assertEqual(authenticity_gate_value({"authenticity_score": 100}), 100.0)

    def test_missing_or_unreadable_is_none(self):
        self.assertIsNone(authenticity_gate_value({}))
        self.assertIsNone(authenticity_gate_value(None))
        self.assertIsNone(authenticity_gate_value({"authenticity_score": "high"}))


class TestChannelHealthAcrossTheBoundary(unittest.TestCase):
    """A window that is healthy on the gate scale must not read YELLOW."""

    def _sub(self, runs: list) -> channel_health.HealthSub:
        with patch(
            "storage.repositories.content_runs.get_content_run_repository",
            return_value=MagicMock(list_for_channel=MagicMock(return_value=runs)),
        ):
            return channel_health._authenticity_sub("tapin")

    def test_a_v4_window_reads_the_gate_not_the_grade(self):
        # Every check passes (gate 100) but the continuous grade is 54: a run
        # that is 60% distinct from recent uploads, has an authorial take that
        # names nothing specific, and is 100 words on 3 facts. Healthy work.
        runs = [
            _run(i, {"authenticity_score": 54, "authenticity_gate_score": 100}) for i in range(1, 6)
        ]
        sub = self._sub(runs)
        self.assertEqual(sub.status, channel_health.GREEN, sub.detail)

    def test_mixed_v3_v4_window_is_one_series(self):
        runs = [_run(i, {"authenticity_score": 100}) for i in range(1, 4)]
        runs += [
            _run(i, {"authenticity_score": 54, "authenticity_gate_score": 100}) for i in range(4, 7)
        ]
        sub = self._sub(runs)
        self.assertEqual(sub.status, channel_health.GREEN, sub.detail)
        # Not a 77 that happens to clear the bar — one scale, mean 100.
        self.assertIn("mean 100", sub.detail)

    def test_a_genuinely_failing_gate_still_goes_red(self):
        runs = [
            _run(i, {"authenticity_score": 30, "authenticity_gate_score": 40}) for i in range(1, 6)
        ]
        sub = self._sub(runs)
        self.assertEqual(sub.status, channel_health.RED, sub.detail)


class TestPredictorTrainingRows(unittest.TestCase):
    def test_the_fit_reads_the_gate_series(self):
        from core import engagement_predictor

        runs = [
            _run(1, {"hook_score": 70, "authenticity_score": 100}),
            _run(2, {"hook_score": 80, "authenticity_score": 62, "authenticity_gate_score": 100}),
        ]
        with (
            patch(
                "core.engagement_predictor.run_engagement_map",
                return_value={1: 0.3, 2: 0.4},
            ),
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=MagicMock(list_for_channel=MagicMock(return_value=runs)),
            ),
        ):
            rows = engagement_predictor._training_rows("tapin")
        self.assertEqual([r[1] for r in rows], [100.0, 100.0], rows)


if __name__ == "__main__":
    unittest.main()
