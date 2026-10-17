"""#1235 tag a clip already in the library. #499 trim a one-shot voice file.
#1046 caption highlight and margin from the skin. #1056 the hook on screen
for the first second. #1039 the hook request is a touch faster.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

CHARGERS = "How the 0-4 chargers can turn it around this year"
DRAFT = "NFL draft night shock trade"
HOOK = "The Chargers can turn it around."


def _index(path: str, clips: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"clips": clips}, handle)


def _ass_bgr(hex_color: str) -> str:
    raw = hex_color.lstrip("#")
    return f"&H00{raw[4:6]}{raw[2:4]}{raw[0:2]}&".upper()


class TagClipTests(unittest.TestCase):
    def test_a_chargers_topic_uses_the_tagged_gameclip(self):
        from assets.clip_tags import clips_for_topic, tag_clip

        with tempfile.TemporaryDirectory() as tmp:
            clip = os.path.join(tmp, "GameClip.mp4")
            other = os.path.join(tmp, "clip0.mp4")
            index = os.path.join(tmp, "index.json")
            _index(index, {clip: {"teams": []}, other: {"teams": []}})
            before = {"clips": {clip: {"teams": []}, other: {"teams": []}}}
            self.assertEqual(clips_for_topic([clip, other], CHARGERS, before), [clip, other])
            tagged = tag_clip(clip, "chargers", index_path=index, apply=True)
            self.assertTrue(tagged["ok"], tagged)
            self.assertEqual(tagged["team"], "Los Angeles Chargers")
            saved = json.loads(Path(index).read_text(encoding="utf-8"))
            self.assertEqual(
                clips_for_topic([clip, other], CHARGERS, saved),
                [clip],
            )

    def test_a_topic_with_no_team_keeps_the_folder(self):
        from assets.clip_tags import clips_for_topic

        paths = ["/lib/GameClip.mp4", "/lib/clip0.mp4"]
        self.assertEqual(clips_for_topic(paths, DRAFT, {"clips": {}}), paths)

    def test_a_missing_clip_is_not_added(self):
        from assets.clip_tags import tag_clip

        with tempfile.TemporaryDirectory() as tmp:
            index = os.path.join(tmp, "index.json")
            _index(index, {})
            result = tag_clip(
                os.path.join(tmp, "GameClip.mp4"),
                "chargers",
                index_path=index,
                apply=True,
            )
            self.assertFalse(result["ok"])
            saved = json.loads(Path(index).read_text(encoding="utf-8"))
            self.assertEqual(saved["clips"], {})

    def test_dry_run_does_not_write(self):
        from assets.clip_tags import tag_clip

        with tempfile.TemporaryDirectory() as tmp:
            clip = os.path.join(tmp, "GameClip.mp4")
            index = os.path.join(tmp, "index.json")
            _index(index, {clip: {"teams": []}})
            before = Path(index).read_text(encoding="utf-8")
            result = tag_clip(clip, "chargers", index_path=index, apply=False)
            self.assertTrue(result["ok"], result)
            self.assertEqual(Path(index).read_text(encoding="utf-8"), before)

    def test_the_command_refuses_a_path_that_is_not_indexed(self):
        from scripts.ops import main

        with tempfile.TemporaryDirectory() as tmp:
            index = os.path.join(tmp, "index.json")
            _index(index, {})
            missing = os.path.join(tmp, "GameClip.mp4")
            with patch("config.paths.CLIP_INDEX_FILE", index):
                code = main(["footage-tag", "--path", missing, "--team", "chargers", "--apply"])
            saved = json.loads(Path(index).read_text(encoding="utf-8"))
            self.assertEqual(code, 1)
            self.assertEqual(saved["clips"], {})


class SingleCallTrimTests(unittest.TestCase):
    def test_a_one_shot_file_loses_its_leading_silence(self):
        from core import tts

        def fake_words(*_args, **_kwargs):
            path = _args[4]
            with open(path, "wb") as handle:
                handle.write(b"silent-head")
            with open(path + ".words.json", "w", encoding="utf-8") as handle:
                json.dump([{"word": "Go", "start": 0.4, "end": 0.9}], handle)
            return True

        def fake_run(cmd, **_kwargs):
            cmd = [str(part) for part in cmd]
            proc = SimpleNamespace(returncode=0, stdout="1.2\n", stderr="")
            if any("silencedetect" in part for part in cmd):
                proc.stderr = "silence_start: 0\nsilence_end: 0.4\n"
            if any("ffprobe" in part for part in cmd):
                proc.stdout = "1.2\n"
            if "-filter_complex" in cmd:
                with open(cmd[-1], "wb") as handle:
                    handle.write(b"trimmed")
            return proc

        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "out.mp3")
            env = {
                "TTS_CACHE": "true",
                "TTS_CACHE_DIR": os.path.join(tmp, "cache"),
                "TTS_PROVIDER": "elevenlabs",
                "ELEVEN_API_KEY": "k",
                "FREE_MODE_STRICT": "",
            }
            with (
                patch.dict(os.environ, env, clear=False),
                patch.object(tts, "_try_alt_tts_provider", return_value=None),
                patch.object(tts, "_should_piper_mix", return_value=False),
                patch.object(tts, "_elevenlabs_quota_would_exceed", return_value=False),
                patch.object(tts, "_word_timestamps_enabled", return_value=True),
                patch.object(tts, "_save_word_timestamps", side_effect=fake_words),
                patch.object(tts, "resolve_tts_config", return_value=("vid", "mid")),
                patch.object(tts, "_elevenlabs_record_chars"),
                patch.object(tts, "ElevenLabs", return_value=MagicMock()),
                patch("core.voice.dead_air.subprocess.run", side_effect=fake_run),
                patch("core.voice.dead_air.shutil.which", return_value="ffmpeg"),
            ):
                tts.synthesize_to_path(
                    "Go.",
                    "Go.",
                    dest,
                    "tapin",
                    tts.tts_cache_key("Go.", "elevenlabs", "vid"),
                )
            words = json.loads(Path(dest + ".words.json").read_text(encoding="utf-8"))
            self.assertEqual(words[0]["start"], 0.0)

    def test_a_cache_hit_is_not_trimmed_again(self):
        from core import tts
        from core.voice.dead_air import trim_dead_air

        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "src.mp3")
            with open(src, "wb") as handle:
                handle.write(b"cached")
            dest = os.path.join(tmp, "out.mp3")
            env = {
                "TTS_CACHE": "true",
                "TTS_CACHE_DIR": tmp,
                "TTS_PROVIDER": "elevenlabs",
            }
            key = tts.tts_cache_key("hello world", "elevenlabs", "")
            with patch.dict(os.environ, env, clear=False):
                tts.tts_cache_store(key, src)
                with (
                    patch.object(tts, "_tts_cache_voice", return_value=""),
                    patch("core.tts.trim_dead_air", wraps=trim_dead_air) as trim,
                ):
                    tts.generate_audio("hello world", dest)
            trim.assert_not_called()


class CaptionSkinTests(unittest.TestCase):
    def _captions(self, channel: str, skin: dict, script: str = HOOK) -> str:
        from video.subtitles import generate_subtitle_file

        words = [
            {"word": "The", "start": 0.0, "end": 0.2},
            {"word": "Chargers", "start": 0.2, "end": 0.5},
            {"word": "can", "start": 0.5, "end": 0.8},
            {"word": "turn", "start": 0.8, "end": 1.1},
            {"word": "it", "start": 1.1, "end": 1.3},
            {"word": "around", "start": 1.3, "end": 1.6},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "captions.ass")
            env = {k: v for k, v in os.environ.items() if k != "CAPTION_STYLE"}
            with (
                patch.dict(os.environ, env, clear=True),
                patch("video.subtitles._caption_skin", return_value=skin),
            ):
                path = generate_subtitle_file(
                    script,
                    4.0,
                    channel_id=channel,
                    output_path=dest,
                    words=words,
                )
            return Path(path).read_text(encoding="utf-8")

    def test_tapin_karaoke_uses_the_brand_highlight(self):
        from config.channels import get_channel_profile

        skin = dict(get_channel_profile("tapin").caption_skin or {})
        text = self._captions("tapin", skin)
        colour = _ass_bgr("#E53935")
        style = next(line for line in text.splitlines() if line.startswith("Style:"))
        self.assertIn(colour, style)
        self.assertNotIn("&H0000FFFF", style.upper().replace(colour.upper(), ""))

    def test_a_skin_margin_is_written(self):
        skin = {
            "mode": "karaoke",
            "font": "Arial",
            "title_font": "Impact",
            "body_font": "Arial",
            "margin_v": 90,
        }
        text = self._captions("tapin", skin)
        style = next(line for line in text.splitlines() if line.startswith("Style: Title,"))
        self.assertIn(",90,1", style)

    def test_a_skin_without_those_fields_keeps_yellow_and_the_word_margin(self):
        from video.subtitles import caption_force_style

        text = self._captions("tapin", {"mode": "karaoke", "font": "Arial"})
        style = next(line for line in text.splitlines() if line.startswith("Style:"))
        self.assertIn("&H0000FFFF,", style)
        self.assertIn(",260,1", style)
        with patch("video.subtitles._caption_skin", return_value={"font": "Arial"}):
            forced = caption_force_style("tapin")
        self.assertIn("MarginV=72", forced)


class HookCardTests(unittest.TestCase):
    def _file(self, channel: str, skin: dict) -> str:
        from video.subtitles import generate_subtitle_file

        words = [
            {"word": "The", "start": 0.0, "end": 0.2},
            {"word": "Chargers", "start": 0.2, "end": 0.5},
            {"word": "can", "start": 0.5, "end": 0.8},
            {"word": "turn", "start": 0.8, "end": 1.2},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "captions.ass")
            env = {k: v for k, v in os.environ.items() if k != "CAPTION_STYLE"}
            with (
                patch.dict(os.environ, env, clear=True),
                patch("video.subtitles._caption_skin", return_value=skin),
            ):
                path = generate_subtitle_file(
                    HOOK,
                    4.0,
                    channel_id=channel,
                    output_path=dest,
                    words=words,
                )
            return Path(path).read_text(encoding="utf-8")

    def test_tapin_shows_the_hook_for_the_first_second(self):
        from config.channels import get_channel_profile

        skin = dict(get_channel_profile("tapin").caption_skin or {})
        text = self._file("tapin", skin)
        card = next(
            line for line in text.splitlines() if line.startswith("Dialogue:") and HOOK in line
        )
        _layer, start, end, *_rest = card.split(",", 9)
        self.assertEqual(start, "0:00:00.00")
        self.assertEqual(end, "0:00:01.00")
        self.assertIn(",Hook,", card)

    def test_the_card_is_absent_when_the_flag_is_off(self):
        skin = {
            "mode": "karaoke",
            "font": "Arial",
            "title_font": "Impact",
            "body_font": "Arial",
            "hook_card": False,
        }
        text = self._file("tapin", skin)
        self.assertFalse(
            any(HOOK in line and line.startswith("Dialogue:") for line in text.splitlines())
        )

    def test_moneywise_has_no_card(self):
        from config.channels import get_channel_profile

        skin = dict(get_channel_profile("moneywise").caption_skin or {})
        text = self._file("moneywise", skin)
        self.assertNotIn("0:00:00.00,0:00:01.00,Hook", text)


class DeliveryTests(unittest.TestCase):
    def test_the_hook_request_is_faster_and_the_next_sentence_is_not(self):
        from core import tts

        script = "*Turn* the season around.\n\nThe next drive starts here."
        client = MagicMock()
        client.text_to_speech.convert.return_value = [b"mp3"]
        client.voices.settings.get.return_value = SimpleNamespace(
            model_dump=lambda: {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0}
        )

        def fake_concat(paths, dest):
            with open(dest, "wb") as handle:
                handle.write(b"joined")
            return dest

        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "out.mp3")
            env = {
                "TTS_CACHE": "true",
                "TTS_CACHE_DIR": os.path.join(tmp, "cache"),
                "TTS_PROVIDER": "elevenlabs",
                "ELEVEN_API_KEY": "k",
                "TTS_SPEED": "",
                "FREE_MODE_STRICT": "",
            }
            with (
                patch.dict(os.environ, env, clear=False),
                patch.object(tts, "ElevenLabs", return_value=client),
                patch.object(tts, "_word_timestamps_enabled", return_value=False),
                patch.object(tts, "_should_piper_mix", return_value=False),
                patch.object(tts, "_elevenlabs_quota_would_exceed", return_value=False),
                patch.object(tts, "resolve_tts_config", return_value=("vid", "mid")),
                patch.object(tts, "_elevenlabs_record_chars"),
                patch.object(tts, "_tts_cache_voice", return_value="vid"),
                patch.object(tts, "ffmpeg_concat_ready", return_value=True),
                patch.object(tts, "concat_audio_segments", side_effect=fake_concat),
                patch.object(tts, "speech_speed", return_value=1.05),
                patch.object(tts, "_try_alt_tts_provider", return_value=None),
            ):
                tts.generate_audio(script, dest, channel_id="tapin")

        calls = client.text_to_speech.convert.call_args_list
        self.assertEqual(len(calls), 2)
        first = calls[0].kwargs
        second = calls[1].kwargs
        self.assertEqual(first["text"], "Turn the season around.")
        self.assertEqual(first["voice_settings"].speed, 1.10)
        self.assertEqual(first["voice_settings"].style, 0.35)
        self.assertEqual(second["text"], "The next drive starts here.")
        self.assertEqual(second["voice_settings"].speed, 1.05)
        self.assertNotIn("*", first["text"])

    def test_an_ellipsis_is_not_spoken_and_the_next_word_waits(self):
        from core import tts

        client = MagicMock()
        client.text_to_speech.convert.return_value = [b"mp3"]
        client.voices.settings.get.return_value = SimpleNamespace(
            model_dump=lambda: {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0}
        )

        def fake_concat(paths, dest):
            with open(paths[0] + ".words.json", "w", encoding="utf-8") as handle:
                json.dump([{"word": "Wait", "start": 0.0, "end": 0.4}], handle)
            with open(paths[1] + ".words.json", "w", encoding="utf-8") as handle:
                json.dump([{"word": "go", "start": 0.0, "end": 0.3}], handle)
            with open(dest, "wb") as handle:
                handle.write(b"joined")
            return dest

        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "out.mp3")
            env = {
                "TTS_CACHE": "true",
                "TTS_CACHE_DIR": os.path.join(tmp, "cache"),
                "TTS_PROVIDER": "elevenlabs",
                "ELEVEN_API_KEY": "k",
                "TTS_SPEED": "",
                "FREE_MODE_STRICT": "",
            }
            with (
                patch.dict(os.environ, env, clear=False),
                patch.object(tts, "ElevenLabs", return_value=client),
                patch.object(tts, "_word_timestamps_enabled", return_value=False),
                patch.object(tts, "_should_piper_mix", return_value=False),
                patch.object(tts, "_elevenlabs_quota_would_exceed", return_value=False),
                patch.object(tts, "resolve_tts_config", return_value=("vid", "mid")),
                patch.object(tts, "_elevenlabs_record_chars"),
                patch.object(tts, "_tts_cache_voice", return_value="vid"),
                patch.object(tts, "ffmpeg_concat_ready", return_value=True),
                patch.object(tts, "concat_audio_segments", side_effect=fake_concat),
                patch.object(tts, "speech_speed", return_value=1.05),
                patch.object(tts, "_try_alt_tts_provider", return_value=None),
            ):
                tts.generate_audio("Wait...\n\nGo now.", dest, channel_id="tapin")
            words = json.loads(Path(dest + ".words.json").read_text(encoding="utf-8"))
        self.assertNotIn("...", client.text_to_speech.convert.call_args_list[0].kwargs["text"])
        self.assertEqual(words[1]["word"], "go")
        self.assertEqual(words[1]["start"], 0.7)

    def test_the_hook_cache_key_is_not_the_unpaced_paragraph(self):
        from core import tts
        from core.voice.delivery import delivery_for

        delivered = delivery_for("*Turn* it.", hook=True, speed=1.05)
        paced = tts.tts_cache_key(
            tts.paragraph_cache_text(delivered["text"], "", "Next.")
            + f"\npace={delivered['speed']}",
            "elevenlabs",
            "vid",
        )
        plain = tts.tts_cache_key(
            tts.paragraph_cache_text("*Turn* it.", "", "Next."),
            "elevenlabs",
            "vid",
        )
        seen: list[str] = []

        def fake_lookup(key, _dest):
            seen.append(key)
            return False

        def fake_seam(*_args, **_kwargs):
            path = _args[2]
            with open(path, "wb") as handle:
                handle.write(b"mp3")
            return path

        def fake_concat(paths, dest):
            with open(dest, "wb") as handle:
                handle.write(b"joined")
            return dest

        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "out.mp3")
            env = {
                "TTS_CACHE": "true",
                "TTS_CACHE_DIR": os.path.join(tmp, "cache"),
                "TTS_PROVIDER": "elevenlabs",
            }
            with (
                patch.dict(os.environ, env, clear=False),
                patch.object(tts, "tts_cache_lookup", side_effect=fake_lookup),
                patch.object(tts, "synthesize_to_path", side_effect=fake_seam),
                patch.object(tts, "ffmpeg_concat_ready", return_value=True),
                patch.object(tts, "concat_audio_segments", side_effect=fake_concat),
                patch.object(tts, "segment_audio_duration", return_value=1.0),
                patch.object(tts, "_tts_cache_voice", return_value="vid"),
                patch.object(tts, "speech_speed", return_value=1.05),
            ):
                tts.generate_audio("*Turn* it.\n\nNext.", dest, channel_id="tapin")
        self.assertIn(paced, seen)
        self.assertNotIn(plain, seen)

    def test_the_script_prompt_asks_for_the_marks(self):
        from core.content_engine import _build_prompts

        _system, user = _build_prompts(
            topic="Chargers",
            signals={},
            min_words=80,
            max_words=140,
            today="2026-10-16",
            channel_id="tapin",
            script_brief="",
            seo_block="",
            signal_facts="",
            signal_summary="",
            brief_block="",
            length_choice="short",
        )
        self.assertIn("asterisks", user)
        self.assertIn("ellipsis", user)
