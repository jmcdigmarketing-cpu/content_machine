"""#1096: an idea that asks for two things gets both.

Filed 2026-10-10 from the topic -> angle plan, measured on ecd737c: the intent read is "first
match wins" (`core/angle_intent._detect`), so "How the Chargers turn it around - reasons for hope"
read `hope` and lost the plan it also asked for ("turn it around"); "hot take tier list" kept the
take and lost the list. The angles came from one table and the script got one shape.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

TWO = "How the Chargers turn it around - reasons for hope"


class ReadTests(unittest.TestCase):
    def test_every_ask_is_read_in_table_order(self):
        from core.angle_intent import intents_in

        self.assertEqual(intents_in(TWO), ["hope", "plan"])
        self.assertEqual(intents_in("NBA hot take tier list"), ["take", "list"])
        self.assertEqual(intents_in("Chargers Hopeium going into week 5"), ["hope"])
        self.assertEqual(intents_in("Chargers week 5"), [])

    def test_the_read_keeps_the_second_ask(self):
        from core.angle_intent import angle_intent_note, read_intent

        read = read_intent(TWO)
        self.assertEqual(
            (read.intent, read.also, read.also_cue), ("hope", "plan", "turn it around")
        )
        self.assertEqual(read.features()["intent_also"], "plan")
        self.assertIn("+ plan", angle_intent_note(read))
        # The second ask may come from the operator's thoughts.
        read = read_intent("Chargers reasons for hope", "how can they turn it around")
        self.assertEqual((read.intent, read.also), ("hope", "plan"))
        self.assertEqual(read_intent("Chargers Hopeium going into week 5").also, "")

    def test_a_mode_the_operator_picks_is_one_mode(self):
        from core.angle_intent import operator_intent, read_intent

        self.assertEqual(operator_intent("take", read_intent(TWO)).also, "")


class AngleTests(unittest.TestCase):
    def _prompt(self, idea):
        from apis import topic_variants

        prompts: list[str] = []
        with patch.object(
            topic_variants, "complete", side_effect=lambda p, **_k: prompts.append(p) or "a\nb\nc"
        ):
            topic_variants.generate_variants(idea, channel_id="tapin")
        return prompts[0]

    def test_the_angles_answer_both_asks(self):
        prompt = self._prompt(TWO)
        self.assertIn("the_strongest_reason_for_hope", prompt)
        self.assertIn("the_plan_that_answers_it", prompt)

    def test_one_ask_keeps_one_table(self):
        self.assertNotIn("the_plan_that_answers_it", self._prompt("Chargers reasons for hope"))


class ScriptTests(unittest.TestCase):
    def _blob(self, brief):
        from core.content_engine import _build_prompts

        system, user = _build_prompts(
            topic="Chargers week 5", signals={}, min_words=150, max_words=300,
            today="2026-10-10", channel_id="tapin", script_brief="", seo_block="",
            signal_facts="", signal_summary="", brief_block="", length_choice="2",
            key_facts=None, seed_topic="Chargers week 5", creative_brief=brief,
        )  # fmt: skip
        return system + "\n" + user

    def test_the_script_is_told_about_the_second_ask(self):
        blob = self._blob(TWO)
        self.assertIn("reasons for HOPE", blob)
        self.assertIn("also asks", blob)
        self.assertIn("what has to change", blob)
        self.assertNotIn("also asks", self._blob("Chargers reasons for hope"))

    def test_the_run_passes_its_second_ask(self):
        from core.content_engine import _build_prompts

        system, user = _build_prompts(
            topic="Chargers week 5", signals={}, min_words=150, max_words=300,
            today="2026-10-10", channel_id="tapin", script_brief="", seo_block="",
            signal_facts="", signal_summary="", brief_block="", length_choice="2",
            key_facts=None, seed_topic="Chargers week 5", intent="take", intent_also="list",
        )  # fmt: skip
        self.assertIn("ranked list", system + user)


if __name__ == "__main__":
    unittest.main()
