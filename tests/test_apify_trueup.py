"""Apify monthly true-up — synthetic fixture only, no network."""

from __future__ import annotations

import unittest
from pathlib import Path

from core.apify_trueup import DEFAULT_FIXTURE, parse_invoice, render, trueup


class TestApifyTrueup(unittest.TestCase):
    def test_fixture_parses(self):
        parsed = parse_invoice(DEFAULT_FIXTURE)
        self.assertEqual(parsed["runs"], 70)
        self.assertAlmostEqual(parsed["total_usd"], 1.40, places=2)
        self.assertEqual(len(parsed["items"]), 2)

    def test_under_count_vs_two_cent_model(self):
        report = trueup(parse_invoice(DEFAULT_FIXTURE))
        # 70 * $0.02 = $1.40 — fixture matches the model.
        self.assertAlmostEqual(report["modeled_usd"], 1.40, places=2)
        self.assertAlmostEqual(report["delta_usd"], 0.0, places=2)
        self.assertFalse(report["under_counted"])
        blob = render(report)
        self.assertIn("invoice", blob.lower())
        self.assertIn("1.40", blob)

    def test_under_count_flags_when_invoice_higher(self):
        parsed = {
            "period": "x",
            "total_usd": 5.0,
            "runs": 10,
            "items": [{"actor": "a", "runs": 10, "usd": 5.0}],
        }
        report = trueup(parsed)
        self.assertTrue(report["under_counted"])
        self.assertGreater(report["delta_usd"], 0)

    def test_fixture_lives_in_tests_not_secrets(self):
        self.assertTrue(Path(DEFAULT_FIXTURE).is_file())
        self.assertIn("tests", str(DEFAULT_FIXTURE).replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()
