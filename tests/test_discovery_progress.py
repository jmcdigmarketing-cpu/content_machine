"""Tests for live per-phase discovery progress reporting."""

import unittest
from unittest.mock import patch

from core import pipeline
from core.ui import DiscoverySpinner


class TestDiscoveryProgress(unittest.TestCase):
    @patch("core.pipeline.ensure_competitor_snapshot", create=True)
    @patch("core.pipeline.composite_score", return_value=10.0)
    @patch("core.pipeline.build_registry", return_value={"youtube": {"score": 1}})
    @patch("core.pipeline.generate_variants")
    def test_progress_callback_reports_phases(
        self, mock_variants, mock_registry, mock_score, _snap
    ):
        mock_variants.return_value = ["v1", "v2", "v3"]
        events: list[tuple] = []

        with patch.dict("os.environ", {"COMPETITOR_SYNC_ON_DISCOVERY": "off"}):
            pipeline.run_discovery(
                "some topic",
                variant_limit=3,
                channel_id="tapin",
                progress=lambda phase, done=None, total=None: events.append((phase, done, total)),
            )

        phases = [e[0] for e in events]
        self.assertIn("Loading history", phases)
        self.assertIn("Fetching signals & variants", phases)
        self.assertIn("Scoring variants", phases)

        # Scoring should report incremental progress up to the variant count.
        scoring = [e for e in events if e[0] == "Scoring variants"]
        self.assertEqual(scoring[-1], ("Scoring variants", 3, 3))

    @patch("core.pipeline.ensure_competitor_snapshot", create=True)
    @patch("core.pipeline.composite_score", return_value=10.0)
    @patch("core.pipeline.build_registry", return_value={"youtube": {"score": 1}})
    @patch("core.pipeline.generate_variants")
    def test_results_in_deterministic_candidate_order(
        self, mock_variants, mock_registry, mock_score, _snap
    ):
        mock_variants.return_value = ["alpha", "bravo", "charlie"]
        with patch.dict("os.environ", {"COMPETITOR_SYNC_ON_DISCOVERY": "off"}):
            result = pipeline.run_discovery("topic", variant_limit=3, channel_id="tapin")
        ordered = [v for v, _, _ in result.evaluated]
        self.assertEqual(ordered, ["alpha", "bravo", "charlie"])

    def test_progress_callback_optional(self):
        # run_discovery must work without a progress callback (back-compat).
        with (
            patch("core.pipeline.generate_variants", return_value=[]),
            patch("core.pipeline.build_registry", return_value={}),
            patch("core.pipeline.ensure_competitor_snapshot", create=True),
            patch.dict("os.environ", {"COMPETITOR_SYNC_ON_DISCOVERY": "off"}),
        ):
            result = pipeline.run_discovery("topic", channel_id="tapin")
        self.assertEqual(result.evaluated, [])


class TestSpinnerReport(unittest.TestCase):
    def test_report_sets_phase_with_count(self):
        spinner = DiscoverySpinner("Discovery")
        spinner.report("Scoring variants", 2, 5)
        self.assertEqual(spinner._current_stage(0.0), "Scoring variants 2/5")

    def test_report_sets_phase_without_count(self):
        spinner = DiscoverySpinner("Discovery")
        spinner.report("Loading history")
        self.assertEqual(spinner._current_stage(0.0), "Loading history")

    def test_time_based_fallback_when_no_phase(self):
        spinner = DiscoverySpinner("Discovery")
        # No report() call -> falls back to time-based stage guesses.
        self.assertEqual(spinner._current_stage(0.0), "Fetching signals")
        self.assertEqual(spinner._current_stage(20.0), "Scoring variants")


if __name__ == "__main__":
    unittest.main()
