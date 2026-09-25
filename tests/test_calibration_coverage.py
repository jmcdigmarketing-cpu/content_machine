"""#818: `ops calibration` reads "collecting" and never says why.

Measured on `tapin` while building #805: 87 runs, **37** carry a `quality_json`,
**12** carry a synced engaged-rate, and **3** carry both. `MIN_MEASURED` is 5,
so the grade correlation is starved by *history* - quality persistence landed
after most of the publishing did - not by volume. Nothing is broken, but the
existing line ("collecting (3/5 measured runs with quality)") reads like a
volume problem and invites someone to re-discover the real reason.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from storage.repositories.content_runs import ContentRunRecord


def _run(run_id: int, *, quality: str = "{}", composite: float = 60.0):
    return ContentRunRecord(
        id=run_id,
        channel_id="tapin",
        input_topic="t",
        selected_topic="t",
        status="published",
        composite_score=composite,
        title=f"run {run_id}",
        quality_json=quality,
    )


_QUALITY = '{"hook_score": 70, "authenticity_score": 80, "ungrounded_count": 0}'


def _patched(runs, rates):
    from contextlib import ExitStack

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


class TestCoverageLine(unittest.TestCase):
    def test_it_names_all_three_populations(self) -> None:
        from core.grade_calibration import build_calibration, coverage_line

        # 6 runs: 4 carry quality, 3 carry an outcome, 2 carry both.
        runs = [_run(i, quality=_QUALITY if i <= 4 else "{}") for i in range(1, 7)]
        rates = {3: 0.3, 4: 0.4, 5: 0.5}

        with _patched(runs, rates):
            line = coverage_line(build_calibration("tapin"), runs_total=len(runs))

        self.assertIn("6", line)  # runs
        self.assertIn("4", line)  # with a grade
        self.assertIn("3", line)  # with an outcome
        self.assertIn("2", line)  # with both

    def test_it_says_history_not_volume(self) -> None:
        """The whole point: stop this reading like 'publish more'."""
        from core.grade_calibration import build_calibration, coverage_line

        runs = [_run(i, quality=_QUALITY if i <= 4 else "{}") for i in range(1, 7)]
        with _patched(runs, {3: 0.3, 4: 0.4, 5: 0.5}):
            line = coverage_line(build_calibration("tapin"), runs_total=len(runs))
        self.assertIn("one per publish", line.lower())

    def test_a_fully_covered_archive_says_nothing(self) -> None:
        """No line when every measured run already carries a grade."""
        from core.grade_calibration import build_calibration, coverage_line

        runs = [_run(i, quality=_QUALITY) for i in range(1, 7)]
        rates = {i: 0.1 * i for i in range(1, 7)}
        with _patched(runs, rates):
            line = coverage_line(build_calibration("tapin"), runs_total=len(runs))
        self.assertEqual(line, "")


class TestItReachesTheWeeklyReport(unittest.TestCase):
    def test_the_weekly_report_carries_it(self) -> None:
        from analytics.weekly_report import format_report

        report = {
            "channel_id": "tapin",
            "ready": True,
            "n": 5,
            "baseline": 0.3,
            "dimensions": {},
            "rows": [{}] * 5,
        }
        with (
            patch("core.grade_calibration.coverage_line", return_value="COVERAGE-LINE"),
            patch("core.grade_calibration.summary_line", return_value="summary"),
            patch("core.grade_calibration.build_calibration"),
        ):
            text = format_report(report)
        self.assertIn("COVERAGE-LINE", text)


if __name__ == "__main__":
    unittest.main()
