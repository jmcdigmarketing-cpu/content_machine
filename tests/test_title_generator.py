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


if __name__ == "__main__":
    unittest.main()
