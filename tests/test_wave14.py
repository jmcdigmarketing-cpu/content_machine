"""Wave 14: run 76 abort. Every test here is a live string from that run.

Observed failing on unmodified d0e687c / 378a923 before the fixes. Docstrings
name the failure; a test that was green before the change is not testing it.
"""

from __future__ import annotations

import os
import unittest
from datetime import date
from unittest.mock import patch

# Run 76 typed seed, verbatim from the operator paste.
RUN76_SEED = (
    "GTA 6 Analysis/Predictions!! Will it be the best game every? What does meeting "
    "the hype mean, is a goy candidate a failure? Long form predictions and content "
    "analysis so far"
)
RUN76_TTS_CHARS = 5720
RUN76_ANGLE_HYPE = "GTA 6 Will It Be the Best: The One Criterion That Decides It All"
RUN76_ANGLE_HONOUR = "GTA 6 Predictions: The Honorable Mention That Almost Made the List"


class TestTtsGraceAndForce(unittest.TestCase):
    """#740. 5,720 vs 5,000 is ~14%. Operator: non-consequential. `y` still raised."""

    def test_run_76_chars_are_not_a_hard_block(self):
        from core.tts_char_cap import tts_char_cap_reason

        self.assertIsNone(tts_char_cap_reason("x" * RUN76_TTS_CHARS))

    def test_fifteen_percent_over_warns_instead_of_blocking(self):
        from core.tts_char_cap import tts_char_cap_warn

        warn = tts_char_cap_warn("x" * RUN76_TTS_CHARS)
        self.assertIsNotNone(warn)
        self.assertIn("5720", warn.replace(",", ""))

    def test_past_the_grace_band_still_hard_blocks(self):
        from core.tts_char_cap import tts_char_cap_reason

        reason = tts_char_cap_reason("x" * 5751)
        self.assertIsNotNone(reason)
        self.assertIn("5751", reason.replace(",", ""))

    def test_force_skips_the_hard_raise_in_run_media_only(self):
        """main.py asked y then called run_media_only with no force flag."""
        from core import pipeline

        over = "x" * 8000
        with (
            patch.dict(
                os.environ,
                {"THUMBNAIL_MODE": "off", "CONTENT_RENDER_PROGRESS": "0"},
                clear=False,
            ),
            patch.object(
                pipeline,
                "media_paths_for_topic",
                return_value=("a.mp3", "v.mp4", "out/v.mp4"),
            ),
            patch.object(pipeline, "generate_audio") as tts,
            patch.object(pipeline, "render_vertical_video", return_value=("v", "bg")),
            patch.object(pipeline, "update_content_run_media"),
            patch.object(pipeline, "record_render_assets"),
            patch("core.run_features.load_features", return_value={}),
            patch("core.run_features.merge_features"),
            patch("core.run_trace.update_trace"),
        ):
            pipeline.run_media_only(
                "topic", over, channel_id="tapin", force=True, content_run_id=76
            )
        tts.assert_called_once()

    def test_extended_floor_covers_the_preset_max(self):
        from core.tts_char_cap import tts_char_cap_reason

        # Extended max 2000 words * 6 chars. 8000 is over 5000*1.15 but under the floor.
        self.assertIsNone(tts_char_cap_reason("x" * 8000, length_choice="4"))


class TestBestSpaceIsNotAList(unittest.TestCase):
    """#742. `"best "` inside 'best game every?' selected ANGLE_LIST."""

    def test_run_76_seed_is_not_a_listicle(self):
        from core.angle_intent import ANGLE_LIST, detect_angle_intent

        self.assertNotEqual(detect_angle_intent(RUN76_SEED), ANGLE_LIST)

    def test_real_list_cues_still_read_as_list(self):
        from core.angle_intent import ANGLE_LIST, detect_angle_intent

        self.assertEqual(detect_angle_intent("top 5 heavyweights of the decade"), ANGLE_LIST)
        self.assertEqual(detect_angle_intent("ranking every GTA protagonist"), ANGLE_LIST)


class TestWindowsPinDefaultsOff(unittest.TestCase):
    """#667. Run 76 PowerShell bled ~1,600) onto every line."""

    def test_win32_pin_is_off_unless_opted_in(self):
        from core.pinned_status import pin_enabled

        with (
            patch("sys.platform", "win32"),
            patch("sys.stdout.isatty", return_value=True),
            patch.dict(os.environ, {"NO_COLOR": "", "CONTENT_UI_PIN": ""}, clear=False),
        ):
            os.environ.pop("CONTENT_UI_PIN", None)
            self.assertFalse(pin_enabled())

    def test_win32_pin_opts_in_with_content_ui_pin(self):
        from core.pinned_status import pin_enabled

        with (
            patch("sys.platform", "win32"),
            patch("sys.stdout.isatty", return_value=True),
            patch.dict(os.environ, {"NO_COLOR": "", "CONTENT_UI_PIN": "1"}, clear=False),
        ):
            self.assertTrue(pin_enabled())


class TestGatesSeePackedFacts(unittest.TestCase):
    """#745. Jason/Lucia and $744M were packed; verifier window was 6000 chars."""

    def test_verifier_window_keeps_a_fact_past_the_old_6000_cap(self):
        from core.claim_verifier import _numbered_facts
        from core.operator_facts import operator_key_fact_char_budget

        padding = "A" * 7000
        late = "Protagonists Jason and Lucia"
        numbered = _numbered_facts(padding + "\n" + late)
        joined = "\n".join(numbered)
        self.assertIn("Jason and Lucia", joined)
        self.assertGreaterEqual(operator_key_fact_char_budget(), 12000)

    def test_script_verbs_are_not_ungrounded_specifics(self):
        from core.fact_grounding import find_ungrounded_entities

        script = (
            "Start with what we actually know. Read that list again. "
            "Compare that to GTA 5. Restricted remote work came back. "
            "The Lakers traded AD last year."
        )
        facts = "The Lakers traded AD last year. GTA 5 exists."
        flagged = find_ungrounded_entities(script, facts)
        for verb in ("Start", "Read", "Compare", "Restricted"):
            self.assertNotIn(verb, flagged, flagged)


class TestPasteAndChrome(unittest.TestCase):
    """#741. `` `paste` `` stored as fact 1; Share / ffaaa filled the 100-line budget."""

    def test_backticked_paste_is_the_paste_command(self):
        from core.operator_facts import is_paste_command

        self.assertTrue(is_paste_command("`paste`"))
        self.assertTrue(is_paste_command("paste"))
        self.assertTrue(is_paste_command("  PASTE  "))
        self.assertFalse(is_paste_command("`paste GTA 6 Developer Is Fighting Drones"))

    def test_run_76_chrome_never_packs_as_operator_facts(self):
        from core.fact_selection import select_facts_for_prompt
        from core.fact_store import TIER_OPERATOR, FactRecord

        chrome = ["`paste`", "Share", "Follow Us", "ffaaa", "Like (1)", "Related Tags"]
        real = (
            "GTA Online has been a money printer for a decade, peaking in the 2020 "
            "pandemic with $744 million in microtransaction spending in a year."
        )
        records = [
            FactRecord(claim=line, tier=TIER_OPERATOR, verified_at=date(2026, 9, 13))
            for line in [*chrome, real]
        ]
        packed, _drops = select_facts_for_prompt(
            records, topic="GTA 6", corpus="GTA 6 Online Rockstar", budget=12000
        )
        blob = "\n".join(packed)
        self.assertIn("$744 million", blob)
        for junk in chrome:
            self.assertNotIn(junk, packed)


class TestOption1BriefReachesThePrompt(unittest.TestCase):
    """#743. Option 1 type-your-own left creative_brief empty."""

    def test_typed_topic_becomes_the_editorial_angle(self):
        from core.content_engine import _build_prompts
        from core.idea_intake import brief_for_typed_topic

        brief = brief_for_typed_topic(RUN76_SEED)
        self.assertIn("meeting the hype", brief.lower())
        _system, user = _build_prompts(
            topic="GTA 6 Will It Be the Best: The One Criterion That Decides It All",
            signals={},
            min_words=150,
            max_words=300,
            today="2026-09-13",
            channel_id="tapin",
            script_brief="",
            seo_block="",
            signal_facts="",
            signal_summary="",
            brief_block="",
            length_choice="2",
            seed_topic=RUN76_SEED,
            creative_brief=brief,
        )
        self.assertIn("EDITORIAL ANGLE", user)
        self.assertIn("meeting the hype", user.lower())


class TestThesisRanking(unittest.TestCase):
    """#744. Editorial 0.54-0.58 could not tell a hype thesis from an honourable mention."""

    def test_hype_criterion_outranks_honourable_mention(self):
        from core.angle_ranker import rank_angles

        scores = rank_angles(
            [RUN76_ANGLE_HYPE, RUN76_ANGLE_HONOUR],
            seed_topic=RUN76_SEED,
            llm_judge=False,
        )
        self.assertGreater(
            scores[RUN76_ANGLE_HYPE],
            scores[RUN76_ANGLE_HONOUR],
            scores,
        )

    def test_cheap_judge_fail_open_keeps_deterministic_ranking(self):
        from core.angle_ranker import rank_angles

        with patch("core.llm_router.complete", side_effect=RuntimeError("no key")):
            scores = rank_angles(
                [RUN76_ANGLE_HYPE, RUN76_ANGLE_HONOUR],
                seed_topic=RUN76_SEED,
                llm_judge=True,
            )
        self.assertGreater(scores[RUN76_ANGLE_HYPE], scores[RUN76_ANGLE_HONOUR], scores)


if __name__ == "__main__":
    unittest.main()
