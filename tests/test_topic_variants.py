"""Tests for topic variant post-processing (list-prefix stripping) + LLM fail-open."""

import unittest
from unittest import mock

from apis import topic_variants
from apis.topic_variants import _LIST_PREFIX_RE, _heuristic_angles


class TestHeuristicFallback(unittest.TestCase):
    def test_angles_when_llm_unavailable_do_not_crash(self):
        # A rate-limited / unavailable LLM must degrade to heuristic angles, not raise.
        with mock.patch.object(
            topic_variants, "complete", side_effect=RuntimeError("rate limited")
        ):
            angles = topic_variants.generate_ai_angles(
                "Conor McGregor UFC 329", ["a", "b", "c"], channel_id=None
            )
        self.assertTrue(angles)  # non-empty
        self.assertIn("Conor McGregor UFC 329", angles)  # seed leads

    def test_empty_llm_output_falls_back(self):
        with mock.patch.object(topic_variants, "complete", return_value="   "):
            angles = topic_variants.generate_ai_angles("Marvel Rivals S9", ["x"], channel_id=None)
        self.assertEqual(angles, _heuristic_angles("Marvel Rivals S9", ["x"]))


class TestVariantPrefixStripping(unittest.TestCase):
    def test_strips_numbered_and_bullet_prefixes(self):
        cases = {
            "1. Max vs Conor": "Max vs Conor",
            "2) Holloway next move": "Holloway next move",
            "10. Tenth item": "Tenth item",
            "- A dash variant": "A dash variant",
            "* star variant": "star variant",
            "• bullet variant": "bullet variant",
        }
        for raw, expected in cases.items():
            self.assertEqual(_LIST_PREFIX_RE.sub("", raw).strip(), expected, raw)

    def test_leaves_unprefixed_titles_untouched(self):
        title = "UFC's Summer Clash: What the Community Wants"
        self.assertEqual(_LIST_PREFIX_RE.sub("", title).strip(), title)

    def test_does_not_strip_mid_string_numbers(self):
        title = "Top 5 reasons Holloway wins"
        self.assertEqual(_LIST_PREFIX_RE.sub("", title).strip(), title)


if __name__ == "__main__":
    unittest.main()
