"""Tests for the shared recommender engagement helpers."""

import unittest
from unittest.mock import patch

from core.engagement import engaged_rate, safe_infer_domain


class TestEngagedRate(unittest.TestCase):
    def test_explicit_engaged_rate_preferred(self):
        self.assertEqual(engaged_rate('{"engaged_rate": 0.42, "views": 100}'), 0.42)

    def test_derived_from_likes_over_views(self):
        self.assertAlmostEqual(engaged_rate('{"views": 200, "likes": 50}'), 0.25)

    def test_zero_views_returns_none(self):
        self.assertIsNone(engaged_rate('{"views": 0, "likes": 5}'))

    def test_malformed_and_empty_return_none(self):
        self.assertIsNone(engaged_rate(""))
        self.assertIsNone(engaged_rate("not json"))
        self.assertIsNone(engaged_rate(None))


class TestSafeInferDomain(unittest.TestCase):
    def test_delegates_to_topic_scorer(self):
        self.assertEqual(safe_infer_domain("Marvel Rivals new season", "tapin"), "gaming")

    def test_falls_back_to_neutral_on_error(self):
        with patch("apis.topic_scorer.infer_domain", side_effect=RuntimeError("boom")):
            self.assertEqual(safe_infer_domain("anything", "tapin"), "neutral")


if __name__ == "__main__":
    unittest.main()
