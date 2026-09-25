"""Tests for parsing pasted video ideas (option 5)."""

import unittest

from core.idea_intake import parse_pasted_idea

# The exact shape an idea generator pastes (matches the user's example).
RICH_IDEA = """Idea illustration
Marvel Rivals Rank Analysis: Why The Competitive Grind Is Saving Modern Gaming Philosophy
We bypass the hollow dopamine loops of modern shooters to dissect how Marvel Rivals restores the punishing, high-stakes meritocracy of legacy competition. By mapping Payton Talbott's relentless forward pressure onto hero-based mechanics, we prove that tactical friction and steep skill ceilings provide the only authentic antidote to the industry's current stagnation.

Develop idea
Save idea
Why this could fit your channel
1
Interdisciplinary Tactical Synthesis
This idea bridges your deep understanding of MMA mentalities with gaming mechanics.
2
Antidote to Stagnation Philosophy
It aligns with your channel's focus on resisting defeatist mindsets.
3
Strategic Genre Evolution
By analyzing Marvel Rivals through a sports-centric lens, you provide a fresh critique."""


class TestParsePastedIdea(unittest.TestCase):
    def test_rich_idea_extracts_title(self):
        p = parse_pasted_idea(RICH_IDEA)
        self.assertTrue(p.title.startswith("Marvel Rivals Rank Analysis"))

    def test_rich_idea_drops_scaffolding(self):
        p = parse_pasted_idea(RICH_IDEA)
        # No UI labels or rationale should leak into title/thesis/angle.
        for junk in ("idea illustration", "develop idea", "save idea", "why this"):
            self.assertNotIn(junk, p.angle.lower())
        self.assertNotIn("interdisciplinary", p.angle.lower())  # rationale dropped

    def test_thesis_captured_as_angle(self):
        p = parse_pasted_idea(RICH_IDEA)
        self.assertIn("dopamine loops", p.thesis)
        self.assertIn("Payton Talbott", p.angle)
        self.assertTrue(p.is_rich)

    def test_seed_is_concise(self):
        # Colon clause is dropped for a searchable seed.
        p = parse_pasted_idea(RICH_IDEA)
        self.assertEqual(p.seed_topic, "Marvel Rivals Rank Analysis")
        self.assertNotIn(":", p.seed_topic)

    def test_plain_single_line_passthrough(self):
        p = parse_pasted_idea("Marvel Rivals season 3 tier list")
        self.assertEqual(p.title, "Marvel Rivals season 3 tier list")
        self.assertEqual(p.seed_topic, "Marvel Rivals season 3 tier list")
        self.assertEqual(p.thesis, "")
        self.assertFalse(p.is_rich)

    def test_title_thesis_two_lines(self):
        p = parse_pasted_idea("Best UFC knockouts\nA breakdown of why they land.")
        self.assertEqual(p.title, "Best UFC knockouts")
        self.assertEqual(p.thesis, "A breakdown of why they land.")
        self.assertTrue(p.is_rich)

    def test_empty(self):
        p = parse_pasted_idea("")
        self.assertEqual(p.title, "")
        self.assertFalse(p.is_rich)

    def test_short_title_keeps_full_when_head_too_short(self):
        # "X: rest" where head is < 3 words keeps the whole title as the seed.
        p = parse_pasted_idea("GTA 6: the everything we know breakdown")
        self.assertEqual(p.seed_topic, "GTA 6: the everything we know breakdown")

    def test_one_line_idea_still_has_a_brief(self):
        """#664. is_rich was False so the writer never saw the typed idea."""
        from core.idea_intake import creative_brief_for_run

        p = parse_pasted_idea("how does the offside rule actually work")
        self.assertFalse(p.is_rich)
        self.assertEqual(
            creative_brief_for_run(p),
            "how does the offside rule actually work",
        )

    def test_youtube_angle_is_the_brief_not_the_search_string(self):
        from core.idea_intake import seed_and_brief_from_youtube

        seed, brief = seed_and_brief_from_youtube(
            "GTA 6 Official Trailer 2",
            "first impressions, looks great",
        )
        self.assertEqual(seed, "GTA 6 Official Trailer 2")
        self.assertEqual(brief, "first impressions, looks great")
        self.assertNotIn("—", seed)


if __name__ == "__main__":
    unittest.main()
