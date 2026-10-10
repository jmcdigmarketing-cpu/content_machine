"""#1085: angle 1 adds nothing the idea did not have.

Run 125 (2026-10-10): the operator typed "Chargers Hopeium going into week 5" and angle 1 -
"your idea, worded for search" - came back "Los Angeles Chargers Hopeium Into Week 5 2023:
What's The Question?". Measured cause: wave 66's `idea_angle` prompt asked for "the year if it
is implied" without saying what today is, so the model added its own year, and told it to
"keep its question" on an idea with none, so it appended one. The validator counted kept words
and take markers only, and the #1008 date check never ran on angle 1.
"""

from __future__ import annotations

import datetime
import unittest
from unittest.mock import patch

IDEA = "Chargers Hopeium going into week 5"
RUN_125 = "Los Angeles Chargers Hopeium Into Week 5 2023: What's The Question?"


class RewordingProblemTests(unittest.TestCase):
    def test_run_125_rewording_is_refused(self):
        from apis.topic_variants import idea_rewording_problem

        self.assertTrue(idea_rewording_problem(IDEA, RUN_125))

    def test_an_added_year_number_or_question(self):
        from apis.topic_variants import idea_rewording_problem

        self.assertIn("2026", idea_rewording_problem(IDEA, "Chargers Hopeium Week 5 2026"))
        self.assertIn("3", idea_rewording_problem(IDEA, "3 Reasons For Chargers Hopeium Week 5"))
        self.assertIn("question", idea_rewording_problem(IDEA, "Chargers Hopeium Into Week 5?"))

    def test_a_clean_rewording_passes(self):
        from apis.topic_variants import idea_rewording_problem

        self.assertEqual(
            idea_rewording_problem(IDEA, "Los Angeles Chargers Hopeium Going Into Week 5"), ""
        )
        own_q = "How can the Chargers turn it around?"
        self.assertEqual(
            idea_rewording_problem(own_q, "How Can The Los Angeles Chargers Turn It Around?"), ""
        )

    def test_a_rewording_that_knocks_the_hope_is_refused(self):
        """#1084: angle 1 keeps the idea's stance as well as its words."""
        from apis.topic_variants import idea_rewording_problem

        self.assertIn(
            "knocks", idea_rewording_problem(IDEA, "Chargers Hopeium Masks Flaws Into Week 5")
        )

    def test_the_old_rules_still_hold(self):
        from apis.topic_variants import idea_rewording_problem

        self.assertTrue(idea_rewording_problem(IDEA, "Chargers Hopeium Is Dead Into Week 5"))
        self.assertTrue(idea_rewording_problem(IDEA, "NFL Week 5 Preview"))


class IdeaAngleTests(unittest.TestCase):
    def _angle(self, reply):
        from apis import topic_variants

        prompts: list[str] = []

        def fake(prompt, **_kw):
            prompts.append(prompt)
            return reply

        with (
            patch("core.llm_router.complete", side_effect=fake),
            patch("core.facts.event_dates._today", return_value=datetime.date(2026, 10, 10)),
        ):
            out = topic_variants.idea_angle(IDEA, "tapin")
        return out, prompts[0]

    def test_run_125_reply_keeps_the_idea_as_typed(self):
        out, prompt = self._angle(RUN_125)
        self.assertEqual(out, IDEA)
        self.assertIn("2026-10-10", prompt)
        self.assertNotIn("the year if it is implied", prompt)
        self.assertNotIn("Keep its question", prompt)

    def test_a_clean_reply_is_used(self):
        out, _prompt = self._angle("Los Angeles Chargers Hopeium Going Into Week 5")
        self.assertEqual(out, "Los Angeles Chargers Hopeium Going Into Week 5")


if __name__ == "__main__":
    unittest.main()
