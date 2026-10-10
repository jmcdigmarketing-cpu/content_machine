"""#1084: every angle, the script and the title keep the operator's stance; a take only
when asked.

Run 125 (2026-10-10): "Chargers Hopeium going into week 5" - the operator, asking for the
positives, the points of hope, going into week 5. All five generated angles came back as takes
against it: "masks deeper roster flaws beneath surface optimism", "Critics question whether
Chargers' Hopeium stems from genuine progress or fan denial", "could validate or shatter
Chargers' fragile Hopeium narrative", "reflects fanbase desperation", "influences betting lines".
The operator: "why am i still getting hot takes on all videos" - raised on runs 73, 77, 124.

Measured on 3b88098: the idea read as `default` intent; and `default` WAS the take - the lens
list asked for "a contrarian counter-take", the angle tables carried `controversy`, the script
prompt said "TAKE A SIDE ... Build to a strong closing line - a hot take", the insight beat
added "an opinion the audience can argue with", and the research brief defaulted to
`short_debate`. Nothing checked an angle against the idea's stance.

The operator's decision (2026-10-10): a topic that names no stance is neutral analysis; a take
only when asked for ("hot take", "overrated", "debate" ...); a hopeful idea gets reasons for hope.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

IDEA = "Chargers Hopeium going into week 5"
RUN_125 = [
    "Chargers' Hopeium masks deeper roster flaws beneath surface optimism",
    "Critics question whether Chargers' Hopeium stems from genuine progress or fan denial",
    "Week 5 showdown could validate or shatter Chargers' fragile Hopeium narrative",
    "Chargers' Hopeium reflects fanbase desperation amid mounting pressure and low expectations",
    "Analyzing how Chargers' Hopeium influences betting lines and community discourse",
]


class IntentTests(unittest.TestCase):
    def test_hopium_is_asking_for_hope(self):
        from core.angle_intent import ANGLE_HOPE, CALM_INTENTS, detect_angle_intent

        for idea in (IDEA, "chargers hopium", "Reasons for hope for the Chargers",
                     "Chargers bright spots after 0-4", "the positives from week 4"):  # fmt: skip
            self.assertEqual(detect_angle_intent(idea), ANGLE_HOPE, idea)
        self.assertIn(ANGLE_HOPE, CALM_INTENTS)

    def test_a_take_is_asked_for_by_name(self):
        from core.angle_intent import ANGLE_TAKE, detect_angle_intent

        for idea in ("World Cup and Rodri Hot takes", "Is Tua overrated?",
                     "Chargers debate: fire the coach?"):  # fmt: skip
            self.assertEqual(detect_angle_intent(idea), ANGLE_TAKE, idea)

    def test_no_stance_is_neutral_analysis(self):
        from core.angle_intent import (
            ANGLE_DEFAULT,
            angle_intent_note,
            detect_angle_intent,
            format_for_intent,
        )

        self.assertEqual(detect_angle_intent("Chargers week 5"), ANGLE_DEFAULT)
        self.assertEqual(format_for_intent(ANGLE_DEFAULT), "analysis")
        self.assertIn("neutral", angle_intent_note(ANGLE_DEFAULT))
        self.assertEqual(format_for_intent("take"), "short_debate")


class StanceFlipTests(unittest.TestCase):
    def test_run_125_angles_knock_the_hope(self):
        from core.angle_intent import ANGLE_HOPE, stance_flip

        flipped = [a for a in RUN_125 if stance_flip(a, ANGLE_HOPE)]
        self.assertEqual(flipped, RUN_125[:4])

    def test_a_reason_for_hope_is_not_a_flip(self):
        from core.angle_intent import ANGLE_HOPE, stance_flip

        for angle in ("Why the doubters are wrong about Herbert's next four games",
                      "The critical matchup that opens up for the Chargers in week 5",
                      "Three numbers that say the Chargers' 0-4 is fixable"):  # fmt: skip
            self.assertEqual(stance_flip(angle, ANGLE_HOPE), "", angle)

    def test_derision_flips_neutral_but_a_take_is_a_take(self):
        from core.angle_intent import ANGLE_DEFAULT, ANGLE_TAKE, stance_flip

        mock = "Chargers fans are in denial about this roster"
        self.assertTrue(stance_flip(mock, ANGLE_DEFAULT))
        self.assertEqual(stance_flip(mock, ANGLE_TAKE), "")
        self.assertEqual(stance_flip("SEC fraud charges against the exchange", ANGLE_DEFAULT), "")


class AngleGenerationTests(unittest.TestCase):
    def test_stance_flips_are_dropped_before_the_menu(self):
        from apis.topic_variants import _clean_angle_lines
        from core.angle_intent import ANGLE_HOPE

        dropped: list[dict] = []
        kept = _clean_angle_lines("\n".join(RUN_125), [], topic=IDEA, dropped=dropped,
                                  intent=ANGLE_HOPE)  # fmt: skip
        self.assertEqual(kept, RUN_125[4:])
        self.assertEqual([d["angle"] for d in dropped], RUN_125[:4])

    def test_the_hope_prompt_asks_for_reasons_for_hope(self):
        from apis import topic_variants

        prompts: list[str] = []

        def fake(prompt, **_kw):
            prompts.append(prompt)
            return "\n".join(
                ["Herbert's deep ball is back", "The Chargers' defense is top 10 in EPA",
                 "Week 5's opponent is 1-3 on the road", "Two starters return this week"]
            )  # fmt: skip

        with patch.object(topic_variants, "complete", side_effect=fake):
            angles = topic_variants.generate_variants(IDEA, channel_id="tapin")
        self.assertEqual(len(angles), 4)
        prompt = prompts[0]
        self.assertIn("HOPE", prompt)
        self.assertIn("not mockery", prompt)
        self.assertNotIn("contrarian", prompt)

    def test_the_neutral_default_asks_for_no_counter_take(self):
        from apis.topic_variants import _LENS_EXAMPLES, generate_variants
        from core.angle_intent import ANGLE_DEFAULT

        self.assertNotIn("contrarian", _LENS_EXAMPLES[ANGLE_DEFAULT])
        captured: list = []

        def fake(topic, angle_types, **_kw):
            captured.append(list(angle_types))
            return ["a", "b", "c"]

        with patch("apis.topic_variants.generate_ai_titles", side_effect=fake):
            generate_variants("Chargers week 5", channel_id="tapin")
        self.assertNotIn("controversy", captured[0])
        self.assertNotIn("community_controversy", captured[0])


class ScriptPromptTests(unittest.TestCase):
    def _prompts(self, topic, brief=""):
        from core.content_engine import _build_prompts

        system, user = _build_prompts(
            topic=topic, signals={}, min_words=150, max_words=300, today="2026-10-10",
            channel_id="tapin", script_brief="", seo_block="", signal_facts="",
            signal_summary="", brief_block="", length_choice="2", key_facts=None,
            seed_topic=topic, creative_brief=brief,
        )  # fmt: skip
        return system + "\n" + user

    def test_hope_gets_reasons_for_hope_and_no_take(self):
        blob = self._prompts("Chargers reasons for optimism", IDEA)
        self.assertNotIn("TAKE A SIDE", blob)
        self.assertNotIn("hot take, implication", blob)
        self.assertIn("reasons for HOPE", blob)

    def test_neutral_default_has_no_take_push(self):
        blob = self._prompts("Chargers week 5")
        self.assertNotIn("TAKE A SIDE", blob)
        self.assertNotIn("hot take, implication", blob)
        self.assertIn("neutral analysis", blob)

    def test_a_take_asked_for_still_argues(self):
        self.assertIn("TAKE A SIDE", self._prompts("Chargers hot take: fire the coach"))

    def test_no_insight_beat_on_a_hope_script(self):
        from core import content_engine as ce

        with patch.object(ce, "_call_content_llm") as call:
            out = ce._maybe_inject_insight("A recap.", "facts", IDEA)
        call.assert_not_called()
        self.assertEqual(out, "A recap.")


@patch("core.research_brief.enrich_facts", new=lambda *a, **k: "")
class ResearchBriefTests(unittest.TestCase):
    """The brief told the writer "Debate angles" and a controversy score for any topic
    without a cue word - its default format was `short_debate`, the take machinery."""

    @patch("core.research_brief._USE_LLM", False)
    @patch("analytics.competitor_context.get_competitor_prompt_block", return_value="")
    @patch("apis.stats_context_api.gather_stats_context", return_value={"lines": []})
    @patch("core.research_brief.fetch_rss_context", return_value={"headlines": []})
    @patch("core.research_brief.get_cached", return_value=None)
    @patch("core.research_brief.set_cache")
    def test_a_neutral_topic_gets_no_debate_brief(self, *_mocks):
        from core.research_brief import build_research_brief

        brief = build_research_brief("Chargers week 5", {}, channel_id="tapin")
        self.assertEqual(brief.recommended_format, "analysis")
        block = brief.to_prompt_block()
        self.assertNotIn("Debate angles", block)
        self.assertNotIn("Controversy", block)
        take = build_research_brief("Chargers hot take: fire the coach", {}, channel_id="tapin")
        self.assertEqual(take.recommended_format, "short_debate")


class TitleAndJudgeTests(unittest.TestCase):
    def test_the_title_promises_the_hope(self):
        from core import title_generator

        prompts: list[str] = []

        def fake(prompt, **_kw):
            prompts.append(prompt)
            return "Chargers Hopeium: 3 Reasons Week 5 Turns It Around"

        with patch.object(title_generator, "complete", side_effect=fake):
            title_generator.generate_title(
                script="Herbert's deep ball is back.", topic="Chargers week 5", seed_topic=IDEA,
                channel_id="tapin", brief=IDEA,
            )  # fmt: skip
        self.assertTrue(prompts)
        self.assertIn("reasons for hope", prompts[0])

    def test_the_judge_scores_the_stance(self):
        from core.angle_ranker import rank_angles

        prompts: list[str] = []

        def fake(prompt, **_kw):
            prompts.append(prompt)
            return '{"scores": [0.2, 0.9]}'

        with patch("core.llm_router.complete", side_effect=fake):
            rank_angles([RUN_125[0], "Herbert's deep ball is back"], seed_topic=IDEA,
                        llm_judge=True)  # fmt: skip
        self.assertIn("stance", prompts[0])


class PersonaTests(unittest.TestCase):
    def test_tapin_no_longer_promises_a_take(self):
        import json

        with open("config/channels.json", encoding="utf-8") as handle:
            channels = json.load(handle)
        tapin = channels["channels"]["tapin"]
        persona = " ".join(str(v) for v in tapin["persona"].values()).lower()
        self.assertNotIn("calls it straight", persona)
        self.assertNotIn("real take", persona)


if __name__ == "__main__":
    unittest.main()
