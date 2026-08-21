"""Tests for the pre-upload authenticity self-check (Phase O)."""

import os
import unittest
from difflib import SequenceMatcher
from unittest.mock import patch

from core.authenticity import (
    _content_cosine,
    _insight_check,
    _substance_check,
    _variation_check,
    evaluate_authenticity,
)

# A script that is distinct, opinionated, and substantial (>55 spoken words).
GOOD_SCRIPT = (
    "Nobody saw this roster move coming. Here's why it changes the entire "
    "division: the matchup data says the champion has never beaten a southpaw "
    "with this kind of reach advantage, and my prediction is a first-round "
    "upset that nobody on the panel is willing to call. The numbers back it "
    "up, the styles are a nightmare, and most fans are sleeping on it "
    "completely. Mark my words, this one ends early and it ends badly for the "
    "favourite when the cage door finally closes this weekend."
)

# A neutral recap — substantial but no authorial take (>55 spoken words).
RECAP_SCRIPT = (
    "The event takes place this weekend at a sold-out arena downtown. There "
    "are five fights on the main card and several more on the prelims. The "
    "main event features two ranked contenders who have both won their last "
    "three bouts. Tickets went on sale last week and the venue holds roughly "
    "twenty thousand people. The broadcast starts in the early evening and the "
    "main card follows a couple of hours after the preliminary fights begin."
)


class TestVariationCheck(unittest.TestCase):
    def test_no_recent_passes(self):
        c = _variation_check(GOOD_SCRIPT, [])
        self.assertTrue(c.passed)

    def test_near_identical_fails(self):
        c = _variation_check(GOOD_SCRIPT, [GOOD_SCRIPT])
        self.assertFalse(c.passed)

    def test_same_opening_fails(self):
        # Near-identical opening (the template tell), then diverges.
        twin = (
            "Nobody saw this roster move coming. Here's why it barely matters "
            "at all, and why the whole storyline is honestly a bit overblown "
            "if you actually look at the tape from a neutral point of view."
        )
        c = _variation_check(GOOD_SCRIPT, [twin])
        self.assertFalse(c.passed)

    def test_distinct_passes(self):
        other = (
            "Completely different topic about a video game patch and balance "
            "changes that nobody expected to drop this early in the season."
        )
        c = _variation_check(GOOD_SCRIPT, [other])
        self.assertTrue(c.passed)

    def test_paraphrase_of_same_facts_fails(self):
        # Same claims, different wording — SequenceMatcher is low; content overlap is not.
        paraphrase = (
            "The roster move shocked everyone. I think it reshapes the whole "
            "division because matchup data shows the champion never beat a "
            "southpaw with that reach advantage. Calling it now: a first-round "
            "upset the panel will not name. Numbers back the styles nightmare, "
            "fans are sleeping, and the favourite ends badly once the cage door "
            "closes this weekend."
        )
        self.assertLess(
            SequenceMatcher(None, GOOD_SCRIPT.lower(), paraphrase.lower()).ratio(),
            0.60,
            "fixture must be a paraphrase, not a near-copy",
        )
        self.assertGreaterEqual(_content_cosine(GOOD_SCRIPT, paraphrase), 0.45)
        with patch.dict("os.environ", {"AUTHENTICITY_SEMANTIC": "true"}, clear=False):
            c = _variation_check(GOOD_SCRIPT, [paraphrase])
        self.assertFalse(c.passed)
        self.assertIn("rehash", c.detail)

    def test_exact_duplicate_fails_lexical_first(self):
        c = _variation_check(GOOD_SCRIPT, [GOOD_SCRIPT])
        self.assertFalse(c.passed)
        self.assertIn("template-stamped", c.detail)

    def test_semantic_can_be_disabled(self):
        paraphrase = (
            "The roster move shocked everyone. I think it reshapes the whole "
            "division because matchup data shows the champion never beat a "
            "southpaw with that reach advantage. Calling it now: a first-round "
            "upset the panel will not name. Numbers back the styles nightmare, "
            "fans are sleeping, and the favourite ends badly once the cage door "
            "closes this weekend."
        )
        with patch.dict("os.environ", {"AUTHENTICITY_SEMANTIC": "false"}, clear=False):
            c = _variation_check(GOOD_SCRIPT, [paraphrase])
        self.assertTrue(c.passed)


class TestInsightCheck(unittest.TestCase):
    def test_opinion_passes(self):
        self.assertTrue(_insight_check(GOOD_SCRIPT).passed)

    def test_neutral_recap_fails(self):
        self.assertFalse(_insight_check(RECAP_SCRIPT).passed)


class TestSubstanceCheck(unittest.TestCase):
    def test_thin_fails(self):
        self.assertFalse(_substance_check("Too short.", fact_count=5).passed)

    def test_no_facts_fails(self):
        self.assertFalse(_substance_check(GOOD_SCRIPT, fact_count=0).passed)

    def test_substantial_passes(self):
        self.assertTrue(_substance_check(GOOD_SCRIPT, fact_count=2).passed)


class TestEvaluate(unittest.TestCase):
    def test_good_script_ok(self):
        with patch("core.authenticity._recent_scripts", return_value=[]):
            report = evaluate_authenticity(GOOD_SCRIPT, "tapin", fact_count=3)
        self.assertEqual(report.verdict, "ok")
        self.assertEqual(report.score, 100)
        self.assertTrue(report.passed)

    def test_recap_is_review(self):
        # Distinct + substantial but no insight -> 40 + 25 = 65 -> review
        with patch("core.authenticity._recent_scripts", return_value=[]):
            report = evaluate_authenticity(RECAP_SCRIPT, "tapin", fact_count=2)
        self.assertEqual(report.verdict, "review")
        self.assertFalse(report.passed)

    def test_templated_thin_blocks(self):
        # Identical to a recent upload, no insight, no facts -> block
        with patch("core.authenticity._recent_scripts", return_value=[RECAP_SCRIPT]):
            report = evaluate_authenticity(RECAP_SCRIPT, "tapin", fact_count=0)
        self.assertEqual(report.verdict, "block")


if __name__ == "__main__":
    unittest.main()
