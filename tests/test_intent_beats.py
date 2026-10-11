"""#1031: each calm intent gets its own shape.

Measured in the prompt: hope, plan, take and the operator's own idea each had a shape. A list,
a tutorial, a comparison, a retrospective and a reaction all shared the explainer's - "hook ->
how it works -> the detail people get wrong -> payoff" - so a ranking was asked to explain a
mechanism and a how-to was asked what people get wrong.
"""

from __future__ import annotations

import unittest


def _prompts(intent, topic="Best UFC welterweights right now"):
    from core.content_engine import _build_prompts

    return _build_prompts(
        topic=topic,
        signals={},
        min_words=150,
        max_words=200,
        today="2026-10-10",
        channel_id="tapin",
        script_brief="",
        seo_block="",
        signal_facts="",
        signal_summary="",
        brief_block="",
        length_choice="2",
        intent=intent,
    )


EXPLAINER_SHAPE = "how it works"


class BeatsTableTests(unittest.TestCase):
    def test_five_intents_have_their_own_beats(self):
        from core.angle_intent import BEATS, beats_for

        for intent in ("list", "tutorial", "comparison", "retrospective", "reaction"):
            self.assertIn(intent, BEATS)
            self.assertGreaterEqual(beats_for(intent).count("→"), 3, intent)

    def test_other_intents_have_none_here(self):
        from core.angle_intent import beats_for

        for intent in ("explainer", "default", "take", "hope", "plan", ""):
            self.assertEqual(beats_for(intent), "", intent)


class PromptShapeTests(unittest.TestCase):
    def test_a_list_is_shaped_as_a_ranking(self):
        system, user = _prompts("list")
        text = system + user
        self.assertIn("the criteria", text)
        self.assertIn("the top pick", text)
        self.assertNotIn(EXPLAINER_SHAPE, text)

    def test_a_tutorial_is_shaped_as_steps(self):
        text = "".join(_prompts("tutorial", "How to counter the Fortnite reload meta"))
        self.assertIn("the steps in order", text)
        self.assertNotIn(EXPLAINER_SHAPE, text)

    def test_a_comparison_weighs_both_sides(self):
        text = "".join(_prompts("comparison", "Madden 27 vs College Football 27"))
        self.assertIn("where each one wins", text)

    def test_a_retrospective_and_a_reaction_have_their_own(self):
        self.assertIn("what it changed", "".join(_prompts("retrospective", "GTA 5 ten years on")))
        self.assertIn("what happened", "".join(_prompts("reaction", "GTA 6 trailer 3 reaction")))

    def test_an_explainer_keeps_its_shape(self):
        text = "".join(_prompts("explainer", "How the NFL salary cap works"))
        self.assertIn(EXPLAINER_SHAPE, text)

    def test_a_take_and_the_default_are_unchanged(self):
        from core.angle_intent import BEATS

        for intent in ("take", "default"):
            text = "".join(_prompts(intent))
            for shape in BEATS.values():
                self.assertNotIn(shape, text)


if __name__ == "__main__":
    unittest.main()
