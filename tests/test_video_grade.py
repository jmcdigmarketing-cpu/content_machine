"""Pillar 2 (Video Grading) tests — report card math, data-gated predictor,
calibration correlations, prompt-eval rubric, analyst-accuracy realignment."""

import json
import unittest
from unittest.mock import MagicMock, patch

from core import engagement_predictor, grade_calibration
from core.video_grade import grade_from_parts, grade_run, render_grade

FULL_QUALITY = {
    "hook_score": 80,
    "hook_verdict": "strong",
    "authenticity_score": 90,
    "authenticity_verdict": "ok",
    "ungrounded_count": 0,
    "trade_warning_count": 0,
}


class TestGradeFromParts(unittest.TestCase):
    def test_full_quality_grades_high(self):
        grade = grade_from_parts(quality=FULL_QUALITY, composite_score=75.0)
        self.assertGreaterEqual(grade.score, 80)
        self.assertIn(grade.letter, ("A", "B"))
        names = [c.name for c in grade.components]
        self.assertEqual(names, ["hook", "authenticity", "grounding", "topic"])
        # Weights renormalize to 1.
        self.assertAlmostEqual(sum(c.weight for c in grade.components), 1.0, places=2)

    def test_ungrounded_specifics_penalize(self):
        clean = grade_from_parts(quality=FULL_QUALITY, composite_score=75.0)
        dirty = grade_from_parts(
            quality={**FULL_QUALITY, "ungrounded_count": 3}, composite_score=75.0
        )
        self.assertLess(dirty.score, clean.score)
        grounding = next(c for c in dirty.components if c.name == "grounding")
        self.assertEqual(grounding.score, 25.0)  # 100 - 3*25

    def test_missing_components_renormalize(self):
        grade = grade_from_parts(quality={"hook_score": 60}, composite_score=0)
        self.assertEqual(len(grade.components), 1)
        self.assertEqual(grade.components[0].weight, 1.0)
        self.assertEqual(grade.score, 60.0)

    def test_thumbnail_joins_when_present(self):
        grade = grade_from_parts(
            quality={**FULL_QUALITY, "thumbnail_overall": 50.0}, composite_score=75.0
        )
        self.assertIn("thumbnail", [c.name for c in grade.components])

    def test_empty_quality_is_f(self):
        grade = grade_from_parts(quality={}, composite_score=0)
        self.assertEqual(grade.letter, "F")
        self.assertEqual(grade.score, 0.0)

    def test_render_contains_letter_and_components(self):
        out = render_grade(grade_from_parts(quality=FULL_QUALITY, composite_score=75.0))
        self.assertIn("Report card:", out)
        self.assertIn("hook", out)
        self.assertIn("authenticity", out)


class TestGradeRun(unittest.TestCase):
    def test_grades_persisted_run(self):
        record = MagicMock()
        record.composite_score = 70.0
        record.channel_id = None  # skip predictor
        record.quality_json = json.dumps(FULL_QUALITY)
        repo = MagicMock()
        repo.get.return_value = record
        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            grade = grade_run(4)
        self.assertIsNotNone(grade)
        self.assertGreater(grade.score, 0)

    def test_missing_quality_returns_none(self):
        record = MagicMock()
        record.quality_json = "{}"
        repo = MagicMock()
        repo.get.return_value = record
        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            self.assertIsNone(grade_run(4))


def _measured_runs(n, *, hook_spread=True):
    """n runs with quality + engagement where higher hook -> higher engagement."""
    runs, engagement = [], {}
    for i in range(n):
        run = MagicMock()
        run.id = i + 1
        hook = 40 + (i * 40 // max(1, n - 1)) if hook_spread else 60
        run.quality_json = json.dumps({"hook_score": hook, "authenticity_score": 80})
        run.composite_score = 70.0
        run.title = f"Video {i + 1}"
        run.selected_topic = f"Topic {i + 1}"
        runs.append(run)
        engagement[run.id] = 0.30 + (hook - 60) * 0.002  # correlated with hook
    return runs, engagement


class TestEngagementPredictor(unittest.TestCase):
    def test_gated_below_min_samples(self):
        runs, engagement = _measured_runs(5)
        repo = MagicMock()
        repo.list_for_channel.return_value = runs
        with (
            patch.object(engagement_predictor, "run_engagement_map", return_value=engagement),
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=repo,
            ),
        ):
            self.assertIsNone(
                engagement_predictor.predict_engaged_rate(
                    "tapin", quality={"hook_score": 70, "authenticity_score": 80}
                )
            )

    def test_predicts_above_gate_and_direction(self):
        runs, engagement = _measured_runs(16)
        repo = MagicMock()
        repo.list_for_channel.return_value = runs
        with (
            patch.object(engagement_predictor, "run_engagement_map", return_value=engagement),
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=repo,
            ),
        ):
            low = engagement_predictor.predict_engaged_rate(
                "tapin", quality={"hook_score": 40, "authenticity_score": 80}
            )
            high = engagement_predictor.predict_engaged_rate(
                "tapin", quality={"hook_score": 80, "authenticity_score": 80}
            )
        self.assertIsNotNone(low)
        self.assertIsNotNone(high)
        self.assertGreater(high.rate, low.rate)  # better hook -> higher prediction
        self.assertEqual(high.n, 16)
        self.assertIn("n=16", high.note)

    def test_no_quality_returns_none(self):
        self.assertIsNone(engagement_predictor.predict_engaged_rate("tapin", quality={}))


class TestCalibration(unittest.TestCase):
    def test_correlation_over_measured_runs(self):
        runs, engagement = _measured_runs(8)
        repo = MagicMock()
        repo.list_for_channel.return_value = runs
        with (
            patch.object(grade_calibration, "_thumbnail_scores", return_value={}),
            patch("core.engagement_predictor.run_engagement_map", return_value=engagement),
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=repo,
            ),
        ):
            report = grade_calibration.build_calibration("tapin")
        self.assertEqual(report.measured, 8)
        self.assertIsNotNone(report.grade_correlation)
        self.assertGreater(report.grade_correlation, 0.5)  # hook drives both
        line = grade_calibration.summary_line(report)
        self.assertIn("r=+", line)

    def test_collecting_below_min(self):
        runs, engagement = _measured_runs(2)
        repo = MagicMock()
        repo.list_for_channel.return_value = runs
        with (
            patch.object(grade_calibration, "_thumbnail_scores", return_value={}),
            patch("core.engagement_predictor.run_engagement_map", return_value=engagement),
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=repo,
            ),
        ):
            report = grade_calibration.build_calibration("tapin")
        self.assertIsNone(report.grade_correlation)
        self.assertIn("collecting", grade_calibration.summary_line(report))

    def test_thumbnail_join_correlation(self):
        runs, engagement = _measured_runs(6)
        thumbs = {rid: 40.0 + rate * 100 for rid, rate in engagement.items()}
        repo = MagicMock()
        repo.list_for_channel.return_value = runs
        with (
            patch.object(grade_calibration, "_thumbnail_scores", return_value=thumbs),
            patch("core.engagement_predictor.run_engagement_map", return_value=engagement),
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=repo,
            ),
        ):
            report = grade_calibration.build_calibration("tapin")
        self.assertEqual(report.thumbnail_n, 6)
        self.assertGreater(report.thumbnail_correlation, 0.9)


class TestPromptEvalRubric(unittest.TestCase):
    def test_score_script_rubric(self):
        from core.prompt_evals import score_script

        script = (
            "Topuria is undefeated at 16-0 and defends against Gaethje at UFC 350. "
            "But here's the thing about this matchup. " + "Word " * 80
        )
        scores = score_script(
            script,
            key_facts=["Ilia Topuria defends against Justin Gaethje at UFC 350"],
            length_choice="2",
        )
        self.assertEqual(scores["rubric_version"], "v1")
        self.assertIsNotNone(scores["hook_score"])
        self.assertEqual(scores["filler_count"], 1)
        self.assertIn("ungrounded_count", scores)

    def test_compare_needs_two_runs(self):
        import tempfile

        from core import prompt_evals

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(prompt_evals, "EVALS_DIR", tmp):
                self.assertIn("Need two eval runs", prompt_evals.compare_latest())


class TestAnalystAccuracyRealignment(unittest.TestCase):
    def _run(self, run_id, score):
        run = MagicMock()
        run.id = run_id
        run.composite_score = score
        run.selected_topic = f"T{run_id}"
        run.input_topic = f"T{run_id}"
        run.status = "rendered"
        return run

    def _log(self, run_id, metrics):
        log = MagicMock()
        log.content_run_id = run_id
        log.youtube_video_id = f"v{run_id}"
        log.metrics_json = json.dumps(metrics)
        return log

    def test_uses_engaged_rate_when_available(self):
        from core.analyst_accuracy import build_accuracy_report

        runs = [self._run(i, 80.0) for i in range(1, 7)]
        logs = [self._log(i, {"views": 100, "engaged_rate": 0.2 + i * 0.05}) for i in range(1, 7)]
        runs_repo = MagicMock()
        runs_repo.list_for_channel.return_value = runs
        publish_repo = MagicMock()
        publish_repo.list_uploaded_for_channel.return_value = logs
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=runs_repo,
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=publish_repo,
            ),
        ):
            report = build_accuracy_report("tapin")
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["metric"], "engaged_rate")
        self.assertIn("engaged-rate", report["summary"])

    def test_views_fallback_without_engagement(self):
        from core.analyst_accuracy import build_accuracy_report

        runs = [self._run(i, 80.0) for i in range(1, 7)]
        logs = [self._log(i, {"views": 100 + i}) for i in range(1, 7)]
        runs_repo = MagicMock()
        runs_repo.list_for_channel.return_value = runs
        publish_repo = MagicMock()
        publish_repo.list_uploaded_for_channel.return_value = logs
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=runs_repo,
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=publish_repo,
            ),
        ):
            report = build_accuracy_report("tapin")
        self.assertEqual(report["metric"], "views")


if __name__ == "__main__":
    unittest.main()
