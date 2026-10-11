"""#380: Apify cost per usable fact.

A billed actor that returns a line the script never uses costs the same as one
that grounds it. The yield names the dollars per fact the script actually used,
and a miss is "no usable fact" rather than a division by zero.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch


def _reddit(title: str, *, backend: str = "apify") -> dict:
    return {
        "reddit": {
            "active": True,
            "connected": True,
            "data": {
                "backend": backend,
                "posts": [
                    {"title": title, "subreddit": "ufc", "ups": 12, "comments": 3},
                ],
            },
        }
    }


class ApifyYieldTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"COST_APIFY_PER_RUN": "0.02"})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_a_fact_the_script_uses_costs_two_cents(self):
        from core.reliability import apify_fact_yield

        rows = apify_fact_yield(_reddit("Jon Jones 19-0"), "Jon Jones is 19-0 and still champion.")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["signal"], "reddit")
        self.assertAlmostEqual(rows[0]["cost"], 0.02)
        self.assertEqual(rows[0]["usable"], 1)
        self.assertAlmostEqual(rows[0]["per_fact"], 0.02)
        self.assertIn("per usable fact", rows[0]["line"])

    def test_a_miss_is_named_not_divided(self):
        from core.reliability import apify_fact_yield

        rows = apify_fact_yield(
            _reddit("Jon Jones 19-0"), "The welterweight belt is the only prize."
        )
        self.assertAlmostEqual(rows[0]["cost"], 0.02)
        self.assertEqual(rows[0]["usable"], 0)
        self.assertIsNone(rows[0]["per_fact"])
        self.assertIn("no usable fact", rows[0]["line"])
        self.assertIn("$0.02", rows[0]["line"])

    def test_a_free_backend_costs_nothing(self):
        from core.reliability import apify_fact_yield

        rows = apify_fact_yield(
            _reddit("Jon Jones 19-0", backend="free"),
            "Jon Jones is 19-0 and still champion.",
        )
        self.assertEqual(rows[0]["cost"], 0.0)
        self.assertIn("$0.00", rows[0]["line"])

    def test_a_competitor_title_is_not_a_usable_fact(self):
        from core.reliability import apify_fact_yield

        signals = {
            "youtube_competitors": {
                "active": True,
                "connected": True,
                "data": {
                    "backend": "apify",
                    "videos": [{"title": "Jon Jones 19-0", "velocity": 10, "channel": "mma"}],
                },
            }
        }
        rows = apify_fact_yield(signals, "Jon Jones is 19-0 and still champion.")
        self.assertEqual(rows[0]["usable"], 0)
        self.assertIn("no usable fact", rows[0]["line"])

    def test_reliability_prints_the_stored_rows(self):
        from core.reliability import apify_fact_yield, render

        rows = apify_fact_yield(_reddit("Jon Jones 19-0"), "Jon Jones is 19-0 and still champion.")
        text = render({"apify": {}, "apify_yield": rows})
        self.assertIn("per usable fact", text)
        self.assertIn("reddit", text)

    def test_a_stored_run_is_what_gets_printed(self):
        import json
        from types import SimpleNamespace

        from core.reliability import render, stored_apify_yield

        run = SimpleNamespace(
            id=9,
            features_json=json.dumps(
                {"apify_yield": [{"signal": "reddit", "line": "reddit: $0.02 per usable fact (1)"}]}
            ),
        )
        with patch("storage.repositories.content_runs.get_content_run_repository") as repo:
            repo.return_value.list_for_channel.return_value = [run]
            rows = stored_apify_yield("tapin")
        text = render({"apify": {}, "apify_yield": rows})
        self.assertIn("per usable fact", text)


if __name__ == "__main__":
    unittest.main()
