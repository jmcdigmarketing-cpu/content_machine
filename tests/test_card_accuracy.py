"""#805 / #561: the report card never says how often it has been right.

#805 - the card prints a grade and a predicted engaged-rate and no indication
of whether either has ever tracked an outcome. Measured on `tapin`
(2026-09-20): grade vs engaged-rate has n=3, below `MIN_MEASURED`, because only
3 runs carry both a `quality_json` and a synced rate. But **composite** vs
engaged-rate has n=12 - composite_score is on every run row and needs no
quality dict - and nothing computed it.

#561 - `core/analyst_accuracy.build_accuracy_report` already backtests the
recommender (n=10, hit rate 40% on `tapin`) and only `core/intelligence_report`
ever read it. The card gives the advice; it should carry the track record.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch


class TestCompositeCorrelation(unittest.TestCase):
    """#805: the correlation that does not need a quality dict."""

    def test_composite_is_correlated_even_when_grades_are_too_few(self) -> None:
        from core.grade_calibration import build_calibration

        # Six runs with a composite and a measured rate; only one with quality.
        runs = [_run(i, composite=50.0 + i * 5, quality=(i == 1)) for i in range(1, 7)]
        rates = {i: 0.20 + i * 0.02 for i in range(1, 7)}

        with _patched(runs, rates):
            report = build_calibration("tapin")

        # The grade side is still gated - 1 run with quality, MIN_MEASURED is 5.
        self.assertIsNone(report.grade_correlation)
        # ...but the composite side has all six.
        self.assertEqual(report.composite_n, 6)
        self.assertIsNotNone(report.composite_correlation)
        self.assertGreater(report.composite_correlation, 0.9)

    def test_composite_correlation_is_gated_below_five(self) -> None:
        from core.grade_calibration import build_calibration

        runs = [_run(i, composite=50.0 + i * 5, quality=False) for i in range(1, 4)]
        rates = {i: 0.20 + i * 0.02 for i in range(1, 4)}

        with _patched(runs, rates):
            report = build_calibration("tapin")

        self.assertEqual(report.composite_n, 3)
        self.assertIsNone(report.composite_correlation)


class TestCardPrintsItsOwnAccuracy(unittest.TestCase):
    """#805 + #561: both lines reach the card the operator actually reads."""

    def test_the_card_carries_the_composite_correlation(self) -> None:
        from core.grade_calibration import accuracy_line

        runs = [_run(i, composite=50.0 + i * 5, quality=False) for i in range(1, 7)]
        rates = {i: 0.20 + i * 0.02 for i in range(1, 7)}

        with _patched(runs, rates):
            line = accuracy_line("tapin", use_cache=False)

        self.assertIsNotNone(line)
        self.assertIn("n=6", line)
        self.assertIn("composite", line.lower())

    def test_the_card_carries_the_recommender_hit_rate(self) -> None:
        from core.analyst_accuracy import hit_rate_line

        report = {
            "status": "ok",
            "metric": "engaged_rate",
            "runs_with_metrics": 10,
            "hit_rate": 0.4,
        }
        with patch("core.analyst_accuracy.build_accuracy_report", return_value=report):
            line = hit_rate_line("tapin", use_cache=False)

        self.assertIsNotNone(line)
        self.assertIn("40%", line)
        self.assertIn("10", line)

    def test_a_volume_gated_recommender_says_collecting_not_a_rate(self) -> None:
        from core.analyst_accuracy import hit_rate_line

        report = {"status": "volume_gated", "runs_with_metrics": 2, "min_runs_required": 5}
        with patch("core.analyst_accuracy.build_accuracy_report", return_value=report):
            line = hit_rate_line("tapin", use_cache=False)

        self.assertIsNotNone(line)
        self.assertIn("collecting", line.lower())
        self.assertNotIn("%", line)

    def test_display_grade_for_run_prints_both_lines(self) -> None:
        """The helper is only real if the operator's card actually shows it."""
        from core.video_grade import display_grade_for_run

        printed: list[str] = []
        record = _run(7, composite=64.0, quality=True)

        class _Repo:
            def get(self, run_id):
                return record

        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=_Repo(),
            ),
            patch("core.video_grade.render_expert_panel", return_value=""),
            patch("core.grade_calibration.accuracy_line", return_value="CARD-ACCURACY-LINE"),
            patch("core.analyst_accuracy.hit_rate_line", return_value="LOOP-HIT-RATE-LINE"),
        ):
            display_grade_for_run(7, print_fn=printed.append)

        text = "\n".join(printed)
        self.assertIn("CARD-ACCURACY-LINE", text)
        self.assertIn("LOOP-HIT-RATE-LINE", text)


def _run(run_id: int, *, composite: float, quality: bool):
    import json

    from storage.repositories.content_runs import ContentRunRecord

    payload = (
        json.dumps(
            {
                "hook_score": 70,
                "hook_verdict": "strong",
                "authenticity_score": 80,
                "authenticity_verdict": "ok",
                "ungrounded_count": 0,
                "grade_version": "v4",
            }
        )
        if quality
        else "{}"
    )
    return ContentRunRecord(
        id=run_id,
        channel_id="tapin",
        input_topic="t",
        selected_topic="t",
        status="published",
        composite_score=composite,
        title=f"run {run_id}",
        script_preview="a script",
        quality_json=payload,
    )


def _patched(runs, rates):
    class _Repo:
        def list_for_channel(self, channel_id, *, status=None):
            return runs

        def get(self, run_id):
            return next((r for r in runs if r.id == run_id), None)

    from contextlib import ExitStack

    stack = ExitStack()
    stack.enter_context(
        patch("storage.repositories.content_runs.get_content_run_repository", return_value=_Repo())
    )
    stack.enter_context(patch("core.engagement_predictor.run_engagement_map", return_value=rates))
    stack.enter_context(patch("config.channels.resolve_channel_id", return_value="tapin"))
    stack.enter_context(patch("core.grade_calibration._thumbnail_scores", return_value={}))
    return stack


if __name__ == "__main__":
    unittest.main()
