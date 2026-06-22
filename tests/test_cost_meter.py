"""Tests for per-run cost estimation (v0)."""

import unittest
from unittest.mock import patch

from core.cost_meter import estimate_run_cost, format_cost_line


class TestCostMeter(unittest.TestCase):
    def test_breakdown_keys_and_total(self):
        cost = estimate_run_cost(script="word " * 150, signals={}, rendered=False)
        for key in ("llm", "tts", "apify", "web_search", "render", "total"):
            self.assertIn(key, cost)
        self.assertAlmostEqual(
            cost["total"],
            cost["llm"] + cost["tts"] + cost["apify"] + cost["web_search"] + cost["render"],
            places=3,
        )

    def test_tts_only_when_rendered(self):
        script = "word " * 200
        unrendered = estimate_run_cost(script=script, rendered=False)
        rendered = estimate_run_cost(script=script, rendered=True)
        self.assertEqual(unrendered["tts"], 0.0)
        self.assertGreater(rendered["tts"], 0.0)

    def test_apify_and_web_search_counted(self):
        signals = {
            "reddit": {"active": True},
            "twitter": {"active": True},
            "tiktok_trends": {"active": False},
            "web_search": {"active": True},
        }
        cost = estimate_run_cost(script="hi", signals=signals)
        self.assertGreater(cost["apify"], 0.0)
        self.assertGreater(cost["web_search"], 0.0)

    def test_rates_overridable_via_env(self):
        with patch.dict("os.environ", {"COST_LLM_PER_1K_TOKENS": "1.0"}, clear=False):
            cost = estimate_run_cost(script="word " * 1000)
        self.assertGreater(cost["llm"], 5.0)


class TestFormatCostLine(unittest.TestCase):
    def test_empty_when_no_cost(self):
        self.assertEqual(format_cost_line(None), "")
        self.assertEqual(format_cost_line({}), "")

    def test_total_and_nonzero_breakdown(self):
        line = format_cost_line(
            {
                "llm": 0.04,
                "tts": 0.02,
                "apify": 0.0,
                "web_search": 0.01,
                "render": 0.0,
                "total": 0.07,
            }
        )
        self.assertIn("Est. run cost: $0.0700", line)
        self.assertIn("llm $0.0400", line)
        self.assertIn("tts $0.0200", line)
        self.assertIn("web $0.0100", line)
        # Zero components are omitted from the breakdown.
        self.assertNotIn("apify", line)
        self.assertNotIn("render", line)

    def test_total_only_when_no_components(self):
        line = format_cost_line({"total": 0.0})
        self.assertEqual(line, "Est. run cost: $0.0000")


if __name__ == "__main__":
    unittest.main()
