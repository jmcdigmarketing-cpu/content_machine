"""Wave 17: a claim you rendered past cannot quietly go public (#754).

Run 77: the claim verifier flagged "GTA 5 didn't win Game of the Year in 2013", the operator
answered `y` at "Render anyway?", and the video queued public (held unlisted). Nothing after the
render remembered the override - not the run features, not the publish refusal list, not the
upload prompt. Each test here failed on unmodified ec11b6f.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

RUN77_VERIFICATION = {
    "total": 9,
    "supported": 7,
    "unsupported": [
        "GTA 5 didn't win Game of the Year in 2013.",
        "GTA 5 went on to sell hundreds of millions of copies.",
    ],
}


class TestOverrideIsRecorded(unittest.TestCase):
    def test_override_features_name_the_claims(self):
        from core.claim_verifier import override_features

        features = override_features(RUN77_VERIFICATION)
        self.assertTrue(features["grounding_override"])
        self.assertIn(
            "GTA 5 didn't win Game of the Year in 2013.", features["grounding_override_claims"]
        )

    def test_no_verification_still_records_the_override(self):
        from core.claim_verifier import override_features

        self.assertTrue(override_features(None)["grounding_override"])

    def test_both_render_paths_record_it(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("main.py", "scripts/auto_generate.py"):
            with self.subTest(caller=name):
                self.assertIn("override_features(", (root / name).read_text(encoding="utf-8"))


class TestPublishListNamesTheOverride(unittest.TestCase):
    def test_a_rendered_override_blocks_publish_by_name(self):
        from core.publish_blockers import blocking_publish_reasons

        reasons = blocking_publish_reasons(
            features={
                "grounding_override": True,
                "grounding_override_claims": RUN77_VERIFICATION["unsupported"],
            }
        )
        blob = " ".join(reasons)
        self.assertIn("grounding gate", blob.lower())
        self.assertIn("GTA 5 didn't win Game of the Year in 2013.", blob)

    def test_a_clean_run_is_not_blocked_by_it(self):
        from core.publish_blockers import blocking_publish_reasons

        reasons = blocking_publish_reasons(features={})
        self.assertFalse(any("grounding gate" in r.lower() for r in reasons), reasons)


class TestUploadPromptRefusesPublic(unittest.TestCase):
    def _plan(self, answers: list[str], *, override: bool):
        from core.ui import prompt_upload_plan

        printed: list[str] = []
        replies = iter(answers)

        def _print(*args) -> None:
            printed.append(" ".join(str(a) for a in args))

        return (
            prompt_upload_plan(
                channel_id="tapin",
                topic="GTA 6",
                print_fn=_print,
                input_fn=lambda *_a, **_k: next(replies),
                grounding_override=override,
            ),
            printed,
        )

    def test_public_is_not_offered_after_an_override(self):
        plan, printed = self._plan(["2", "3"], override=True)
        self.assertEqual(plan.privacy_status, "unlisted")
        blob = " ".join(printed).lower()
        self.assertIn("grounding gate", blob)

    def test_a_clean_run_can_still_choose_public(self):
        plan, _printed = self._plan(["2", "3"], override=False)
        self.assertEqual(plan.privacy_status, "public")

    def test_main_passes_the_flag(self):
        root = Path(__file__).resolve().parents[1]
        self.assertIn("grounding_override=", (root / "main.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()


class TestIntermittentPartnerIsNormal(unittest.TestCase):
    """The operator's second agent helps intermittently; "5 commits behind" is not a defect."""

    def test_behind_note_says_so(self):
        from core.agent_comms import behind_note

        self.assertEqual(behind_note(0), "current")
        self.assertIn("intermittent", behind_note(5).lower())
        self.assertIn("5", behind_note(5))

    def test_the_mailbox_says_so_too(self):
        text = (
            Path(__file__)
            .resolve()
            .parents[1]
            .joinpath("docs/handoff.md")
            .read_text(encoding="utf-8")
        )
        self.assertIn("intermittent", text.lower())


class TestSpacedShortQueue(unittest.TestCase):
    """1 long + 5 Shorts is 6 uploads against a 5-per-7-day cap (#757)."""

    def _slots(self, count: int, *, recent: int = 1, cap: int = 5):
        from datetime import datetime, timedelta, timezone

        from core.cadence import CadenceStatus
        from core.spaced_queue import plan_spaced_uploads

        base = datetime(2026, 9, 16, 22, 0, tzinfo=timezone.utc)
        times = iter([base + timedelta(days=i) for i in range(10)])
        items = [(200 + i, f"Short {i + 1}") for i in range(count)]
        with (
            patch(
                "core.spaced_queue.cadence_status",
                return_value=CadenceStatus(recent=recent, upcoming=0, cap=cap, window_days=7),
            ),
            patch(
                "core.spaced_queue.next_optimal_post_time", side_effect=lambda *a, **k: next(times)
            ),
        ):
            return plan_spaced_uploads(items, channel_id="tapin", topic="GTA 6")

    def test_each_short_gets_a_later_slot_until_the_cap(self):
        slots = self._slots(5)
        queued = [s for s in slots if s.publish_at]
        self.assertEqual(len(queued), 4, [(s.run_id, s.skipped) for s in slots])
        stamps = [s.publish_at for s in queued]
        self.assertEqual(stamps, sorted(stamps))
        self.assertIn("cadence", slots[-1].skipped.lower())

    def test_nothing_is_queued_when_the_window_is_full(self):
        slots = self._slots(3, recent=5)
        self.assertTrue(all(s.publish_at is None for s in slots), slots)

    def test_queue_spaced_uploads_enqueues_only_the_planned_ones(self):
        from datetime import datetime, timezone

        from core.spaced_queue import SpacedSlot, queue_spaced_uploads

        when = datetime(2026, 9, 16, 22, 0, tzinfo=timezone.utc)
        slots = [
            SpacedSlot(run_id=201, title="One", publish_at=when),
            SpacedSlot(run_id=202, title="Two", publish_at=None, skipped="cadence cap"),
        ]
        record = SimpleNamespace(
            id=201,
            channel_id="tapin",
            title="One",
            description="d",
            tags_json='["GTA6"]',
            mp4_path=__file__,
        )
        repo = SimpleNamespace(get=lambda run_id: record)
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),
            patch("core.spaced_queue.enqueue_repurpose_jobs") as enqueue,
        ):
            queued = queue_spaced_uploads(slots, channel_id="tapin", privacy_status="unlisted")
        self.assertEqual(queued, [201])
        self.assertEqual(enqueue.call_count, 1)
        kwargs = enqueue.call_args.kwargs
        self.assertEqual(kwargs["content_run_id"], 201)
        self.assertEqual(kwargs["youtube_publish_at"], when)
        self.assertEqual(kwargs["privacy_status"], "unlisted")

    def test_main_offers_the_spaced_queue(self):
        text = Path(__file__).resolve().parents[1].joinpath("main.py").read_text(encoding="utf-8")
        self.assertIn("plan_spaced_uploads(", text)


class TestLongFormVoicePolicy(unittest.TestCase):
    """TTS is 91% of all-time spend ($13.50 of $14.85) and Extended is the worst case (#758).

    #775 (2026-09-17): the operator listened to the first piper Extended render and called it
    clearly worse, so the policy no longer diverts long-form by default - it diverts only when
    TTS_PROVIDER_LONG is set. These now pin that opt-in path."""

    def test_long_presets_use_the_local_voice_when_opted_in(self):
        from core.tts import long_form_provider

        with patch.dict(
            os.environ, {"TTS_PROVIDER": "", "TTS_PROVIDER_LONG": "piper"}, clear=False
        ):
            self.assertEqual(long_form_provider("elevenlabs", "4"), "piper")
            self.assertEqual(long_form_provider("elevenlabs", "3"), "piper")
            self.assertEqual(long_form_provider("elevenlabs", "2"), "elevenlabs")
            self.assertEqual(long_form_provider("elevenlabs", "1"), "elevenlabs")

    def test_an_explicit_provider_wins_everywhere(self):
        from core.tts import long_form_provider

        with patch.dict(os.environ, {"TTS_PROVIDER": "elevenlabs"}, clear=False):
            self.assertEqual(long_form_provider("elevenlabs", "4"), "elevenlabs")

    def test_the_long_provider_is_configurable(self):
        from core.tts import long_form_provider

        with patch.dict(os.environ, {"TTS_PROVIDER": "", "TTS_PROVIDER_LONG": "edge"}, clear=False):
            self.assertEqual(long_form_provider("elevenlabs", "4"), "edge")

    def test_the_render_length_reaches_the_resolver(self):
        from core import tts

        with patch.dict(
            os.environ, {"TTS_PROVIDER": "", "TTS_PROVIDER_LONG": "piper"}, clear=False
        ):
            with tts.length_context("4"):
                self.assertEqual(tts._resolve_tts_provider(), "piper")
            self.assertEqual(tts._resolve_tts_provider(), "elevenlabs")

    def test_run_media_only_passes_the_length(self):
        text = (
            Path(__file__)
            .resolve()
            .parents[1]
            .joinpath("core/pipeline.py")
            .read_text(encoding="utf-8")
        )
        self.assertIn(
            "generate_audio(script, mp3_path, channel_id=channel_id, length_choice=length_choice)",
            text,
        )

    def test_documented_in_env_example(self):
        text = (
            Path(__file__).resolve().parents[1].joinpath(".env.example").read_text(encoding="utf-8")
        )
        self.assertIn("TTS_PROVIDER_LONG", text)


RUN77_THOUGHTS = (
    "GTA 6 predictions analysis based off everything we know. talk about will it be Game of "
    "year and will that be a shortcoming? i think the online economy is the whole story here. "
    "how will it stack up to other entries?"
)


class TestOperatorQuotedVerbatim(unittest.TestCase):
    """#543. Typed thoughts are the brief since run 77, but the writer paraphrased them."""

    def test_first_person_opinions_are_picked_out(self):
        from core.idea_intake import operator_quotes

        quotes = operator_quotes(RUN77_THOUGHTS)
        self.assertTrue(any("online economy is the whole story" in q for q in quotes), quotes)
        self.assertFalse(any("how will it stack up" in q.lower() for q in quotes), quotes)

    def test_a_brief_with_no_opinion_yields_none(self):
        from core.idea_intake import operator_quotes

        self.assertEqual(operator_quotes("GTA 6 release date and price"), [])

    def test_quote_survived_rejects_a_paraphrase(self):
        from core.idea_intake import quote_survived

        quote = "i think the online economy is the whole story here"
        self.assertTrue(
            quote_survived('He said "the online economy is the whole story here."', [quote])
        )
        self.assertFalse(quote_survived("The economy matters most of all in this one.", [quote]))

    def test_the_script_prompt_carries_the_operators_words(self):
        from core.content_engine import _build_prompts

        _system, user = _build_prompts(
            topic="GTA 6 online economy",
            signals={},
            min_words=150,
            max_words=300,
            today="2026-09-15",
            channel_id="tapin",
            script_brief="",
            seo_block="",
            signal_facts="",
            signal_summary="",
            brief_block="",
            length_choice="2",
            seed_topic="GTA 6",
            creative_brief=RUN77_THOUGHTS,
        )
        self.assertIn("OPERATOR'S OWN WORDS", user)
        self.assertIn("the online economy is the whole story here", user)

    def test_the_package_records_whether_the_quote_survived(self):
        from core.content_engine import generate_content_package

        payload = {
            "script": "GTA 6 Online has no date. " * 20,
            "tags": ["GTA6", "GTA6Online", "RockstarGames", "TakeTwo", "Gaming", "GTAOnline"],
        }
        with (
            patch("core.content_engine.enrich_facts", return_value="- GTA 6 Online has no date"),
            patch("core.content_engine._call_content_llm", return_value=payload),
            patch("core.content_engine._expand_script", side_effect=lambda **k: k["script"]),
            patch(
                "core.content_engine._relength_after_postprocessing",
                side_effect=lambda script, **k: (script, list(k.get("ungrounded") or [])),
            ),
            patch("core.claim_verifier.verify_claims", return_value=None),
            patch("core.title_generator.generate_title", return_value="GTA 6 Online"),
            patch("core.content_engine._maybe_improve_hook", side_effect=lambda s: s),
            patch("core.content_engine._maybe_inject_insight", side_effect=lambda s, *_a, **_k: s),
        ):
            package = generate_content_package(
                "GTA 6 online economy",
                {},
                (150, 300),
                "2026-09-15",
                channel_id="tapin",
                creative_brief=RUN77_THOUGHTS,
                length_choice="2",
            )
        self.assertTrue(package["operator_quotes"])
        self.assertFalse(package["operator_quote_used"])

    def test_the_run_features_carry_it(self):
        text = (
            Path(__file__)
            .resolve()
            .parents[1]
            .joinpath("core/pipeline.py")
            .read_text(encoding="utf-8")
        )
        self.assertIn("operator_quote_used", text)
