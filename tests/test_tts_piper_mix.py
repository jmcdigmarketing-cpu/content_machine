"""Occasional Piper mix on Standard ElevenLabs renders (TTS_PIPER_MIX_EVERY)."""

from __future__ import annotations

import os
import random
import tempfile
import unittest
from unittest.mock import patch

from core import tts
from core.cost_meter import merge_render_cost


class TestShouldPiperMix(unittest.TestCase):
    def test_seeded_every_8_is_about_one_in_eight(self):
        rng = random.Random(0)
        env = {
            "TTS_PROVIDER": "elevenlabs",
            "FREE_MODE_STRICT": "",
            "TTS_PIPER_MIX_EVERY": "8",
        }
        with (
            patch.dict(os.environ, env, clear=False),
            patch.object(tts.random, "randrange", rng.randrange),
            patch("core.run_mode._tts_provider_ready", return_value=True),
        ):
            hits = sum(1 for _ in range(8000) if tts._should_piper_mix())
        self.assertGreater(hits, 800)
        self.assertLess(hits, 1200)

    def test_never_when_piper_not_ready(self):
        env = {
            "TTS_PROVIDER": "elevenlabs",
            "TTS_PIPER_MIX_EVERY": "1",
            "FREE_MODE_STRICT": "",
        }
        with (
            patch.dict(os.environ, env, clear=False),
            patch("core.run_mode._tts_provider_ready", return_value=False),
        ):
            self.assertFalse(tts._should_piper_mix())

    def test_never_when_provider_already_piper_or_edge(self):
        for provider in ("piper", "edge"):
            with (
                patch.dict(
                    os.environ,
                    {
                        "TTS_PROVIDER": provider,
                        "TTS_PIPER_MIX_EVERY": "1",
                        "FREE_MODE_STRICT": "",
                    },
                    clear=False,
                ),
                patch("core.run_mode._tts_provider_ready", return_value=True),
            ):
                self.assertFalse(tts._should_piper_mix(), provider)

    def test_never_when_every_is_zero(self):
        with (
            patch.dict(
                os.environ,
                {
                    "TTS_PROVIDER": "elevenlabs",
                    "TTS_PIPER_MIX_EVERY": "0",
                    "FREE_MODE_STRICT": "",
                },
                clear=False,
            ),
            patch("core.run_mode._tts_provider_ready", return_value=True),
        ):
            self.assertFalse(tts._should_piper_mix())


class TestGenerateAudioPiperMix(unittest.TestCase):
    def test_mix_uses_piper_not_elevenlabs(self):
        env = {
            "TTS_PROVIDER": "elevenlabs",
            "TTS_PIPER_MIX_EVERY": "1",
            "FREE_MODE_STRICT": "",
            "ELEVEN_API_KEY": "k",
            "ELEVENLABS_MONTHLY_CHAR_BUDGET": "",
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "a.mp3")
            with (
                patch.dict(os.environ, env, clear=False),
                patch("core.run_mode._tts_provider_ready", return_value=True),
                patch.object(tts, "_piper_synth", return_value=out) as piper,
                patch.object(tts, "ElevenLabs") as eleven,
            ):
                result = tts.generate_audio("hello world", out, channel_id="tapin")
        piper.assert_called_once()
        eleven.assert_not_called()
        self.assertEqual(result, out)
        self.assertTrue(tts.last_tts_was_piper_mix())
        self.assertFalse(tts.last_tts_was_cache_hit())

    def test_mix_synth_none_falls_open_to_elevenlabs(self):
        env = {
            "TTS_PROVIDER": "elevenlabs",
            "TTS_PIPER_MIX_EVERY": "1",
            "FREE_MODE_STRICT": "",
            "ELEVEN_API_KEY": "k",
            "ELEVENLABS_MONTHLY_CHAR_BUDGET": "",
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "a.mp3")
            with (
                patch.dict(os.environ, env, clear=False),
                patch("core.run_mode._tts_provider_ready", return_value=True),
                patch.object(tts, "_piper_synth", return_value=None),
                patch.object(tts, "ElevenLabs") as eleven,
                patch.object(tts, "_word_timestamps_enabled", return_value=False),
                patch.object(tts, "resolve_tts_config", return_value=("v", "m")),
            ):
                eleven.return_value.text_to_speech.convert.return_value = [b"x"]
                tts.generate_audio("hello world", out, channel_id="tapin")
                eleven.assert_called_once()
                self.assertFalse(tts.last_tts_was_piper_mix())
                self.assertTrue(os.path.isfile(out))

    def test_mix_render_meters_zero_tts(self):
        env = {
            "TTS_PROVIDER": "elevenlabs",
            "TTS_PIPER_MIX_EVERY": "1",
            "FREE_MODE_STRICT": "",
            "ELEVEN_API_KEY": "k",
            "ELEVENLABS_MONTHLY_CHAR_BUDGET": "",
        }
        script = "x" * 1000
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "a.mp3")
            with (
                patch.dict(os.environ, env, clear=False),
                patch("core.run_mode._tts_provider_ready", return_value=True),
                patch.object(tts, "_piper_synth", return_value=out),
                patch.object(tts, "ElevenLabs") as eleven,
            ):
                tts.generate_audio(script, out, channel_id="tapin")
                eleven.assert_not_called()
                billed = merge_render_cost({}, script, tts_cached=False)
                mixed = merge_render_cost({}, script, tts_cached=tts.last_tts_was_piper_mix())
        self.assertGreater(billed["tts"], 0.0)
        self.assertTrue(tts.last_tts_was_piper_mix())
        self.assertEqual(mixed["tts"], 0.0)


if __name__ == "__main__":
    unittest.main()
