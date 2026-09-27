"""#890: the voice speaks a touch slower (operator, 2026-09-27).

No ElevenLabs call set a speed: `convert` and `convert_with_timestamps` were sent a voice,
a model and the text, so every render used the voice's default pace. The speed is now
0.95 unless the channel or `TTS_SPEED` says otherwise. The voice's own saved settings
(stability, similarity) are read once and kept - only the speed changes. Local voices
get the same factor, and the cache key carries it, so a 1.0x clip is never reused.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_quota_governor import GovernorCase


def _profile(speed=None):
    return SimpleNamespace(
        tts_model_id="m1",
        tts_voice_id="voiceA",
        tts_voice_pool=None,
        tts_rotate=False,
        tts_speed=speed,
        local_tts_voices=None,
        local_tts_voice=None,
    )


class SpeechSpeedTests(unittest.TestCase):
    def _speed(self, env=None, profile_speed=None):
        from core.tts import speech_speed

        environ = {k: v for k, v in os.environ.items() if k != "TTS_SPEED"}
        environ.update(env or {})
        with (
            patch.dict(os.environ, environ, clear=True),
            patch("core.tts.get_channel_profile", return_value=_profile(profile_speed)),
        ):
            return speech_speed("tapin")

    def test_default_is_a_touch_slower(self):
        self.assertEqual(self._speed(), 0.95)

    def test_the_channel_setting_wins_over_the_default(self):
        self.assertEqual(self._speed(profile_speed=0.9), 0.9)

    def test_the_env_wins_over_the_channel(self):
        self.assertEqual(self._speed(env={"TTS_SPEED": "1.0"}, profile_speed=0.9), 1.0)

    def test_values_are_clamped_and_junk_is_ignored(self):
        self.assertEqual(self._speed(env={"TTS_SPEED": "3"}), 1.2)
        self.assertEqual(self._speed(env={"TTS_SPEED": "0.1"}), 0.7)
        self.assertEqual(self._speed(env={"TTS_SPEED": "fast"}), 0.95)

    def test_the_real_channels_parse_a_speed_field(self):
        from config.channels import get_channel_profile

        self.assertTrue(hasattr(get_channel_profile("tapin"), "tts_speed"))


class ElevenLabsSpeedTests(GovernorCase):
    ENV = {  # noqa: RUF012 - read-only
        "TTS_PROVIDER": "elevenlabs",
        "TTS_PIPER_MIX_EVERY": "0",
        "ELEVEN_API_KEY": "k",
        "ELEVENLABS_MONTHLY_CHAR_BUDGET": "100000",
    }

    def _render(self, *, timestamps=False, settings_error=None, env=None):
        from elevenlabs import VoiceSettings

        from core import tts

        tts._saved_voice_settings.clear()
        environ = {k: v for k, v in os.environ.items() if k != "TTS_SPEED"}
        environ.update({**self.ENV, **(env or {})})
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "a.mp3")
            with (
                patch.dict(os.environ, environ, clear=True),
                patch("core.tts.get_channel_profile", return_value=_profile()),
                patch.object(tts, "ElevenLabs") as eleven,
                patch.object(tts, "_word_timestamps_enabled", return_value=timestamps),
            ):
                client = eleven.return_value
                if settings_error:
                    client.voices.settings.get.side_effect = settings_error
                else:
                    client.voices.settings.get.return_value = VoiceSettings(
                        stability=0.3, similarity_boost=0.8
                    )
                client.text_to_speech.convert.return_value = [b"x"]
                client.text_to_speech.convert_with_timestamps.side_effect = RuntimeError("no ts")
                tts.generate_audio("hello world", out, channel_id="tapin")
        return client

    def test_convert_gets_the_speed_and_keeps_the_saved_settings(self):
        client = self._render()
        settings = client.text_to_speech.convert.call_args.kwargs["voice_settings"]
        self.assertEqual(settings.speed, 0.95)
        self.assertEqual(settings.stability, 0.3)
        self.assertEqual(settings.similarity_boost, 0.8)

    def test_the_timestamp_call_gets_it_too(self):
        client = self._render(timestamps=True)
        settings = client.text_to_speech.convert_with_timestamps.call_args.kwargs["voice_settings"]
        self.assertEqual(settings.speed, 0.95)

    def test_an_unreadable_saved_setting_sends_the_speed_alone(self):
        client = self._render(settings_error=RuntimeError("403"))
        settings = client.text_to_speech.convert.call_args.kwargs["voice_settings"]
        self.assertEqual(settings.speed, 0.95)
        self.assertIsNone(settings.stability)

    def test_speed_one_sends_today_s_call(self):
        client = self._render(env={"TTS_SPEED": "1.0"})
        self.assertNotIn("voice_settings", client.text_to_speech.convert.call_args.kwargs)


class LocalAndCacheTests(unittest.TestCase):
    def test_local_voices_get_the_same_factor(self):
        from core import tts

        with (
            patch.dict(os.environ, {"TTS_VOICE_VARIETY": ""}),
            patch("core.tts.get_channel_profile", return_value=_profile()),
        ):
            self.assertEqual(tts._local_speed_factor("tapin", seed="x"), 0.95)

    def test_the_cache_key_changes_with_the_speed(self):
        from core import tts

        keys = []
        for speed in ("1.0", "0.95"):
            with (
                patch.dict(os.environ, {"TTS_PROVIDER": "elevenlabs", "TTS_SPEED": speed}),
                patch("core.tts.get_channel_profile", return_value=_profile()),
                tts.voice_context({"narrator": "voiceA"}),
            ):
                keys.append(tts._tts_cache_voice("tapin"))
        self.assertEqual(keys[0], "voiceA")
        self.assertNotEqual(keys[0], keys[1])


if __name__ == "__main__":
    unittest.main()
