"""Tests for post-script fact-grounded title generation."""

import unittest
from unittest.mock import patch

from core.title_generator import _clean_title, _hook_line, generate_title


class TestTitleHelpers(unittest.TestCase):
    def test_hook_line_first_sentence(self):
        self.assertEqual(
            _hook_line("Giannis is a Heat player. More here."), "Giannis is a Heat player."
        )

    def test_clean_rejects_slop(self):
        bad = "Free Agency Day 1 Just Broke the League"
        good = "Giannis to Miami: What the Heat Gave Up"
        self.assertEqual(_clean_title(bad, fallback=good), good)


class TestGenerateTitle(unittest.TestCase):
    @patch(
        "core.title_generator.complete", return_value="Giannis to Miami Heat — Full Trade Breakdown"
    )
    def test_uses_facts_and_script(self, mock_complete):
        title = generate_title(
            script="Giannis Antetokounmpo is officially a Miami Heat player.",
            topic="Giannis trade fallout angle",
            seed_topic="NBA Free Agency",
            key_facts=["Giannis traded to Miami Heat June 2026"],
            channel_id="tapin",
        )
        self.assertIn("Giannis", title)
        mock_complete.assert_called()
        prompt = mock_complete.call_args[0][0]
        self.assertIn("Giannis traded to Miami", prompt)


class TestGenerateTitleFailOpen(unittest.TestCase):
    """The title runs AFTER the script + grounding + claim verifier have succeeded, so an
    LLM outage here must degrade to the script hook — never throw that work away.

    Regression: a retired OpenRouter `:free` slug raised 404 out of `complete()` and
    killed a fully-generated run.
    """

    def _generate(self):
        return generate_title(
            script="Valve engineers warn the memory crisis is still getting worse.",
            topic="Steam Machine memory crisis angle",
            seed_topic="Steam Machine",
            key_facts=["Valve engineers say memory prices keep climbing"],
            channel_id="tapin",
        )

    @patch("core.title_generator.complete", side_effect=RuntimeError("boom"))
    def test_llm_failure_falls_back_to_hook(self, _mock):
        title = self._generate()
        self.assertTrue(title)
        self.assertIn("Valve engineers", title)  # the script hook

    def test_llm_unavailable_does_not_raise(self):
        from core.llm_router import LLMUnavailableError

        with patch(
            "core.title_generator.complete",
            side_effect=LLMUnavailableError("all providers failed"),
        ):
            self.assertTrue(self._generate())

    @patch("core.title_generator.complete", return_value="")
    def test_empty_response_falls_back(self, _mock):
        self.assertTrue(self._generate())

    def test_retry_failure_keeps_first_pass_fallback(self):
        # First call returns slop (rejected -> fallback), retry then fails: still no raise.
        seq = ["You Won't Believe This Changes Everything", RuntimeError("boom")]

        def fake(*_a, **_k):
            item = seq.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        with patch("core.title_generator.complete", side_effect=fake):
            self.assertTrue(self._generate())


if __name__ == "__main__":
    unittest.main()
