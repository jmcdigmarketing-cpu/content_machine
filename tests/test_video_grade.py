"""Pillar 2 (Video Grading) tests — report card math, data-gated predictor,
calibration correlations, prompt-eval rubric, analyst-accuracy realignment,
optional Expert-Panel qualitative section (Pillar 6)."""

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from core import engagement_predictor, grade_calibration
from core.providers import ProviderResult
from core.video_grade import (
    display_grade_for_run,
    expert_panel_for_run,
    grade_from_parts,
    grade_run,
    render_expert_panel,
    render_grade,
)

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

    def test_fact_engine_outputs_penalize(self):
        # Pillar 3: unsupported claims (15), conflicts (15), tier warnings (10).
        dirty = grade_from_parts(
            quality={
                **FULL_QUALITY,
                "unsupported_claim_count": 2,
                "fact_conflict_count": 1,
                "tier_warning_count": 2,
            },
            composite_score=75.0,
        )
        grounding = next(c for c in dirty.components if c.name == "grounding")
        self.assertEqual(grounding.score, 35.0)  # 100 - 2*15 - 15 - 2*10
        self.assertIn("unsupported claim", grounding.note)
        self.assertIn("fact conflict", grounding.note)
        self.assertIn("tier warning", grounding.note)

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


class TestExpertPanelSection(unittest.TestCase):
    """Pillar 6 — optional qualitative panel beside the report card.

    Invariants: OFF by default (output byte-identical to the numeric-only card),
    present only when EXPERT_PANEL_ENABLED=true, and fail-open — a not-ok panel
    result or a raising panel never changes the numeric score or breaks grading.
    """

    RUN_ID = 4

    def setUp(self):
        # Restore the operator's env after each test; start from the gate unset.
        patcher = patch.dict(os.environ, {}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("EXPERT_PANEL_ENABLED", None)

    def _record(self):
        record = MagicMock()
        record.composite_score = 70.0
        record.channel_id = None  # skip predictor
        record.quality_json = json.dumps(FULL_QUALITY)
        record.script_preview = "Hook line. Body of the draft script."
        return record

    def _display_lines(self):
        repo = MagicMock()
        repo.get.return_value = self._record()
        lines: list[str] = []
        with patch(
            "storage.repositories.content_runs.get_content_run_repository", return_value=repo
        ):
            display_grade_for_run(self.RUN_ID, print_fn=lines.append)
        return lines

    def _numeric_only_lines(self):
        """What display_grade_for_run printed before the panel existed."""
        grade = grade_from_parts(quality=FULL_QUALITY, composite_score=70.0, channel_id=None)
        return [""] + [f"  {line}" for line in render_grade(grade).splitlines()]

    # -- disabled (default) ------------------------------------------------

    def test_off_by_default_output_byte_identical(self):
        lines = self._display_lines()
        self.assertEqual(lines, self._numeric_only_lines())
        self.assertNotIn("Expert panel", "\n".join(lines))

    def test_off_by_default_section_is_empty_without_llm(self):
        # No LLM mock in scope: disabled must return "" before any LLM work.
        self.assertEqual(render_expert_panel("draft text"), "")
        self.assertEqual(expert_panel_for_run(self.RUN_ID), "")

    # -- enabled -----------------------------------------------------------

    def test_enabled_panel_section_present(self):
        with (
            patch.dict(os.environ, {"EXPERT_PANEL_ENABLED": "true"}, clear=False),
            patch(
                "core.grade._load_personas",
                return_value=[("skeptical_editor", "You are a skeptical editor.")],
            ),
            patch("core.llm_router.complete", return_value="Strong hook; tighten the middle."),
        ):
            section = render_expert_panel("Hook line. Body.", "tapin")
        self.assertIn("Expert panel", section)
        self.assertIn("does not affect the score", section)
        self.assertIn("skeptical_editor", section)
        self.assertIn("tighten the middle", section)

    def test_enabled_panel_shown_beside_report_card(self):
        with (
            patch.dict(os.environ, {"EXPERT_PANEL_ENABLED": "true"}, clear=False),
            patch(
                "core.grade.expert_panel_review",
                return_value=ProviderResult.success(
                    "expert_panel",
                    "expert_panel",
                    data=[{"persona": "skeptical_editor", "review": "Solid draft."}],
                ),
            ),
        ):
            lines = self._display_lines()
        # The numeric card is byte-identical; the panel is appended after it.
        numeric = self._numeric_only_lines()
        self.assertEqual(lines[: len(numeric)], numeric)
        panel_text = "\n".join(lines[len(numeric) :])
        self.assertIn("Expert panel", panel_text)
        self.assertIn("Solid draft.", panel_text)

    # -- fail-open ---------------------------------------------------------

    def test_fail_open_not_ok_result_keeps_grading_and_score(self):
        with (
            patch.dict(os.environ, {"EXPERT_PANEL_ENABLED": "true"}, clear=False),
            patch(
                "core.grade.expert_panel_review",
                return_value=ProviderResult.fail_open("expert_panel", "no persona replied"),
            ),
        ):
            lines = self._display_lines()
        self.assertEqual(lines, self._numeric_only_lines())

    def test_fail_open_raising_panel_keeps_grading_and_score(self):
        with (
            patch.dict(os.environ, {"EXPERT_PANEL_ENABLED": "true"}, clear=False),
            patch("core.grade.expert_panel_review", side_effect=RuntimeError("llm down")),
        ):
            lines = self._display_lines()
        self.assertEqual(lines, self._numeric_only_lines())

    def test_fail_open_missing_record(self):
        repo = MagicMock()
        repo.get.return_value = None
        with (
            patch.dict(os.environ, {"EXPERT_PANEL_ENABLED": "true"}, clear=False),
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),
        ):
            self.assertEqual(expert_panel_for_run(self.RUN_ID), "")


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
