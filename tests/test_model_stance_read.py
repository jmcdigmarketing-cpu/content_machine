"""#1089: an idea the cue words cannot read gets one cheap model read, shown and correctable.

Measured on ecd737c: "Bolts bounce back week 5", "Herbert is HIM" and "Can Herbert save the
season" read `default` - the cue tables in `core/angle_intent.py` are a lexicon, and slang it
has never seen falls to neutral analysis. The lexicon was kept deliberately small because "an
inference that cannot be seen or overridden is the wrong kind of magic"; since wave 69 the read
is shown with the words that set it and "M" overrides it, so a model read can be both.

Rules pinned here: the cue words always win; the model is asked only when every text reads
neutral; its answer counts only when it quotes the idea's own words; it is asked once per run
(discovery reads it, the angle screen and the run reuse it); STANCE_MODEL_READ=false turns it off.
"""

from __future__ import annotations

import argparse
import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

IDEA = "Bolts bounce back week 5"
REPLY = '{"mode": "hope", "phrase": "bounce back"}'


def _on():
    return patch.dict(os.environ, {"STANCE_MODEL_READ": "true"})


class ReplyTests(unittest.TestCase):
    def test_a_reply_counts_only_with_the_ideas_own_words(self):
        from core.angle_intent import model_read_from_reply

        self.assertEqual(model_read_from_reply(IDEA, REPLY), ("hope", "bounce back"))
        self.assertEqual(
            model_read_from_reply(IDEA, 'Sure: {"mode": "hope", "phrase": "Bounce Back"}'),
            ("hope", "Bounce Back"),
        )
        for bad in ('{"mode": "hope", "phrase": "comeback"}',  # not the idea's words
                    '{"mode": "neutral", "phrase": "week 5"}', '{"mode": "rage", "phrase": "back"}',
                    "hope", "", '{"mode": "hope"}'):  # fmt: skip
            self.assertEqual(model_read_from_reply(IDEA, bad), ("default", ""), bad)

    def test_take_and_plan_are_read_too(self):
        from core.angle_intent import model_read_from_reply

        self.assertEqual(
            model_read_from_reply("Herbert is HIM", '{"mode": "take", "phrase": "is HIM"}'),
            ("take", "is HIM"),
        )


class ResolveTests(unittest.TestCase):
    def setUp(self):
        from core import angle_intent

        angle_intent.reset_model_reads()

    def test_slang_the_cues_miss_is_read_by_the_model(self):
        from core.angle_intent import angle_intent_note, resolve_intent

        with _on(), patch("core.llm_router.complete", return_value=REPLY) as call:
            read = resolve_intent(IDEA)
        self.assertEqual((read.intent, read.source, read.cue), ("hope", "model", "bounce back"))
        self.assertEqual(call.call_count, 1)
        note = angle_intent_note(read)
        self.assertIn("read by the model from 'bounce back'", note)
        self.assertIn("M if wrong", note)

    def test_the_cue_words_always_win_and_cost_nothing(self):
        from core.angle_intent import resolve_intent

        with _on(), patch("core.llm_router.complete") as call:
            read = resolve_intent("Chargers Hopeium going into week 5")
        self.assertEqual((read.intent, read.source), ("hope", "cue"))
        call.assert_not_called()

    def test_off_wrong_or_down_means_neutral(self):
        from core.angle_intent import reset_model_reads, resolve_intent

        with (
            patch.dict(os.environ, {"STANCE_MODEL_READ": "false"}),
            patch("core.llm_router.complete") as call,
        ):
            self.assertEqual(resolve_intent(IDEA).intent, "default")
        call.assert_not_called()
        with _on(), patch("core.llm_router.complete", side_effect=RuntimeError("down")):
            self.assertEqual(resolve_intent(IDEA).source, "default")
        reset_model_reads()
        with _on(), patch("core.llm_router.complete", return_value='{"mode":"hope","phrase":"x"}'):
            self.assertEqual(resolve_intent(IDEA).intent, "default")

    def test_one_read_per_idea(self):
        from core.angle_intent import resolve_intent

        with _on(), patch("core.llm_router.complete", return_value=REPLY) as call:
            resolve_intent(IDEA)
            resolve_intent(IDEA)
        self.assertEqual(call.call_count, 1)


def _env(**extra):
    env = {"COMPETITOR_SYNC_ON_DISCOVERY": "off", "APIFY_CONTENT_MACHINE_KEY": "",
           "STANCE_MODEL_READ": "true", "ANGLE_LLM_JUDGE": "false", **extra}  # fmt: skip
    return patch.dict(os.environ, env, clear=False)


class RunTests(unittest.TestCase):
    def setUp(self):
        from core import angle_intent

        angle_intent.reset_model_reads()

    def test_discovery_reads_once_and_the_angles_follow(self):
        from core import pipeline

        seen: dict = {}

        def fake_variants(topic, **kwargs):
            seen.update(kwargs)
            return ["Herbert's deep ball is back"]

        with (
            _env(),
            patch("core.pipeline.generate_variants", side_effect=fake_variants),
            patch("core.pipeline.build_registry", return_value={}),
            patch("core.pipeline.composite_score", return_value=10.0),
            patch("core.llm_router.complete", return_value=REPLY) as call,
        ):
            discovery = pipeline.run_discovery(IDEA, channel_id="tapin")
        self.assertEqual(seen.get("intent"), "hope")
        self.assertEqual(discovery.meta["intent_read"]["source"], "model")
        self.assertEqual(call.call_count, 1)

    def test_the_angle_screen_and_the_run_reuse_the_discoverys_read(self):
        import main
        from core.angle_intent import IntentRead
        from core.pipeline import DiscoveryResult

        discovery = DiscoveryResult(
            input_topic=IDEA, base_signals={}, evaluated=[("a", 1.0, {})], channel_id="tapin",
            meta={"intent_read": IntentRead("hope", "model", "bounce back").as_dict()},
        )  # fmt: skip
        with _env(), patch("core.llm_router.complete") as call:
            read = main._screen_intent(discovery, IDEA, "")
        call.assert_not_called()
        self.assertEqual((read.intent, read.source), ("hope", "model"))

        from unittest.mock import MagicMock

        from core.pipeline import run_pipeline

        with (
            _env(AUTO_RESEARCH_ENABLED="false"),
            patch("core.llm_router.complete") as call,
            patch("core.pipeline.write_run_trace"),
            patch("core.pipeline.persist_quality"),
            patch("core.pipeline.build_quality", return_value={}),
            patch("core.pipeline.record_learning_outcome"),
            patch("core.pipeline.record_content_run", return_value=42),
            patch("core.pipeline.build_research_brief", return_value=MagicMock(version="v1")),
            patch("core.pipeline.generate_content_package") as content,
        ):
            content.return_value = {"title": "T", "script": "S", "description": "D", "tags": []}
            result = run_pipeline(
                IDEA, discovery=discovery, proceed_video=False, channel_id="tapin"
            )
        call.assert_not_called()
        self.assertEqual(content.call_args.kwargs.get("intent"), "hope")
        self.assertEqual(result.features["intent_source"], "model")

    def test_the_operators_correction_keeps_what_was_read(self):
        from core.angle_intent import IntentRead, operator_intent

        chosen = operator_intent("plan", IntentRead("hope", "model", "bounce back"))
        self.assertEqual(chosen.features()["intent_detected"], "hope")


class CheckVerbTests(unittest.TestCase):
    def setUp(self):
        from core import angle_intent

        angle_intent.reset_model_reads()

    def test_intent_check_says_how_each_idea_reads(self):
        from scripts import ops

        text = ""
        for idea in (IDEA, "Chargers Hopeium going into week 5"):
            out = io.StringIO()
            with _on(), patch("core.llm_router.complete", return_value=REPLY), redirect_stdout(out):
                ops.COMMANDS["intent-check"][1](argparse.Namespace(target=idea, table=False))
            text += out.getvalue()
        self.assertIn("hope", text)
        self.assertIn("model", text)
        self.assertIn("bounce back", text)
        self.assertIn("hopeium", text)

    def test_the_table_counts_what_reads_as_recorded(self):
        from scripts import ops

        out = io.StringIO()
        with _on(), patch("core.llm_router.complete", return_value="{}"), redirect_stdout(out):
            ops.COMMANDS["intent-check"][1](argparse.Namespace(target=None, table=True))
        self.assertRegex(out.getvalue(), r"\d+ of \d+ read as recorded")


if __name__ == "__main__":
    unittest.main()
