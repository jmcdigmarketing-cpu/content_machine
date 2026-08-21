"""ops postmortem from in-memory traces — no data/traces writes."""

from __future__ import annotations

import unittest

from core.postmortem import assemble, render


class TestPostmortem(unittest.TestCase):
    def test_slowest_failed_ungrounded_and_hint(self):
        data = assemble(
            run_id=9,
            trace={
                "status": "drafted",
                "selected_topic": "UFC 317",
                "timings": {
                    "signals_and_variants": 40.0,
                    "variant_scoring": 2.0,
                    "research_brief": 3.0,
                    "content_package": 5.0,
                },
                "signals": {"tiktok_trends": {"status": "quota_exceeded"}},
                "llm_cost_usd": 0.01,
            },
            quality={"ungrounded_count": 2},
            cost={"total": 0.31, "tts": 0.25},
        )
        self.assertEqual(data["slowest"]["phase"], "signals_and_variants")
        self.assertIn("tiktok_trends:quota_exceeded", data["failed_signals"])
        self.assertEqual(data["ungrounded_count"], 2)
        self.assertIn("grounding", data["next_fix"])
        blob = render(data)
        self.assertIn("#9", blob)
        self.assertIn("UFC 317", blob)

    def test_quota_hint_when_no_ungrounded(self):
        data = assemble(
            run_id=1,
            trace={"signals": {"youtube": {"status": "auth_error"}}, "timings": {}},
            quality={"ungrounded_count": 0},
            cost={"total": 0.1, "tts": 0.1},
        )
        self.assertIn("quota/auth", data["next_fix"])


if __name__ == "__main__":
    unittest.main()
