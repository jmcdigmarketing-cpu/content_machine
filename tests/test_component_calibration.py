"""#824: the report card is anti-predictive (r=-0.32, n=12) - re-measure per component,
and say what n would settle it.

|r|=0.32 at n=12 is not significant; the item says twice not to retune the rubric on it.
What can be done now is the measurement the number lacks: the correlation of each grade
component with engaged-rate, on the same rows, and the n at which the observed |r| would
clear p<0.05. No `GRADE_VERSION` bump - nothing about how a grade is computed changes.

Fixtures follow tests/test_calibration_coverage.py: a fake run repo plus a patched
engagement map. Rows carry a recorded grade snapshot (#808) so `components` is filled.
"""

from __future__ import annotations

import json
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from storage.repositories.content_runs import ContentRunRecord


def _quality(hook: float, authenticity: float, *, recurrence_n: int | None = None) -> str:
    q = {
        "hook_score": hook,
        "authenticity_score": authenticity,
        "ungrounded_count": 0,
        "grade_version": "v4",
        # The grade must vary or its Pearson is undefined and #824's lines stay silent.
        "grade_score": round(0.4 * hook + 0.4 * authenticity + 10, 1),
        "grade_letter": "B",
        "grade_components": {
            "hook": {"score": hook, "weight": 0.28},
            "authenticity": {"score": authenticity, "weight": 0.28},
        },
    }
    if recurrence_n is not None:
        q["style_recurrence_n"] = recurrence_n
        q["style_recurrence_opener"] = recurrence_n
    return json.dumps(q)


def _run(run_id: int, quality: str) -> ContentRunRecord:
    return ContentRunRecord(
        id=run_id,
        channel_id="tapin",
        input_topic="t",
        selected_topic="t",
        status="published",
        composite_score=60.0,
        title=f"run {run_id}",
        quality_json=quality,
    )


def _patched(runs, rates):
    class _Repo:
        def list_for_channel(self, channel_id, *, status=None):
            return runs

        def get(self, run_id):
            return next((r for r in runs if r.id == run_id), None)

    stack = ExitStack()
    stack.enter_context(
        patch("storage.repositories.content_runs.get_content_run_repository", return_value=_Repo())
    )
    stack.enter_context(patch("core.engagement_predictor.run_engagement_map", return_value=rates))
    stack.enter_context(patch("config.channels.resolve_channel_id", return_value="tapin"))
    stack.enter_context(patch("core.grade_calibration._thumbnail_scores", return_value={}))
    return stack


class TestSignificance(unittest.TestCase):
    def test_n_for_the_observed_r(self) -> None:
        from core.grade_calibration import n_for_significance

        self.assertEqual(n_for_significance(0.32), 36)
        self.assertEqual(n_for_significance(-0.32), 36)
        self.assertEqual(n_for_significance(0.5), 14)
        self.assertIsNone(n_for_significance(0.0))
        self.assertIsNone(n_for_significance(None))


class TestPerComponent(unittest.TestCase):
    def _report(self):
        from core.grade_calibration import build_calibration

        # hook rises with engagement; authenticity is flat -> r undefined/None.
        hooks = [40, 50, 60, 70, 80, 90]
        runs = [_run(i, _quality(hooks[i - 1], 80.0)) for i in range(1, 7)]
        rates = {i: 0.01 * i for i in range(1, 7)}
        with _patched(runs, rates):
            return build_calibration("tapin")

    def test_each_component_gets_its_own_correlation_and_n(self) -> None:
        report = self._report()
        r, n = report.component_correlations["hook"]
        self.assertEqual(n, 6)
        self.assertIsNotNone(r)
        self.assertGreater(r, 0.99)
        r_auth, n_auth = report.component_correlations["authenticity"]
        self.assertEqual(n_auth, 6)
        self.assertIsNone(r_auth, "a constant component has no correlation, not r=0")

    def test_the_lines_say_do_not_retune_below_significance(self) -> None:
        from core.grade_calibration import component_line, significance_line

        report = self._report()
        comp = component_line(report)
        self.assertIn("hook", comp)
        self.assertIn("r=+", comp)
        sig = significance_line(report)
        self.assertIn("needs n", sig)

    def test_render_prints_them(self) -> None:
        from core.grade_calibration import render

        hooks = [40, 50, 60, 70, 80, 90]
        runs = [_run(i, _quality(hooks[i - 1], 80.0)) for i in range(1, 7)]
        rates = {i: 0.01 * i for i in range(1, 7)}
        with _patched(runs, rates):
            text = render("tapin")
        self.assertIn("per component", text.lower())
        self.assertIn("needs n", text)


if __name__ == "__main__":
    unittest.main()
