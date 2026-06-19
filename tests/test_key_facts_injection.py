"""Unit tests for operator key-facts injection into LLM prompts."""

import unittest
from unittest.mock import MagicMock, patch


class TestKeyFactsInjection(unittest.TestCase):
    """_build_prompts injects OPERATOR KEY FACTS when key_facts is provided."""

    def _call_build_prompts(self, key_facts):
        from core.content_engine import _build_prompts

        return _build_prompts(
            topic="Test topic",
            signals={},
            min_words=60,
            max_words=90,
            today="2026-06-17",
            channel_id="tapin",
            script_brief="Be punchy.",
            seo_block="",
            signal_facts="No structured facts available.",
            signal_summary="",
            brief_block="",
            length_choice="1",
            key_facts=key_facts,
        )

    def test_key_facts_appear_in_user_prompt(self):
        _, user_prompt = self._call_build_prompts(
            ["Topuria is the featherweight champion", "He won by KO in round 2"]
        )
        self.assertIn("OPERATOR KEY FACTS", user_prompt)
        self.assertIn("Topuria is the featherweight champion", user_prompt)
        self.assertIn("He won by KO in round 2", user_prompt)

    def test_key_facts_appear_before_verified_facts(self):
        _, user_prompt = self._call_build_prompts(["Champion is Topuria"])
        op_pos = user_prompt.index("OPERATOR KEY FACTS")
        vf_pos = user_prompt.index("VERIFIED FACTS")
        self.assertLess(op_pos, vf_pos)

    def test_system_prompt_contains_key_facts_rule(self):
        system_prompt, _ = self._call_build_prompts(["some fact"])
        self.assertIn("OPERATOR KEY FACTS RULE", system_prompt)

    def test_empty_key_facts_produces_no_block(self):
        _, user_prompt = self._call_build_prompts([])
        self.assertNotIn("OPERATOR KEY FACTS", user_prompt)

    def test_none_key_facts_produces_no_block(self):
        _, user_prompt = self._call_build_prompts(None)
        self.assertNotIn("OPERATOR KEY FACTS", user_prompt)

    def test_whitespace_only_fact_is_skipped(self):
        _, user_prompt = self._call_build_prompts(["   ", "Real fact here"])
        # The block should still appear (one real fact)
        self.assertIn("Real fact here", user_prompt)
        # Blank-only fact should not produce a bare dash line
        lines = [ln.strip() for ln in user_prompt.splitlines()]
        self.assertNotIn("-", lines)

    def test_all_whitespace_facts_produces_no_block(self):
        _, user_prompt = self._call_build_prompts(["   ", "\t"])
        self.assertNotIn("OPERATOR KEY FACTS", user_prompt)


class TestKeyFactsThroughPipeline(unittest.TestCase):
    """key_facts flows through run_pipeline → generate_content_package."""

    @patch("core.pipeline.record_learning_outcome")
    @patch("core.pipeline.record_content_run", return_value=42)
    @patch("core.pipeline.build_research_brief", return_value=MagicMock(version="v1"))
    @patch("core.pipeline.generate_content_package")
    @patch("core.pipeline.run_discovery")
    def test_key_facts_passed_to_content_package(
        self, mock_discovery, mock_content, mock_brief, mock_record, mock_learn
    ):
        from core.pipeline import DiscoveryResult, run_pipeline

        discovery = DiscoveryResult(
            input_topic="UFC topic",
            base_signals={},
            evaluated=[("Topuria fight breakdown", 80.0, {})],
            channel_id="tapin",
        )
        mock_discovery.return_value = discovery
        mock_content.return_value = {
            "title": "T",
            "script": "S",
            "description": "D",
            "tags": [],
        }

        run_pipeline(
            "UFC topic",
            discovery=discovery,
            proceed_video=False,
            channel_id="tapin",
            key_facts=["Topuria is featherweight champion"],
        )

        call_kwargs = mock_content.call_args.kwargs
        self.assertIn("key_facts", call_kwargs)
        self.assertEqual(call_kwargs["key_facts"], ["Topuria is featherweight champion"])


if __name__ == "__main__":
    unittest.main()
