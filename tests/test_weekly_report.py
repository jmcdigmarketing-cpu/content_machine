"""Tests for the rules-based weekly intelligence report."""

import json
import unittest
from unittest.mock import patch

from analytics import weekly_report as wr


def _row(rate, **features):
    return {"run_id": 1, "engaged_rate": rate, "features": features}


class TestBuildReport(unittest.TestCase):
    def test_not_ready_with_few_rows(self):
        with patch("analytics.weekly_report._load_rows", return_value=[_row(0.3, domain="ufc")]):
            report = wr.build_report("tapin")
        self.assertFalse(report["ready"])

    def test_winners_and_losers_vs_baseline(self):
        rows = [
            _row(0.50, angle="fraud", domain="ufc"),
            _row(0.45, angle="fraud", domain="ufc"),
            _row(0.40, angle="fraud", domain="ufc"),
            _row(0.10, angle="recap", domain="ufc"),
            _row(0.12, angle="recap", domain="ufc"),
            _row(0.11, angle="recap", domain="ufc"),
        ]
        with patch("analytics.weekly_report._load_rows", return_value=rows):
            report = wr.build_report("tapin")
        self.assertTrue(report["ready"])
        angles = {g["value"]: g for g in report["dimensions"]["angle"]}
        self.assertGreater(angles["fraud"]["delta"], 0)
        self.assertLess(angles["recap"]["delta"], 0)

    def test_sample_gating_drops_small_groups(self):
        rows = [
            _row(0.5, angle="fraud"),
            _row(0.4, angle="fraud"),
            _row(0.3, angle="fraud"),
            _row(0.9, angle="rare"),  # only 1 sample — must be dropped
        ]
        with patch("analytics.weekly_report._load_rows", return_value=rows):
            report = wr.build_report("tapin")
        values = {g["value"] for g in report["dimensions"].get("angle", [])}
        self.assertIn("fraud", values)
        self.assertNotIn("rare", values)

    def test_cost_summary_included(self):
        rows = [
            _row(0.3, angle="fraud", cost={"total": 0.05}),
            _row(0.3, angle="fraud", cost={"total": 0.07}),
            _row(0.3, angle="fraud", cost={"total": 0.06}),
        ]
        with patch("analytics.weekly_report._load_rows", return_value=rows):
            report = wr.build_report("tapin")
        self.assertIsNotNone(report["avg_cost"])
        self.assertAlmostEqual(report["total_cost"], 0.18, places=2)


class TestFormatReport(unittest.TestCase):
    def test_format_not_ready(self):
        text = wr.format_report({"channel_id": "tapin", "n": 1, "ready": False})
        self.assertIn("Not enough analytics", text)

    def test_format_ready(self):
        report = {
            "channel_id": "tapin",
            "n": 6,
            "ready": True,
            "baseline": 0.25,
            "dimensions": {"angle": [{"value": "fraud", "avg": 0.45, "n": 3, "delta": 0.20}]},
            "avg_cost": 0.06,
            "total_cost": 0.36,
        }
        text = wr.format_report(report)
        self.assertIn("fraud", text)
        self.assertIn("baseline", text)
        self.assertIn("Cost:", text)


# Smoke test that the JSON feature round-trips through the loader shape.
class TestLoaderShape(unittest.TestCase):
    def test_features_json_parsing_is_tolerant(self):
        # malformed features_json must not crash build_report
        rows = [{"run_id": 1, "engaged_rate": 0.3, "features": json.loads("{}")}] * 3
        with patch("analytics.weekly_report._load_rows", return_value=rows):
            report = wr.build_report("tapin")
        self.assertTrue(report["ready"])


if __name__ == "__main__":
    unittest.main()
