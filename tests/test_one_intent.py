"""#1091: the intent is read once per run, used everywhere, and recorded as used.

Planned 2026-10-10, measured on 6b5f648. The intent was re-read about nine times per run, from
different text: the angle screen and the angle generator read the topic, then the operator's
thoughts; `run_pipeline` read the topic only, and that value is what the run recorded as
`angle_intent`; the research brief read the seed only. Option 5 with the search seed "Chargers
week 5" and the idea "Chargers Hopeium going into week 5" in the thoughts ran as hope on every
screen and was recorded as `default` - the learning loop counted a hope video as neutral.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

IDEA = "Chargers Hopeium going into week 5"
SEED = "Chargers week 5"


class ReadTests(unittest.TestCase):
    def test_the_first_text_that_names_an_intent_sets_it(self):
        from core.angle_intent import read_intent

        read = read_intent(SEED, IDEA)
        self.assertEqual((read.intent, read.source, read.cue), ("hope", "cue", "hopeium"))
        self.assertEqual(read_intent(SEED).source, "default")
        self.assertEqual(read_intent("Jets are doomed").cue, "are doomed")

    def test_the_angle_screen_says_what_set_it(self):
        from core.angle_intent import angle_intent_note, operator_intent, read_intent

        self.assertIn("hopeium", angle_intent_note(read_intent(SEED, IDEA)))
        self.assertIn("you chose", angle_intent_note(operator_intent("take")))
        self.assertEqual(
            angle_intent_note("hope"), angle_intent_note(read_intent("hope")).split(" [")[0]
        )


def _run(**kwargs):
    from core.pipeline import DiscoveryResult, run_pipeline

    discovery = DiscoveryResult(
        input_topic=SEED,
        base_signals={},
        evaluated=[("Herbert's deep ball is back", 80.0, {})],
        channel_id="tapin",
        brief=IDEA,
    )
    with (
        patch("core.pipeline.write_run_trace"),
        patch("core.pipeline.persist_quality"),
        patch("core.pipeline.build_quality", return_value={}),
        patch("core.pipeline.record_learning_outcome"),
        patch("core.pipeline.record_content_run", return_value=42),
        patch("core.pipeline.build_research_brief", return_value=MagicMock(version="v1")) as brief,
        patch("core.pipeline.generate_content_package") as content,
        patch.dict("os.environ", {"AUTO_RESEARCH_ENABLED": "false"}, clear=False),
    ):
        content.return_value = {"title": "T", "script": "S", "description": "D", "tags": []}
        result = run_pipeline(
            SEED, discovery=discovery, proceed_video=False, channel_id="tapin", **kwargs
        )
    return result, brief.call_args.kwargs, content.call_args.kwargs


class PipelineTests(unittest.TestCase):
    def test_a_hope_idea_in_the_thoughts_runs_and_is_recorded_as_hope(self):
        result, brief, content = _run(creative_brief=IDEA)
        self.assertEqual(brief.get("intent"), "hope")
        self.assertEqual(content.get("intent"), "hope")
        self.assertEqual(result.features["angle_intent"], "hope")
        self.assertEqual(result.features["intent_source"], "cue")
        self.assertEqual(result.features["intent_cue"], "hopeium")
        self.assertEqual(result.features["angle"], "hope")

    def test_the_operators_mode_is_the_runs_mode(self):
        from core.angle_intent import operator_intent

        result, brief, content = _run(creative_brief=IDEA, intent_read=operator_intent("take"))
        self.assertEqual(brief.get("intent"), "take")
        self.assertEqual(content.get("intent"), "take")
        self.assertEqual(result.features["angle_intent"], "take")
        self.assertEqual(result.features["intent_source"], "operator")


class ScriptAndTitleTests(unittest.TestCase):
    def test_the_package_takes_the_runs_intent(self):
        from core.content_engine import _build_prompts

        system, user = _build_prompts(
            topic=SEED, signals={}, min_words=150, max_words=300, today="2026-10-10",
            channel_id="tapin", script_brief="", seo_block="", signal_facts="",
            signal_summary="", brief_block="", length_choice="2", key_facts=None,
            seed_topic=SEED, creative_brief="", intent="hope",
        )  # fmt: skip
        self.assertIn("reasons for HOPE", system + user)

    def test_the_title_takes_the_runs_intent(self):
        from core import title_generator

        prompts: list[str] = []

        def fake(prompt, **_kw):
            prompts.append(prompt)
            return "Chargers Week 5: Three Reasons To Believe"

        with patch.object(title_generator, "complete", side_effect=fake):
            title_generator.generate_title(
                script="Herbert's deep ball is back.", topic=SEED, channel_id="tapin",
                intent="hope",
            )  # fmt: skip
        self.assertIn("reasons for hope", prompts[0])


if __name__ == "__main__":
    unittest.main()
