"""Tests for core/experiments.py — script-lever A/B lifecycle + attribution.

Storage isolated to a temp file; engagement joins mocked (no DB)."""

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core import batch_generation as bg
from core import experiments as ex
from core.experiment_levers import arms, directive


class ExperimentCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        import config.paths as paths

        self._patch = patch.object(
            paths, "EXPERIMENTS_FILE", os.path.join(self._tmp.name, "experiments.json")
        )
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()


class TestLifecycle(ExperimentCase):
    def test_start_status_stop(self):
        self.assertIsNone(ex.active_experiment("tapin"))
        ex.start_experiment("tapin", "hook_style")
        active = ex.active_experiment("tapin")
        self.assertEqual(active["lever"], "hook_style")
        # Per-channel isolation.
        self.assertIsNone(ex.active_experiment("moneywise"))
        ex.stop_experiment("tapin")
        self.assertIsNone(ex.active_experiment("tapin"))

    def test_unknown_lever_rejected(self):
        with self.assertRaises(ValueError):
            ex.start_experiment("tapin", "nonsense_lever")

    def test_next_arm_none_without_experiment(self):
        self.assertIsNone(ex.next_arm("tapin"))


class TestAssignment(ExperimentCase):
    def test_round_robin_alternates_arms(self):
        ex.start_experiment("tapin", "hook_style")
        lever_arms = arms("hook_style")

        first = ex.next_arm("tapin")
        self.assertEqual(first[0], "hook_style")
        self.assertEqual(first[1], lever_arms[0])  # ties resolve in declared order
        self.assertEqual(first[2], directive("hook_style", first[1]))
        ex.record_assignment("tapin", 101, first[0], first[1])

        second = ex.next_arm("tapin")
        self.assertEqual(second[1], lever_arms[1])  # least-used arm next
        ex.record_assignment("tapin", 102, second[0], second[1])

        third = ex.next_arm("tapin")
        self.assertEqual(third[1], lever_arms[0])  # back to parity → declared order

    def test_assignment_without_run_id_is_skipped(self):
        ex.start_experiment("tapin", "hook_style")
        ex.record_assignment("tapin", None, "hook_style", arms("hook_style")[0])
        report = ex.experiment_report("tapin")
        self.assertEqual(sum(report["assigned"].values()), 0)


class TestAttribution(ExperimentCase):
    def _seed(self, outcomes: dict[int, float], per_arm: int = 6):
        """Assign run-ids alternately and mock their engagement."""
        ex.start_experiment("tapin", "hook_style")
        a, b = arms("hook_style")
        run_id = 1
        for _ in range(per_arm):
            for arm in (a, b):
                ex.record_assignment("tapin", run_id, "hook_style", arm)
                run_id += 1
        return outcomes

    def test_arm_outcomes_join_engagement(self):
        a, b = arms("hook_style")
        # Odd run-ids = arm a, even = arm b (from the alternating seed order).
        engagement = {i: (0.5 if i % 2 == 1 else 0.1) for i in range(1, 13)}
        self._seed(engagement)
        with patch.object(ex, "_run_engagement", return_value=engagement):
            out = ex.arm_outcomes("tapin", "hook_style")
        self.assertEqual(len(out[a]), 6)
        self.assertEqual(len(out[b]), 6)
        self.assertTrue(all(r == 0.5 for r in out[a]))
        self.assertTrue(all(r == 0.1 for r in out[b]))

    def test_report_declares_winner_with_clear_data(self):
        a, _ = arms("hook_style")
        engagement = {i: (0.5 if i % 2 == 1 else 0.1) for i in range(1, 13)}
        self._seed(engagement)
        with patch.object(ex, "_run_engagement", return_value=engagement):
            report = ex.experiment_report("tapin")
        self.assertEqual(report["evaluation"]["status"], "winner")
        self.assertEqual(report["evaluation"]["winner"], a)

    def test_report_collecting_with_few_samples(self):
        ex.start_experiment("tapin", "hook_style")
        a, b = arms("hook_style")
        ex.record_assignment("tapin", 1, "hook_style", a)
        ex.record_assignment("tapin", 2, "hook_style", b)
        with patch.object(ex, "_run_engagement", return_value={1: 0.5, 2: 0.1}):
            report = ex.experiment_report("tapin")
        self.assertEqual(report["evaluation"]["status"], "collecting")
        self.assertIsNone(report["evaluation"]["winner"])


class TestBatchIntegration(ExperimentCase):
    """batch_generation picks up the active experiment's arm directive."""

    def test_draft_uses_directive_and_records_assignment(self):
        ex.start_experiment("tapin", "hook_style")
        first_arm = arms("hook_style")[0]

        discovery = SimpleNamespace(evaluated=[("Angle", 80.0, {})], channel_id="tapin", timings={})
        result = SimpleNamespace(
            aborted=False,
            abort_reason=None,
            script="Hook!\nBody.",
            title="T",
            description="",
            tags=[],
            run_id=7,
            features={},
        )
        with (
            tempfile.TemporaryDirectory() as out_tmp,
            patch("core.output_paths.channel_output_root", return_value=out_tmp),
            patch("core.fact_enrichment.enrich_facts", return_value=""),
            patch(
                "core.authenticity.evaluate_authenticity",
                return_value=SimpleNamespace(verdict="ok"),
            ),
            patch(
                "core.length_recommender.get_recommended_length",
                side_effect=RuntimeError("no analytics"),
            ),
            patch("core.pipeline.run_discovery", return_value=discovery),
            patch("core.pipeline.run_pipeline", return_value=result) as rp,
        ):
            out = bg.generate_draft("UFC 320", "tapin")

        self.assertTrue(out.ok)
        self.assertEqual(out.experiment_arm, f"hook_style={first_arm}")
        self.assertEqual(rp.call_args.kwargs["creative_brief"], directive("hook_style", first_arm))
        report = ex.experiment_report("tapin")
        self.assertEqual(report["assigned"][first_arm], 1)


if __name__ == "__main__":
    unittest.main()
