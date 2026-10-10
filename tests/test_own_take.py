"""#1090: the operator's own take is argued, not countered.

Planned 2026-10-10, measured on 6b5f648. Run 124's complaint, word for word: "the system will
take the hot take and change my idea away from my intention". Two ways it still did:

- "Jets are doomed" read `default` (no cue word), and wave 68's neutral mockery filter then
  dropped the angle that agreed with the operator: `stance_flip("Why the Jets are doomed after
  week 4", "default")` -> "'doomed' knocks a neutral one".
- "Chargers hot take: Herbert is elite" read `take`, but the take table still asked for
  `contrarian_counter_take`, its lens for "a contrarian counter-take", `stance_rule(take)` was
  empty and nothing could flip a take - "Why Herbert isn't elite" went straight to the menu.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

SIDE = "Chargers hot take: Herbert is elite"


class StatedSideTests(unittest.TestCase):
    def test_a_stated_verdict_is_a_take_with_a_side(self):
        from core.angle_intent import ANGLE_TAKE, detect_angle_intent, stated_side

        cases = {SIDE: ["elite"], "Jets are doomed": ["doomed"], "Tua is washed": ["washed"],
                 "Chargers are cooked": ["cooked"]}  # fmt: skip
        for idea, side in cases.items():
            self.assertEqual(detect_angle_intent(idea), ANGLE_TAKE, idea)
            self.assertEqual(stated_side(idea), side, idea)

    def test_a_question_or_takes_in_general_states_no_side(self):
        from core.angle_intent import stated_side

        for idea in ("Is Tua overrated?", "NBA preseason hot takes", "World Cup and Rodri Hot takes",
                     "Chargers week 5", "The Rodgers trade is done"):  # fmt: skip
            self.assertEqual(stated_side(idea), [], idea)

    def test_an_angle_against_the_side_is_a_flip(self):
        from core.angle_intent import ANGLE_TAKE, stance_flip

        self.assertIn(
            "argues against", stance_flip("Why Herbert isn't elite", ANGLE_TAKE, idea=SIDE)
        )
        self.assertIn(
            "argues against", stance_flip("Herbert is not elite yet", ANGLE_TAKE, idea=SIDE)
        )
        self.assertIn(
            "myth", stance_flip("The myth of Herbert the elite QB", ANGLE_TAKE, idea=SIDE)
        )
        self.assertEqual(
            stance_flip("Herbert's elite numbers through week 4", ANGLE_TAKE, idea=SIDE), ""
        )
        # A take with no side named keeps every angle, as before.
        self.assertEqual(
            stance_flip("Why Herbert isn't elite", ANGLE_TAKE, idea="NBA preseason hot takes"), ""
        )

    def test_the_operators_own_word_is_never_a_flip(self):
        from core.angle_intent import ANGLE_DEFAULT, stance_flip

        idea = "Chargers fans in denial going into week 5"
        self.assertEqual(
            stance_flip("Why Chargers fans are in denial", ANGLE_DEFAULT, idea=idea), ""
        )
        self.assertTrue(stance_flip("Why Chargers fans are in denial", ANGLE_DEFAULT))


class AngleTests(unittest.TestCase):
    def _variants(self, idea, reply="a\nb\nc"):
        from apis import topic_variants

        prompts: list[str] = []
        with patch.object(
            topic_variants, "complete", side_effect=lambda p, **_k: prompts.append(p) or reply
        ):
            angles = topic_variants.generate_variants(idea, channel_id="tapin")
        return angles, prompts[0]

    def test_a_stated_take_gets_angles_that_argue_it(self):
        angles, prompt = self._variants(
            SIDE, "Herbert's elite numbers through week 4\nWhy Herbert isn't elite\n"
            "The throws only an elite QB makes\nWhat Herbert's arm means for week 5",
        )  # fmt: skip
        self.assertNotIn("contrarian", prompt)
        self.assertIn("own take", prompt)
        self.assertIn("the_case_for_the_take", prompt)
        self.assertNotIn("Why Herbert isn't elite", angles)
        self.assertIn("Herbert's elite numbers through week 4", angles)

    def test_takes_in_general_keep_the_take_table(self):
        _angles, prompt = self._variants("NBA preseason hot takes")
        self.assertIn("contrarian_counter_take", prompt)

    def test_your_doomed_idea_keeps_its_doomed_angle(self):
        angles, _prompt = self._variants(
            "Jets are doomed", "Why the Jets are doomed after week 4\nWhy the Jets aren't doomed "
            "yet\nThe schedule that seals it for the Jets\nThe Jets' injury list, week 5",
        )  # fmt: skip
        self.assertIn("Why the Jets are doomed after week 4", angles)
        self.assertNotIn("Why the Jets aren't doomed yet", angles)

    def test_angle_one_keeps_your_verdict(self):
        from apis.topic_variants import idea_rewording_problem

        self.assertEqual(idea_rewording_problem("Jets are doomed", "New York Jets Are Doomed"), "")
        self.assertTrue(idea_rewording_problem("Jets are doomed", "New York Jets Are Not Doomed"))


class ScriptPromptTests(unittest.TestCase):
    def _blob(self, topic, brief=""):
        from core.content_engine import _build_prompts

        system, user = _build_prompts(
            topic=topic, signals={}, min_words=150, max_words=300, today="2026-10-10",
            channel_id="tapin", script_brief="", seo_block="", signal_facts="",
            signal_summary="", brief_block="", length_choice="2", key_facts=None,
            seed_topic=topic, creative_brief=brief,
        )  # fmt: skip
        return system + "\n" + user

    def test_the_script_argues_the_operators_side(self):
        blob = self._blob("Herbert week 5", SIDE)
        self.assertIn("own take is", blob)
        self.assertIn("Herbert is elite", blob)

    def test_takes_in_general_name_no_side(self):
        self.assertNotIn("own take is", self._blob("NBA preseason hot takes"))


if __name__ == "__main__":
    unittest.main()
