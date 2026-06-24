"""Tests for title-pattern features + the A/B attribution loop."""

import unittest
from unittest.mock import patch

from core import title_experiments as te
from core.title_features import feature_tags


class TestFeatureTags(unittest.TestCase):
    def test_detects_structural_patterns(self):
        tags = feature_tags("5 Reasons the Lakers Are Overrated: A Deep Dive")
        self.assertIn("number", tags)
        self.assertIn("listicle", tags)
        self.assertIn("colon", tags)
        self.assertIn("callout", tags)  # "overrated"

    def test_question_and_curiosity(self):
        tags = feature_tags("Why is nobody talking about this?")
        self.assertIn("question", tags)
        self.assertIn("curiosity", tags)

    def test_versus_and_short(self):
        tags = feature_tags("Kape vs Horiguchi")
        self.assertIn("versus", tags)
        self.assertIn("short", tags)

    def test_empty_title(self):
        self.assertEqual(feature_tags(""), [])


# colon titles average high, plain titles low.
_OUTCOMES = [
    ("Kape's Rise: The Untold Story", 0.30),
    ("Marvel Rivals Meta: What Changed", 0.26),
    ("UFC 300 Recap: Three Takeaways", 0.22),
    ("just a plain recap of the fights", 0.05),
    ("another flat title with no hook", 0.04),
]


class TestLeaderboard(unittest.TestCase):
    def setUp(self):
        te.reset_cache()

    def tearDown(self):
        te.reset_cache()

    def test_pattern_leaderboard_ranks_colon_high(self):
        with patch.object(te, "_titled_outcomes", return_value=_OUTCOMES):
            board = te.pattern_leaderboard("tapin", min_measured=3)
        tags = [tag for tag, _, _ in board]
        self.assertIn("colon", tags)
        # colon (avg .26) should rank above any tag from the flat titles.
        colon_avg = next(avg for tag, avg, _ in board if tag == "colon")
        self.assertGreater(colon_avg, 0.2)

    def test_winning_tags_beats_overall(self):
        with patch.object(te, "_titled_outcomes", return_value=_OUTCOMES):
            winners = te.winning_tags("tapin")
        # overall avg ≈ 0.17; colon (0.26) is a winner.
        self.assertIn("colon", winners)

    def test_empty_outcomes(self):
        with patch.object(te, "_titled_outcomes", return_value=[]):
            self.assertEqual(te.pattern_leaderboard("tapin"), [])
            self.assertEqual(te.winning_tags("tapin"), frozenset())

    def test_min_samples_filters(self):
        with patch.object(te, "_titled_outcomes", return_value=_OUTCOMES[:1]):
            # one title → no tag clears min_measured=3
            self.assertEqual(te.pattern_leaderboard("tapin", min_measured=3), [])


if __name__ == "__main__":
    unittest.main()
