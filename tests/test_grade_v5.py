"""Report card v5 (2026-09-26, run 98): the topic composite keeps a small weight.

Run 98 scored all five angles 94.61 - signals are fetched once per topic and
copied to every angle, so the composite cannot tell one angle from another. And on
the operator's 23 measured videos it does not predict engagement (composite
r=-0.05, 95% interval about -0.45..+0.37). At 12% it moved a grade by up to ~12
points for something the video itself does not control. The operator chose to
lower it, not remove it: 0.12 -> 0.05, stamped v5.

`core/grade_calibration.py` refuses to correlate across rubric versions, so the day
v5 lands the 23 v4 rows and every new v5 row would switch the grade r off. The
re-grade of every measured row under today's rubric is reported beside it,
labelled, so the measurement does not go dark while history is re-stamped.
"""

from __future__ import annotations

import json
import unittest

from core.video_grade import GRADE_VERSION, grade_from_parts

QUALITY = {
    "hook_score": 85,
    "authenticity_score": 87,
    "ungrounded_count": 0,
    "trade_warning_count": 0,
    "word_count": 164,
    "min_words": 150,
    "max_words": 300,
}


class TestV5(unittest.TestCase):
    def test_the_version_is_v5(self) -> None:
        self.assertEqual(GRADE_VERSION, "v5")

    def test_the_topic_share_is_small(self) -> None:
        grade = grade_from_parts(quality=QUALITY, composite_score=94.6)
        topic = next(c for c in grade.components if c.name == "topic")
        self.assertLess(topic.weight, 0.06, grade.components)
        self.assertGreater(topic.weight, 0.04)

    def test_the_composite_moves_the_grade_by_at_most_a_few_points(self) -> None:
        low = grade_from_parts(quality=QUALITY, composite_score=1.0).score
        high = grade_from_parts(quality=QUALITY, composite_score=100.0).score
        self.assertLess(high - low, 6.0, (low, high))
        self.assertGreater(high - low, 3.0)


class TestCalibrationAcrossTheBump(unittest.TestCase):
    def _run(self, i: int, version: str):
        from tests.test_component_calibration import _run

        q = {
            "hook_score": 40 + 10 * i,
            "authenticity_score": 80,
            "ungrounded_count": 0,
            "grade_version": version,
            "grade_score": 60.0 + i,
            "grade_letter": "B",
        }
        return _run(i, json.dumps(q))

    def test_mixed_versions_still_report_today_s_regrade(self) -> None:
        from core.grade_calibration import build_calibration, render
        from tests.test_component_calibration import _patched

        runs = [self._run(i, "v4" if i < 4 else "v5") for i in range(1, 7)]
        rates = {i: 0.01 * i for i in range(1, 7)}
        with _patched(runs, rates):
            report = build_calibration("tapin")
            text = render("tapin")
        self.assertTrue(report.mixed_versions)
        self.assertIsNone(report.grade_correlation)
        self.assertIsNotNone(report.regraded_correlation)
        self.assertIn("under today's rubric", text)
        self.assertIn("backfill-quality", text)


if __name__ == "__main__":
    unittest.main()
