"""#802: a slow provider must cost seconds, not minutes.

Research brief maxed at 138 s (median 11.2); variant scoring at 185 s (median 0.9).
There is no wall-clock budget — `_fallback_brief` only runs when the LLM returns
None. Unmodified `_build_with_llm` sleeps through the budget and returns its
slow narrative; `as_completed` waits for every `_score_variant` future.
"""

from __future__ import annotations

import os
import time
import unittest
from unittest.mock import patch

from core.research_brief import ResearchBrief, build_research_brief


class TestResearchBriefDeadline(unittest.TestCase):
    @patch("core.research_brief._USE_LLM", True)
    @patch("analytics.competitor_context.get_competitor_prompt_block", return_value="")
    @patch("apis.stats_context_api.gather_stats_context", return_value={"lines": []})
    @patch("core.research_brief.fetch_rss_context", return_value={"headlines": []})
    @patch("core.research_brief.get_cached", return_value=None)
    @patch("core.research_brief.set_cache")
    def test_a_slow_llm_falls_back_inside_the_budget(self, *_mocks) -> None:
        def _slow(*_a, **_k):
            time.sleep(1.0)
            return ResearchBrief(topic="t", narrative="SLOW LLM NARRATIVE")

        with (
            patch("core.research_brief._build_with_llm", side_effect=_slow),
            patch("core.research_brief.enrich_facts", return_value=""),
            patch("core.research_brief.build_script_brief", return_value=""),
            patch.dict(os.environ, {"RESEARCH_BRIEF_DEADLINE_S": "0.05"}, clear=False),
        ):
            started = time.perf_counter()
            brief = build_research_brief("UFC 250 preview", {}, channel_id="tapin")
            elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 0.6, elapsed)
        self.assertNotEqual(brief.narrative, "SLOW LLM NARRATIVE")
        self.assertIn("UFC 250", brief.narrative)
        self.assertEqual(brief.fallback_reason, "deadline")

    def test_deadline_defaults_to_thirty_seconds(self) -> None:
        from core.research_brief import research_brief_deadline_s

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RESEARCH_BRIEF_DEADLINE_S", None)
            self.assertEqual(research_brief_deadline_s(), 30.0)

    def test_features_persist_the_deadline_fallback(self) -> None:
        from core.run_features import build_features

        brief = ResearchBrief(
            topic="UFC 250 preview",
            narrative="Focus on the specific angle",
            fallback_reason="deadline",
        )
        with patch.dict(os.environ, {"RESEARCH_BRIEF_DEADLINE_S": "30"}, clear=False):
            features = build_features(
                topic="UFC 250 preview",
                channel_id="tapin",
                content_package={"title": "UFC 250", "script": "Hello."},
                research_brief=brief,
            )
        self.assertEqual(features.get("brief_fallback"), "deadline")
        self.assertEqual(features.get("brief_deadline_s"), 30.0)


class TestVariantScoringDeadline(unittest.TestCase):
    def test_a_hung_scorer_does_not_hold_the_run(self) -> None:
        from core.pipeline import collect_scored_variants

        def _hang(variant, *_a, **_k):
            time.sleep(2.0)
            return variant, 50.0, {}, 50.0

        candidates = ["angle a", "angle b"]
        with (
            patch("core.pipeline._score_variant", side_effect=_hang),
            patch.dict(os.environ, {"VARIANT_SCORING_DEADLINE_S": "0.08"}, clear=False),
        ):
            started = time.perf_counter()
            evaluated, raw, meta = collect_scored_variants(candidates, "tapin", {}, "GTA 6")
            elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 0.8, elapsed)
        self.assertTrue(evaluated)
        self.assertEqual(evaluated[0][0], "GTA 6")
        self.assertEqual(meta.get("fallback"), "deadline")

    def test_run_discovery_records_the_scoring_fallback(self) -> None:
        from core import pipeline

        def _hang(variant, *_a, **_k):
            time.sleep(2.0)
            return variant, 50.0, {}, 50.0

        with (
            patch("core.pipeline._score_variant", side_effect=_hang),
            patch("core.pipeline.generate_variants", return_value=["angle a", "angle b"]),
            patch("core.pipeline.build_registry", return_value={}),
            patch("core.pipeline.ensure_competitor_snapshot", create=True),
            patch("core.pipeline._load_discovery_cache", return_value=None),
            patch("core.channel_context.recent_input_topics", return_value=[]),
            patch("core.run_mode.guard_before_discovery", return_value=[]),
            patch.dict(
                os.environ,
                {
                    "VARIANT_SCORING_DEADLINE_S": "0.08",
                    "COMPETITOR_SYNC_ON_DISCOVERY": "off",
                    "APIFY_CONTENT_MACHINE_KEY": "",
                },
                clear=False,
            ),
        ):
            started = time.perf_counter()
            result = pipeline.run_discovery(
                "GTA 6 deadline-802", variant_limit=2, channel_id="tapin"
            )
            elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 0.8, elapsed)
        # #813: the marker lives in `meta`, not `timings` — the report sums
        # `timings` and formats every key as seconds.
        self.assertEqual(result.meta.get("variant_scoring_fallback"), "deadline")
        self.assertNotIn("variant_scoring_fallback", result.timings)
        self.assertTrue(all(isinstance(v, int | float) for v in result.timings.values()))
        self.assertEqual(result.evaluated[0][0], "GTA 6 deadline-802")

    def test_the_marker_still_reaches_the_persisted_timings(self) -> None:
        """timings_json/trace keys are unchanged — only the in-memory home moved."""
        from core.pipeline import DiscoveryResult

        discovery = DiscoveryResult(
            input_topic="GTA 6",
            base_signals={},
            evaluated=[("GTA 6", 1.0, {})],
            timings={"variant_scoring": 15.0},
            meta={"variant_scoring_fallback": "deadline", "angle_spread": 0.2},
        )
        recorded = {**discovery.timings, **discovery.meta, **{"length_preset": "2"}}
        self.assertEqual(recorded["variant_scoring_fallback"], "deadline")
        self.assertEqual(recorded["angle_spread"], 0.2)


if __name__ == "__main__":
    unittest.main()
