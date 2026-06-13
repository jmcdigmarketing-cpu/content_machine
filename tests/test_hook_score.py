"""Tests for hook scoring (Phase P)."""

import unittest

from core.hook_score import extract_hook, score_hook, score_script_hook


class TestExtractHook(unittest.TestCase):
    def test_first_sentence(self):
        self.assertEqual(
            extract_hook("Nobody saw this coming. Then it got worse."),
            "Nobody saw this coming.",
        )

    def test_first_line_wins(self):
        self.assertEqual(extract_hook("Big news today\nMore details follow."), "Big news today")

    def test_empty(self):
        self.assertEqual(extract_hook(""), "")


class TestScoreHook(unittest.TestCase):
    def test_strong_hook_scores_high(self):
        hs = score_hook("Nobody saw this $2 billion collapse coming.")
        self.assertGreaterEqual(hs.score, 70)
        self.assertEqual(hs.verdict, "strong")
        self.assertTrue(hs.passed)

    def test_weak_opener_scores_low(self):
        hs = score_hook(
            "Today we're going to talk about the Marvel Rivals progression system in detail."
        )
        self.assertLess(hs.score, 60)
        self.assertEqual(hs.verdict, "weak")
        self.assertFalse(hs.passed)
        # The weak opener penalty should be among the reasons.
        labels = [label for label, _ in hs.reasons]
        self.assertIn("weak opener", labels)

    def test_number_and_brevity_help(self):
        hs = score_hook("Holloway finished McGregor in 47 seconds.")
        self.assertGreaterEqual(hs.score, 70)

    def test_question_opener_penalised(self):
        with_q = score_hook("Is Marvel Rivals dying already?")
        self.assertTrue(any(label == "opens as a question" for label, _ in with_q.reasons))

    def test_empty_is_zero(self):
        self.assertEqual(score_hook("").score, 0)

    def test_score_clamped(self):
        hs = score_hook("Nobody saw this $2 billion record collapse coming.")
        self.assertLessEqual(hs.score, 100)
        self.assertGreaterEqual(hs.score, 0)

    def test_score_script_hook_uses_first_sentence(self):
        hs = score_script_hook(
            "Nobody saw this coming. A long boring second sentence follows here."
        )
        self.assertEqual(hs.hook, "Nobody saw this coming.")


if __name__ == "__main__":
    unittest.main()
