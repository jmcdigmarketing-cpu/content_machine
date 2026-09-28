"""#883-#886: more than one voice, chosen once per run.

`resolve_tts_config` returned the channel's fixed `voice_id` whenever one was set, so
the `voice_pool` in channels.json was dead config and every run was the same voice.
Resolving per synth call also meant a pool would change voice between sentences. The
voices are now picked once per run (`voice_context`), rotate when `tts.rotate` is on,
and a run can carry several roles: a quote voice, a voice per chapter, two hosts.
"""

from __future__ import annotations

import os
import random
import tempfile
import unittest
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import patch

from tests.test_quota_governor import GovernorCase

POOL = {"voiceA": 4, "voiceB": 2, "voiceC": 1}


def _profile(**over):
    base = {
        "tts_model_id": "m1",
        "tts_voice_id": "voiceA",
        "tts_voice_pool": dict(POOL),
        "tts_rotate": True,
        "local_tts_voices": None,
        "local_tts_voice": None,
    }
    base.update(over)
    return SimpleNamespace(**base)


class RotationTests(unittest.TestCase):
    def setUp(self):
        from core import tts

        tts.reset_dead_voices()

    def test_rotate_uses_the_pool_not_the_fixed_voice(self):
        from core import tts

        seen = set()
        with patch("core.tts.get_channel_profile", return_value=_profile()):
            for seed in range(40):
                random.seed(seed)
                with tts.voice_context({}):
                    seen.add(tts.resolve_tts_config("tapin")[0])
        self.assertGreater(len(seen), 1, "rotate on must draw from the pool")

    def test_rotate_off_keeps_the_fixed_voice(self):
        from core import tts

        with patch("core.tts.get_channel_profile", return_value=_profile(tts_rotate=False)):
            with tts.voice_context({}):
                self.assertEqual(tts.resolve_tts_config("tapin")[0], "voiceA")

    def test_one_voice_for_every_call_of_a_run(self):
        from core import tts

        with patch("core.tts.get_channel_profile", return_value=_profile()):
            for seed in range(10):
                random.seed(seed)
                with tts.voice_context({}):
                    first = tts.resolve_tts_config("tapin")[0]
                    others = {tts.resolve_tts_config("tapin")[0] for _ in range(20)}
                self.assertEqual(others, {first})

    def test_cache_voice_is_the_run_voice(self):
        from core import tts

        with (
            patch("core.tts.get_channel_profile", return_value=_profile()),
            patch.dict(os.environ, {"TTS_PROVIDER": "elevenlabs"}),
        ):
            with tts.voice_context({"narrator": "voiceC"}):
                # #890 appends the speaking pace ("voiceC@0.95"); the voice is the run's.
                self.assertTrue(tts._tts_cache_voice("tapin").startswith("voiceC"))
                self.assertEqual(tts.resolve_tts_config("tapin")[0], "voiceC")

    def test_a_dead_run_voice_is_replaced_for_the_rest_of_the_run(self):
        from core import tts

        with patch("core.tts.get_channel_profile", return_value=_profile()):
            ctx = {"narrator": "voiceA"}
            with tts.voice_context(ctx):
                tts._mark_voice_dead("voiceA", "voice_not_found")
                replacement = tts.resolve_tts_config("tapin")[0]
                self.assertNotEqual(replacement, "voiceA")
                self.assertEqual(tts.resolve_tts_config("tapin")[0], replacement)
        tts.reset_dead_voices()

    def test_roles_resolve_to_their_own_voice(self):
        from core import tts

        with patch("core.tts.get_channel_profile", return_value=_profile()):
            with tts.voice_context({"narrator": "voiceA", "cohost": "voiceB"}):
                with tts.voice_role("cohost"):
                    self.assertEqual(tts.resolve_tts_config("tapin")[0], "voiceB")
                self.assertEqual(tts.resolve_tts_config("tapin")[0], "voiceA")

    def test_the_real_channels_rotate(self):
        from config.channels import get_channel_profile

        for cid in ("tapin", "moneywise"):
            profile = get_channel_profile(cid)
            self.assertTrue(profile.tts_rotate, cid)
            self.assertGreaterEqual(len(profile.tts_voice_pool or {}), 2, cid)


class PickRunVoicesTests(unittest.TestCase):
    def _pick(self, roles=("narrator",), previous="", profile=None, seed=0):
        from core.voice.plan import pick_run_voices

        with patch("core.voice.plan.get_channel_profile", return_value=profile or _profile()):
            return pick_run_voices(
                "tapin", roles, previous_narrator=previous, rng=random.Random(seed)
            )

    def test_never_repeats_the_previous_narrator(self):
        for seed in range(30):
            self.assertNotEqual(self._pick(previous="voiceA", seed=seed)["narrator"], "voiceA")

    def test_extra_roles_get_distinct_voices(self):
        voices = self._pick(roles=("narrator", "quote", "cohost"))
        self.assertEqual(len(set(voices.values())), 3)

    def test_roles_beyond_the_pool_come_from_the_catalog(self):
        profile = _profile(tts_voice_pool={"voiceA": 1}, tts_rotate=False)
        with patch("core.voice.plan.load_voice_registry", return_value={"x": {"voiceZ": 1}}):
            voices = self._pick(roles=("narrator", "cohost"), profile=profile)
        self.assertEqual(voices, {"narrator": "voiceA", "cohost": "voiceZ"})

    def test_rotate_off_narrator_is_the_fixed_voice(self):
        voices = self._pick(profile=_profile(tts_rotate=False), previous="voiceA")
        self.assertEqual(voices["narrator"], "voiceA")


class PlanSegmentsTests(unittest.TestCase):
    def test_single_is_one_narrator_segment(self):
        from core.voice.plan import plan_segments

        segs = plan_segments("One. Two.", "single")
        self.assertEqual([(s.text, s.role) for s in segs], [("One. Two.", "narrator")])

    def test_quotes_of_four_words_or_more_take_the_quote_voice(self):
        from core.voice.plan import plan_segments

        script = (
            'Dana White said, "we are not doing that fight this year." Then he left. '
            'Fans said "no way" online. He called it “the biggest card we have ever done”.'
        )
        segs = plan_segments(script, "quotes")
        quotes = [s.text for s in segs if s.role == "quote"]
        self.assertEqual(len(quotes), 2)
        self.assertIn("we are not doing that fight this year", quotes[0])
        self.assertIn("the biggest card we have ever done", quotes[1])
        self.assertNotIn("no way", " ".join(quotes), "a two-word quote stays narrated")
        self.assertEqual(" ".join(s.text for s in segs).split(), script.split())

    def test_chapters_split_at_char_start_one_role_each(self):
        from core.angle_chapters import AngleChapter
        from core.voice.plan import plan_segments

        script = "Intro line. First angle text. Second angle text. Third angle text."
        starts = [script.index("First"), script.index("Second"), script.index("Third")]
        chapters = [AngleChapter(i + 1, f"t{i}", f"a{i}", 0, c) for i, c in enumerate(starts)]
        segs = plan_segments(script, "chapters", chapters=chapters)
        self.assertEqual(len({s.role for s in segs}), 3)
        self.assertTrue(segs[1].text.startswith("Second"))
        self.assertTrue(segs[2].text.startswith("Third"))
        self.assertEqual("".join(s.text for s in segs).split(), script.split())

    def test_debate_tags_become_two_voices(self):
        from core.voice.plan import plan_segments

        script = (
            "HOST: Topuria is the best featherweight ever.\n"
            "CO-HOST: No chance. Volkanovski held the belt longer.\n"
            "That still counts for something.\n"
            "**HOST:** Longevity is not dominance."
        )
        segs = plan_segments(script, "debate")
        self.assertEqual([s.role for s in segs], ["narrator", "cohost", "narrator"])
        self.assertIn("That still counts", segs[1].text)
        self.assertNotIn("HOST", " ".join(s.text for s in segs))

    def test_debate_turns_survive_a_rewrite_of_the_clean_script(self):
        from core.voice.plan import parse_speaker_turns, plan_segments, strip_speaker_tags

        tagged = (
            "HOST: Topuria is the best featherweight ever.\n"
            "CO-HOST: No chance, Volkanovski held the belt far longer."
        )
        turns = parse_speaker_turns(tagged)
        rewritten = (
            "Topuria is the greatest featherweight ever. "
            "No chance, Volkanovski held that belt far longer."
        )
        self.assertNotIn("HOST", strip_speaker_tags(tagged))
        segs = plan_segments(rewritten, "debate", turns=turns)
        self.assertEqual([s.role for s in segs], ["narrator", "cohost"])

    def test_strip_leaves_ordinary_text_alone(self):
        from core.voice.plan import strip_speaker_tags

        text = "The host city: Las Vegas. He said the co-host role is gone."
        self.assertEqual(strip_speaker_tags(text), text)


class MultiVoiceSynthTests(unittest.TestCase):
    def test_each_segment_is_synthesized_in_its_role_voice(self):
        from core import tts
        from core.voice.plan import Segment

        calls = []

        def fake_synth(spoken, alt, path, channel_id, key, *, allow_piper_mix=True):
            calls.append((spoken, tts.resolve_tts_config(channel_id)[0], allow_piper_mix))
            with open(path, "wb") as f:
                f.write(b"x")
            with open(path + ".words.json", "w", encoding="utf-8") as f:
                f.write('[{"word": "w", "start": 0.0, "end": 1.0}]')
            return path

        def fake_concat(paths, out):
            with open(out, "wb") as f:
                for part in paths:
                    with open(part, "rb") as src:
                        f.write(src.read())

        segs = [
            Segment("He said", "narrator"),
            Segment('"this is a long quote here"', "quote"),
            Segment("and left.", "narrator"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "a.mp3")
            with (
                patch.dict(os.environ, {"TTS_PROVIDER": "elevenlabs"}),
                patch("core.tts.get_channel_profile", return_value=_profile()),
                patch("core.tts.ffmpeg_concat_ready", return_value=True),
                patch("core.tts.synthesize_to_path", side_effect=fake_synth),
                patch("core.tts.concat_audio_segments", side_effect=fake_concat),
                patch("core.tts.segment_audio_duration", return_value=1.0),
            ):
                tts.generate_audio(
                    'He said "this is a long quote here" and left.',
                    out,
                    channel_id="tapin",
                    voices={"narrator": "voiceA", "quote": "voiceB"},
                    segments=segs,
                )
                self.assertTrue(os.path.isfile(out))
                import json

                with open(out + ".words.json", encoding="utf-8") as f:
                    words = json.load(f)
        self.assertEqual([c[1] for c in calls], ["voiceA", "voiceB", "voiceA"])
        self.assertFalse(any(c[2] for c in calls), "no piper mix inside a multi-voice render")
        self.assertEqual([w["start"] for w in words], [0.0, 1.0, 2.0])

    def test_single_role_takes_the_ordinary_path(self):
        from core import tts
        from core.voice.plan import Segment

        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "a.mp3")
            with (
                patch.dict(os.environ, {"TTS_PROVIDER": "elevenlabs"}),
                patch("core.tts.get_channel_profile", return_value=_profile()),
                patch("core.tts.synthesize_to_path", return_value=out) as synth,
                patch("core.tts._generate_by_sentences") as by_sent,
            ):
                tts.generate_audio(
                    "One line only.",
                    out,
                    channel_id="tapin",
                    voices={"narrator": "voiceB"},
                    segments=[Segment("One line only.", "narrator")],
                )
        by_sent.assert_not_called()
        synth.assert_called_once()


class DebatePromptTests(unittest.TestCase):
    def test_directive_only_in_debate_mode(self):
        from core.voice.plan import voice_mode_directive

        self.assertIn("CO-HOST:", voice_mode_directive("debate"))
        for mode in ("single", "quotes", "chapters", ""):
            self.assertEqual(voice_mode_directive(mode), "")

    def test_menu_offers_chapter_voices_only_with_chapters(self):
        from core.voice.plan import voice_menu_lines

        self.assertNotIn("3)", " ".join(voice_menu_lines(all_angles=False)))
        self.assertIn("3)", " ".join(voice_menu_lines(all_angles=True)))
        self.assertIn("debate", " ".join(voice_menu_lines()))

    def test_menu_choice_maps_to_modes(self):
        from core.voice.plan import voice_mode_from_choice

        self.assertEqual(voice_mode_from_choice(""), "single")
        self.assertEqual(voice_mode_from_choice("2"), "quotes")
        self.assertEqual(voice_mode_from_choice("3", all_angles=True), "chapters")
        self.assertEqual(voice_mode_from_choice("3", all_angles=False), "single")
        self.assertEqual(voice_mode_from_choice("4"), "debate")
        self.assertEqual(voice_mode_from_choice("x"), "single")


class RunPlanTests(unittest.TestCase):
    def test_plan_for_run_reads_the_stored_mode_and_avoids_the_last_voice(self):
        from core.voice.plan import plan_for_run

        features = {"voice_mode": "debate"}
        prev = SimpleNamespace(id=5, features_json='{"voices": {"narrator": "voiceA"}}')
        repo = SimpleNamespace(list_for_channel=lambda cid, status=None: [prev])
        with (
            patch("core.voice.plan.load_features", return_value=features),
            patch("core.voice.plan._run_repo", return_value=repo),
            patch("core.voice.plan.get_channel_profile", return_value=_profile()),
        ):
            voices, segs = plan_for_run(
                "HOST: One claim here.\nCO-HOST: A rebuttal there.", "tapin", 6
            )
        self.assertNotEqual(voices["narrator"], "voiceA")
        self.assertIn("cohost", voices)
        self.assertEqual([s.role for s in segs or []], ["narrator", "cohost"])

    def test_no_run_is_one_rotating_voice(self):
        from core.voice.plan import plan_for_run

        with patch("core.voice.plan.get_channel_profile", return_value=_profile()):
            voices, segs = plan_for_run("Plain script.", "tapin", None)
        self.assertEqual(list(voices), ["narrator"])
        self.assertIsNone(segs)


DEBATE_SCRIPT = (
    "HOST: Topuria is the best featherweight the UFC has ever had.\n"
    "CO-HOST: No chance. Volkanovski defended the belt five times in a row.\n"
    "HOST: Defences are not the same as finishing the best man in the division."
)


class DebatePipelineTests(unittest.TestCase):
    """The tags are a TTS instruction; nothing a viewer or checker reads may carry them."""

    def test_content_engine_strips_tags_and_keeps_the_turns(self):
        from core import content_engine as ce
        from core.content_engine import generate_content_package

        payload = {
            "script": DEBATE_SCRIPT,
            "title": "Topuria vs Volkanovski",
            "description": "HOST: who is the best featherweight?",
            "tags": ["ufc"],
        }
        seen = {}

        def fake_ground(script, *a, **k):
            seen["grounding"] = script
            return []

        with (
            patch.object(ce, "enrich_facts", return_value="Topuria won the title."),
            patch.object(ce, "_call_content_llm", return_value=payload),
            patch.object(ce, "find_ungrounded_entities", side_effect=fake_ground),
            patch("core.claim_verifier.verify_claims", return_value=None),
            patch("core.title_generator.generate_title", return_value="Topuria vs Volkanovski"),
        ):
            pkg = generate_content_package(
                "Topuria vs Volkanovski",
                {},
                (20, 200),
                "2026-09-26",
                channel_id="tapin",
                length_choice="1",
                voice_mode="debate",
            )
        for key in ("script", "description"):
            self.assertNotIn("HOST:", pkg[key], key)
        self.assertNotIn("HOST:", seen.get("grounding", ""))
        self.assertEqual(
            [t["role"] for t in pkg["speaker_turns"]], ["narrator", "cohost", "narrator"]
        )

    def _run(self, voice_mode, chapter_angles=None):
        from core.pipeline import DiscoveryResult, run_pipeline

        turns = [{"role": "narrator", "text": "a"}, {"role": "cohost", "text": "b"}]
        discovery = DiscoveryResult(
            input_topic="Topuria",
            base_signals={},
            evaluated=[("Topuria vs Volkanovski", 100.0, {})],
            channel_id="tapin",
        )
        with (
            patch("core.pipeline.write_run_dossier"),
            patch("core.pipeline.write_run_trace"),
            patch("core.pipeline.persist_quality"),
            patch("core.pipeline.build_quality", return_value={}),
            patch("core.pipeline.record_learning_outcome"),
            patch("core.pipeline.record_content_run", return_value=101),
            patch(
                "core.pipeline.build_research_brief",
                return_value=SimpleNamespace(version="v1", to_prompt_block=lambda: ""),
            ),
            patch("core.pipeline.generate_content_package") as mock_content,
            patch("core.llm_router.complete_json", side_effect=RuntimeError("down")),
        ):
            mock_content.return_value = {
                "title": "T",
                "script": "Topuria is the best. No chance.",
                "description": "d",
                "speaker_turns": turns if voice_mode == "debate" else [],
            }
            result = run_pipeline(
                "Topuria",
                discovery=discovery,
                variant_index=0,
                length_choice="1",
                proceed_video=False,
                channel_id="tapin",
                voice_mode=voice_mode,
                chapter_angles=chapter_angles,
            )
        return mock_content.call_args.kwargs, result, turns

    def test_run_pipeline_briefs_the_debate_and_stores_mode_and_turns(self):
        kwargs, result, turns = self._run("debate")
        self.assertIn("CO-HOST:", kwargs["creative_brief"])
        self.assertEqual(kwargs["voice_mode"], "debate")
        self.assertEqual(result.features["voice_mode"], "debate")
        self.assertEqual(result.features["speaker_turns"], turns)

    def test_other_modes_leave_the_writer_call_as_it_was(self):
        for mode in ("single", "quotes"):
            kwargs, result, _ = self._run(mode)
            self.assertNotIn("voice_mode", kwargs, mode)
            self.assertNotIn("CO-HOST", kwargs["creative_brief"], mode)
            self.assertEqual(result.features["voice_mode"], mode)
            self.assertNotIn("speaker_turns", result.features)

    def test_chapter_voices_without_chapters_fall_back_to_one_voice(self):
        _kwargs, result, _ = self._run("chapters")
        self.assertEqual(result.features["voice_mode"], "single")


class RenderVoicesTests(unittest.TestCase):
    def test_dossier_audit_names_the_voices(self):
        from core.vault.dossiers import audit_lines

        text = "\n".join(
            audit_lines({"voice_mode": "debate", "voices": {"narrator": "vA", "cohost": "vB"}}, {})
        )
        self.assertIn("Voices (debate)", text)
        self.assertIn("cohost vB", text)

    def test_run_media_only_plans_voices_and_stores_what_was_used(self):
        from core import pipeline

        merged = {}
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.dict(os.environ, {"THUMBNAIL_MODE": "off", "CONTENT_RENDER_PROGRESS": "0"}),
                patch.object(pipeline, "update_content_run_media"),
                patch.object(pipeline, "record_render_assets"),
                patch("core.run_trace.update_trace"),
                patch.object(
                    pipeline,
                    "media_paths_for_topic",
                    return_value=(os.path.join(tmp, "a.mp3"), "a.mp4", os.path.join(tmp, "a.mp4")),
                ),
                patch("core.tts_char_cap.tts_char_cap_reason", return_value=""),
                patch.object(pipeline, "generate_audio") as audio,
                patch.object(pipeline, "render_vertical_video", return_value=(None, None)),
                patch(
                    "core.voice.plan.plan_for_run",
                    return_value=({"narrator": "voiceB", "cohost": "voiceC"}, ["seg"]),
                ),
                patch(
                    "core.tts.last_run_voices",
                    return_value={"narrator": "voiceB", "cohost": "voiceC"},
                ),
                patch(
                    "core.run_features.merge_features",
                    side_effect=lambda rid, upd: merged.setdefault(rid, {}).update(upd),
                ),
                patch("core.run_features.load_features", return_value={}),
            ):
                pipeline.run_media_only("topic", "script", channel_id="tapin", content_run_id=7)
        kwargs = audio.call_args.kwargs
        self.assertEqual(kwargs["voices"], {"narrator": "voiceB", "cohost": "voiceC"})
        self.assertEqual(kwargs["segments"], ["seg"])
        self.assertEqual(merged[7]["voices"], {"narrator": "voiceB", "cohost": "voiceC"})


class SpokenVoicesTests(GovernorCase):
    """`last_run_voices` is what actually spoke - never an id a local voice stood in for."""

    ENV: ClassVar[dict[str, str]] = {
        "TTS_PROVIDER": "elevenlabs",
        "TTS_PIPER_MIX_EVERY": "0",
        "ELEVEN_API_KEY": "k",
        "ELEVENLABS_MONTHLY_CHAR_BUDGET": "100000",
    }

    def test_an_elevenlabs_render_records_its_voice(self):
        from core import tts

        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "a.mp3")
            with (
                patch.dict(os.environ, self.ENV),
                patch("core.tts.get_channel_profile", return_value=_profile()),
                patch.object(tts, "ElevenLabs") as eleven,
                patch.object(tts, "_word_timestamps_enabled", return_value=False),
            ):
                eleven.return_value.text_to_speech.convert.return_value = [b"x"]
                tts.generate_audio(
                    "hello world", out, channel_id="tapin", voices={"narrator": "voiceB"}
                )
        self.assertEqual(
            eleven.return_value.text_to_speech.convert.call_args.kwargs["voice_id"], "voiceB"
        )
        self.assertEqual(tts.last_run_voices(), {"narrator": "voiceB"})

    def test_a_local_voice_render_records_no_elevenlabs_id(self):
        from core import tts

        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "a.mp3")
            with (
                patch.dict(os.environ, {**self.ENV, "TTS_PROVIDER": "piper"}),
                patch("core.tts.get_channel_profile", return_value=_profile()),
                patch.object(tts, "_try_alt_tts_provider", return_value=out),
            ):
                tts.generate_audio(
                    "hello world", out, channel_id="tapin", voices={"narrator": "voiceB"}
                )
        self.assertEqual(tts.last_run_voices(), {})

    def test_the_sentence_loop_resolves_each_role_once(self):
        from core import tts

        def fake_synth(spoken, alt, path, channel_id, key, *, allow_piper_mix=True):
            with open(path, "wb") as f:
                f.write(b"x")
            return path

        def fake_concat(paths, out):
            with open(out, "wb") as f:
                f.write(b"x")

        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "a.mp3")
            with (
                patch.object(tts, "_tts_cache_voice", return_value="v") as voice,
                patch.object(tts, "synthesize_to_path", side_effect=fake_synth),
                patch.object(tts, "concat_audio_segments", side_effect=fake_concat),
                patch.object(tts, "segment_audio_duration", return_value=1.0),
            ):
                sents = ["One.", "Two.", "Three."]
                tts._generate_by_sentences(sents, sents, out, "tapin", "k", lambda n: None)
        self.assertEqual(voice.call_count, 1, "a local voice pool rotates per call")


if __name__ == "__main__":
    unittest.main()
