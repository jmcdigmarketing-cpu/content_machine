"""#1016: your idea stays yours.

Run 124: the operator typed "How the 0-4 chargers can turn it around this year" and got "a
good video, just not what i intended": "the system will take the hot take and change my
idea away from my intention too often". Asked, they set the rule: angle 1 is "100% the
intention of my idea, maybe just worded with more seo velocity ... rephrasing which i want,
[not] making it a hot take". Measured causes:

- "how can" was no intent cue, so the run was `default`: the prompt said "TAKE A SIDE",
  "hot take", "my prediction", and the insight pass added an opinion beat;
- the operator's words sat under "EDITORIAL ANGLE (the creator's deliberate take ...)" and
  the chosen hot-take angle under "TOPIC";
- only option 5 offered "your idea" (as 0, never the default); option 1 offered none;
- the ranker's thesis term was "can turn it around this" and no angle contained it, and the
  lower-case "chargers" was no subject term, so every angle's seed fidelity was 0;
- nothing checked that the script answered the question typed.

Now: `ANGLE_PLAN` (a calm intent - "answer the question: what must happen, in order");
the intent is read from the brief too; `apis.topic_variants.idea_angle` words the typed
idea for search and refuses a rewording that adds a take; it is angle 1 and Enter keeps it,
for option 1 and option 5; choosing it removes the take push and the insight beat; the
idea block heads the prompt; and `keep_to_idea` checks the script answers the idea, with
one rewrite when it does not.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

IDEA = "How the 0-4 chargers can turn it around this year"


class IntentTests(unittest.TestCase):
    def test_how_can_is_a_plan(self):
        from core.angle_intent import ANGLE_PLAN, CALM_INTENTS, detect_angle_intent

        self.assertEqual(detect_angle_intent(IDEA), ANGLE_PLAN)
        self.assertIn(ANGLE_PLAN, CALM_INTENTS)

    def test_the_brief_counts_when_the_angle_says_nothing(self):
        from core.angle_intent import ANGLE_PLAN, intent_of

        self.assertEqual(intent_of("Chargers season outlook", "", IDEA), ANGLE_PLAN)


def _prompts(**kw):
    from core.content_engine import _build_prompts

    base = {"topic": "The Chargers' 2026 season hinges on beating Denver", "signals": {},
            "min_words": 150, "max_words": 200, "today": "2026-10-09", "channel_id": "tapin",
            "script_brief": "", "seo_block": "", "signal_facts": "", "signal_summary": "",
            "brief_block": "", "length_choice": "2", "seed_topic": IDEA,
            "creative_brief": IDEA}  # fmt: skip
    base.update(kw)
    return _build_prompts(**base)


class PromptTests(unittest.TestCase):
    def test_a_plan_answers_the_question(self):
        system, user = _prompts()
        both = system + user
        self.assertNotIn("TAKE A SIDE", both)
        self.assertNotIn("my prediction", both)
        self.assertIn("in order", both)
        self.assertIn("THE OPERATOR'S IDEA", user)
        self.assertLess(user.index("THE OPERATOR'S IDEA"), user.index("ANGLE:"))

    def test_your_idea_chosen_drops_the_take_push_on_any_intent(self):
        system, user = _prompts(seed_topic="Chargers season", creative_brief="Chargers season",
                                own_idea=True)  # fmt: skip
        both = system + user
        self.assertNotIn("TAKE A SIDE", both)
        self.assertNotIn("hot take, implication", both)
        self.assertIn("answer the operator's idea as asked", both.lower())

    def test_an_angle_the_operator_did_not_type_still_argues(self):
        system, user = _prompts(seed_topic="Chargers season", creative_brief="")
        self.assertIn("TAKE A SIDE", system + user)

    def test_no_insight_beat_on_your_idea(self):
        from core.content_engine import _maybe_inject_insight

        with patch("core.content_engine._call_content_llm") as llm:
            out = _maybe_inject_insight("A neutral recap.", "facts", "Chargers season",
                                        own_idea=True)  # fmt: skip
        self.assertEqual(out, "A neutral recap.")
        llm.assert_not_called()


class IdeaAngleTests(unittest.TestCase):
    def _angle(self, reply):
        from apis.topic_variants import idea_angle

        with patch("core.llm_router.complete", side_effect=reply):
            return idea_angle(IDEA, "tapin")

    def test_an_seo_rewording_is_kept(self):
        got = self._angle(
            lambda *a, **k: "How the 0-4 Chargers Can Still Turn Their 2026 Season Around"
        )
        self.assertEqual(got, "How the 0-4 Chargers Can Still Turn Their 2026 Season Around")

    def test_a_hot_take_is_refused(self):
        got = self._angle(lambda *a, **k: "The Chargers Are Done: Why 0-4 Is the End")
        self.assertEqual(got, IDEA)

    def test_a_different_question_is_refused(self):
        got = self._angle(lambda *a, **k: "Is Jim Harbaugh on the hot seat in Los Angeles?")
        self.assertEqual(got, IDEA)

    def test_no_model_keeps_the_words(self):
        def boom(*a, **k):
            raise RuntimeError("down")

        self.assertEqual(self._angle(boom), IDEA)


class MenuTests(unittest.TestCase):
    def test_your_idea_is_angle_one(self):
        from core.ui import display_variants

        printed: list[str] = []
        evaluated = [("The Chargers' season hinges on Denver", 90.0, {}),
                     ("Why the Chargers' 0-4 start is a mirage", 88.0, {})]  # fmt: skip
        with patch("core.ui.subsection"):
            display_variants(evaluated, idea_angle="How the 0-4 Chargers can turn it around",
                             print_fn=lambda *a: printed.append(" ".join(map(str, a))))  # fmt: skip
        text = "\n".join(printed)
        self.assertIn("1. How the 0-4 Chargers can turn it around", text)
        self.assertIn("your idea", text)
        self.assertIn("2.", text)
        self.assertIn("3.", text)

    def test_enter_and_one_keep_your_idea(self):
        import main

        for answer in ("", "1"):
            self.assertEqual(main._parse_angle_choice(answer, 2, 1, allow_own=False,
                                                      idea_first=True), ("own", -1))  # fmt: skip
        self.assertEqual(main._parse_angle_choice("3", 2, 1, allow_own=False, idea_first=True),
                         ("one", 1))  # fmt: skip
        self.assertEqual(main._parse_angle_choice("", 2, 1, allow_own=False), ("one", 1))

    def test_option_one_typed_idea_counts(self):
        import main

        self.assertEqual(main._typed_idea(topic=IDEA, creative_brief=IDEA, seed_topic=None,
                                          from_best_bet=False), IDEA)  # fmt: skip
        self.assertEqual(main._typed_idea(topic="best bet topic", creative_brief="",
                                          seed_topic=None, from_best_bet=True), "")  # fmt: skip
        self.assertEqual(main._typed_idea(topic=IDEA, creative_brief="my thoughts",
                                          seed_topic=IDEA, from_best_bet=False), "my thoughts")  # fmt: skip

    def test_the_pipeline_carries_it(self):
        import inspect

        from core import pipeline

        self.assertIn("own_idea", inspect.signature(pipeline.run_pipeline).parameters)
        self.assertIn("own_idea=own_idea", inspect.getsource(pipeline.run_pipeline))


class FidelityTests(unittest.TestCase):
    def test_the_seed_terms_find_the_team_and_the_question(self):
        from core.angle_ranker import _fidelity, _seed_terms

        terms = _seed_terms(IDEA)
        self.assertIn("Chargers", terms)
        on = _fidelity("How the Chargers can still turn it around after 0-4", terms)
        off = _fidelity("Harbaugh's hot seat is the real story in LA", terms)
        self.assertGreater(on, off)
        self.assertGreater(on, 0.5)


class KeepToIdeaTests(unittest.TestCase):
    def test_a_script_that_answers_is_kept(self):
        from core.content_engine import _keep_to_idea

        with patch("core.content_engine._call_content_llm",
                   return_value={"answers": True, "missing": ""}) as llm:  # fmt: skip
            script, extra = _keep_to_idea("S", IDEA, min_words=1, max_words=999)
        self.assertEqual(script, "S")
        self.assertTrue(extra["answers_idea"])
        self.assertEqual(llm.call_count, 1)

    def test_a_script_that_drifted_is_rewritten_once(self):
        from core.content_engine import _keep_to_idea

        replies = [{"answers": False, "missing": "what must change to win"},
                   {"script": "The Chargers turn it around if three things change."},
                   {"answers": True, "missing": ""}]  # fmt: skip
        with patch("core.content_engine._call_content_llm", side_effect=replies) as llm:
            script, extra = _keep_to_idea("Beat Denver or it is over.", IDEA, min_words=1,
                                          max_words=999)  # fmt: skip
        self.assertIn("three things", script)
        self.assertTrue(extra["answers_idea"])
        self.assertEqual(extra["missing_before"], "what must change to win")
        self.assertEqual(llm.call_count, 3)

    def test_no_idea_no_call(self):
        from core.content_engine import _keep_to_idea

        with patch("core.content_engine._call_content_llm") as llm:
            self.assertEqual(_keep_to_idea("S", "", min_words=1, max_words=9)[0], "S")
        llm.assert_not_called()


class TitleAndCardTests(unittest.TestCase):
    def test_the_title_prompt_carries_the_idea(self):
        from core import title_generator

        prompts: list[str] = []

        def fake(prompt, **_kw):
            prompts.append(prompt)
            return "How the 0-4 Chargers can still turn their season around"

        with patch.object(title_generator, "_complete_or_none", side_effect=fake):
            title_generator.generate_title(script="The Chargers are 0-4.", topic=IDEA,
                                           seed_topic=IDEA, brief=IDEA)  # fmt: skip
        self.assertIn("THE OPERATOR'S IDEA", prompts[0])
        self.assertIn(IDEA, prompts[0])

    def test_the_card_says_when_the_idea_went_unanswered(self):
        from core.video_grade import format_script_passes

        line = format_script_passes([
            {"name": "keep_to_idea", "adopted": False, "answers_idea": False,
             "missing_before": "what must change"}])  # fmt: skip
        self.assertIn("may not answer your idea", line)
        self.assertIn("what must change", line)
        rewritten = format_script_passes([
            {"name": "keep_to_idea", "adopted": True, "answers_idea": True, "word_delta": 4}])  # fmt: skip
        self.assertIn("idea +4w", rewritten)


if __name__ == "__main__":
    unittest.main()
