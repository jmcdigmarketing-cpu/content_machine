"""#850: the research brief never saw the operator's key facts.

`core/pipeline.run_pipeline` had `key_facts` in scope and passed them to the script
writer, but called `build_research_brief(content_topic, best_signals, ...)` without
them. The brief is the "primary context" block of the script prompt, so it could
frame a story against facts the operator had just pasted. Its 3h cache key also
ignored facts, so a regenerate with new facts got the old brief back.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

FACTS = ["City were found guilty of 114 of 115 charges on 2026-09-25."]

_QUIET = (
    patch("analytics.competitor_context.get_competitor_prompt_block", return_value=""),
    patch("apis.stats_context_api.gather_stats_context", return_value={"lines": []}),
    patch("core.research_brief.fetch_rss_context", return_value={"headlines": []}),
    # #921: the fallback brief enriches thin facts from live RSS and an LLM.
    patch("core.research_brief.enrich_facts", return_value=""),
    patch("core.research_brief.get_cached", return_value=None),
)


def _quiet(fn):
    for p in reversed(_QUIET):
        fn = p(fn)
    return fn


class TestTheBriefSeesTheFacts(unittest.TestCase):
    @_quiet
    def test_the_prompt_carries_the_operator_facts(self, *_mocks) -> None:
        from core import research_brief

        seen: dict = {}

        def fake_json(prompt, **kwargs):
            seen["prompt"] = prompt
            return None

        with (
            patch.object(research_brief, "_USE_LLM", True),
            patch.object(research_brief, "complete_json", side_effect=fake_json),
            patch.object(research_brief, "set_cache"),
        ):
            research_brief.build_research_brief(
                "Man City guilty", {}, channel_id="tapin", key_facts=FACTS
            )
        self.assertIn("OPERATOR KEY FACTS", seen.get("prompt", ""))
        self.assertIn("114 of 115 charges", seen["prompt"])

    @_quiet
    def test_the_fallback_uses_them_as_evidence(self, *_mocks) -> None:
        from core import research_brief

        with (
            patch.object(research_brief, "_USE_LLM", False),
            patch.object(research_brief, "set_cache"),
        ):
            brief = research_brief.build_research_brief(
                "Man City guilty", {}, channel_id="tapin", key_facts=FACTS
            )
        self.assertIn(FACTS[0], brief.supporting_evidence)

    @_quiet
    def test_the_cache_key_changes_with_the_facts(self, *_mocks) -> None:
        from core import research_brief

        with (
            patch.object(research_brief, "_USE_LLM", False),
            patch.object(research_brief, "set_cache") as mock_set,
        ):
            research_brief.build_research_brief("Man City guilty", {}, channel_id="tapin")
            research_brief.build_research_brief(
                "Man City guilty", {}, channel_id="tapin", key_facts=FACTS
            )
        keys = [c.args[0] for c in mock_set.call_args_list]
        self.assertEqual(len(keys), 2)
        self.assertNotEqual(keys[0], keys[1])


class TestThePipelinePassesThem(unittest.TestCase):
    @patch("core.pipeline.write_run_trace")
    @patch("core.pipeline.persist_quality")
    @patch("core.pipeline.build_quality", return_value={})
    @patch("core.pipeline.record_learning_outcome")
    @patch("core.pipeline.record_content_run", return_value=42)
    @patch("core.pipeline.build_research_brief", return_value=MagicMock(version="v1"))
    @patch("core.pipeline.generate_content_package")
    @patch("core.pipeline.run_discovery")
    def test_run_pipeline_hands_key_facts_to_the_brief(
        self, mock_discovery, mock_content, mock_brief, *_rest
    ) -> None:
        from core.pipeline import DiscoveryResult, run_pipeline

        mock_discovery.return_value = DiscoveryResult(
            input_topic="Man City guilty",
            base_signals={},
            evaluated=[("Man City guilty: what now", 80.0, {})],
            channel_id="tapin",
        )
        mock_content.return_value = {"title": "T", "script": "S", "description": "D", "tags": []}
        with patch.dict("os.environ", {"AUTO_RESEARCH_ENABLED": "false"}, clear=False):
            run_pipeline(
                "Man City guilty",
                discovery=mock_discovery.return_value,
                proceed_video=False,
                channel_id="tapin",
                key_facts=FACTS,
            )
        self.assertEqual(mock_brief.call_args.kwargs.get("key_facts"), FACTS)


if __name__ == "__main__":
    unittest.main()
