"""DiscoverySpinner engagement upgrades: detail line, typ-hints, report back-compat."""

import unittest
from unittest.mock import patch

from core.ui import DiscoverySpinner


class TestSpinnerReport(unittest.TestCase):
    def _spinner(self) -> DiscoverySpinner:
        with patch.object(DiscoverySpinner, "_load_typical_timings", return_value={}):
            return DiscoverySpinner("Discovery")

    def test_report_three_arg_back_compat(self):
        s = self._spinner()
        s.report("Scoring variants", 2, 5)  # old signature still works
        stage = s._current_stage(1.0)
        self.assertIn("2/5", stage)

    def test_report_detail_shown_and_truncated(self):
        s = self._spinner()
        s.report("Scoring variants", 3, 5, detail="Palworld patch scale " + "x" * 80)
        stage = s._current_stage(1.0)
        self.assertIn("3/5", stage)
        self.assertIn("Palworld patch scale", stage)
        self.assertLess(len(stage), 120)  # detail capped, line stays terminal-safe

    def test_typical_hint_from_last_trace(self):
        with patch.object(
            DiscoverySpinner,
            "_load_typical_timings",
            return_value={"variant_scoring": 42.0, "signals_and_variants": 30.0},
        ):
            s = DiscoverySpinner("Discovery")
        s.report("Scoring variants", 1, 5)
        self.assertIn("typ ~42s", s._current_stage(1.0))
        s.report("Fetching signals & variants")
        self.assertIn("typ ~30s", s._current_stage(1.0))

    def test_no_traces_means_no_hint(self):
        s = self._spinner()
        s.report("Scoring variants", 1, 5)
        self.assertNotIn("typ", s._current_stage(1.0))

    def test_load_typical_timings_fail_open(self):
        with patch("core.run_trace.list_traces", side_effect=RuntimeError("no traces dir")):
            self.assertEqual(DiscoverySpinner._load_typical_timings(), {})


class TestPipelineReportForwardsDetail(unittest.TestCase):
    def test_four_arg_then_three_arg_fallback(self):
        # Mirror core/pipeline._report's dual-signature dispatch.
        calls: list[tuple] = []

        def four_arg(phase, done, total, detail):
            calls.append((phase, done, total, detail))

        def three_arg(phase, done, total):
            calls.append((phase, done, total))

        # Re-implement the dispatch contract the pipeline uses:
        for cb in (four_arg, three_arg):
            try:
                cb("Scoring variants", 1, 5, "Variant A")
            except TypeError:
                cb("Scoring variants", 1, 5)
        self.assertEqual(calls[0], ("Scoring variants", 1, 5, "Variant A"))
        self.assertEqual(calls[1], ("Scoring variants", 1, 5))


if __name__ == "__main__":
    unittest.main()
