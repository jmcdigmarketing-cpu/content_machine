"""Tests for topic variant post-processing (list-prefix stripping)."""

import unittest

from apis.topic_variants import _LIST_PREFIX_RE


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
