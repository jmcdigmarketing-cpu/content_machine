"""#821: style recurrence is report-only; measure it against engagement before promoting it.

#803 counts the repeated opener; it is not in `points`, `gate_score` or `passed`. Moving
it is a rubric change that needs a `GRADE_VERSION` bump plus a floor (0.50) and a count
(3) that are calibrated against nothing. #823 backfilled `style_recurrence_n` onto 87
rows, so the calibration join can now say whether a recurring opener costs engagement.
Until |r| clears significance the rubric does not move - the line says so.

Two report-only gaps fixed alongside: `recurrence_line` hard-coded the count of 3
instead of reading `_RECURRENCE_MIN`, and `ops grade` never printed it although #803's
note said it did.
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from tests.test_component_calibration import _patched, _quality, _run


class TestRecurrenceCorrelation(unittest.TestCase):
    def test_rows_carry_recurrence_and_the_report_correlates_it(self) -> None:
        from core.grade_calibration import build_calibration, recurrence_line

        # recurrence rises as engagement falls -> negative r.
        runs = [_run(i, _quality(60.0, 80.0, recurrence_n=i)) for i in range(1, 7)]
        rates = {i: 0.07 - 0.01 * i for i in range(1, 7)}
        with _patched(runs, rates):
            report = build_calibration("tapin")
        self.assertEqual([r.recurrence_n for r in report.rows], [1, 2, 3, 4, 5, 6])
        r, n = report.recurrence_correlation
        self.assertEqual(n, 6)
        self.assertLess(r, -0.99)
        line = recurrence_line(report)
        self.assertIn("recurring opener", line.lower())
        self.assertIn("promotion", line)

    def test_rows_without_the_field_are_collecting(self) -> None:
        from core.grade_calibration import build_calibration, recurrence_line

        runs = [_run(i, _quality(60.0, 80.0)) for i in range(1, 7)]
        rates = {i: 0.01 * i for i in range(1, 7)}
        with _patched(runs, rates):
            report = build_calibration("tapin")
        self.assertEqual(report.recurrence_correlation, (None, 0))
        self.assertIn("collecting", recurrence_line(report))


class TestReportOnlyGaps(unittest.TestCase):
    def test_recurrence_line_reads_the_configured_minimum(self) -> None:
        from core import authenticity
        from core.video_grade import recurrence_line

        quality = {"style_recurrence_n": 8, "style_recurrence_opener": 2}
        with patch.object(authenticity, "_RECURRENCE_MIN", 2):
            self.assertIn("2/8", recurrence_line(quality))
        with patch.object(authenticity, "_RECURRENCE_MIN", 3):
            self.assertEqual(recurrence_line(quality), "")

    def test_ops_grade_prints_the_recurrence_line(self) -> None:
        import argparse

        from scripts.ops import cmd_grade

        quality = {
            "hook_score": 70,
            "authenticity_score": 80,
            "ungrounded_count": 0,
            "style_recurrence_n": 9,
            "style_recurrence_opener": 4,
        }
        record = _run(7, "{}")
        record.quality_json = __import__("json").dumps(quality)

        class _Repo:
            def get(self, run_id):
                return record

        args = argparse.Namespace(run_id=7, md=False, html=False, channel="tapin")
        out = io.StringIO()
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=_Repo()
            ),
            patch("core.video_grade.expert_panel_for_run", return_value=""),
            patch("core.grade_calibration.accuracy_line", return_value=None),
            redirect_stdout(out),
        ):
            cmd_grade(args)
        self.assertIn("same opener shape appears in 4/9", out.getvalue())


if __name__ == "__main__":
    unittest.main()
