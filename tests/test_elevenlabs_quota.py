"""ElevenLabs character-quota governor — isolated store, no real data/ writes."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from core import quota_governor as qg
from core import quota_state, tts
from core.utils import clean_script_for_tts


class GovernorCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._state_patch = patch.object(
            quota_state, "QUOTA_STATE_FILE", os.path.join(self._tmp.name, "q.json")
        )
        self._state_patch.start()

    def tearDown(self):
        self._state_patch.stop()
        self._tmp.cleanup()


class TestElevenLabsGovernor(GovernorCase):
    def test_add_and_would_exceed(self):
        qg.elevenlabs_add_chars(100)
        self.assertEqual(qg.elevenlabs_chars_used(), 100)
        self.assertFalse(qg.elevenlabs_would_exceed(10, 200))
        self.assertTrue(qg.elevenlabs_would_exceed(101, 200))
        self.assertTrue(qg.elevenlabs_would_exceed(1, 100))

    def test_zero_budget_never_exceeds(self):
        self.assertFalse(qg.elevenlabs_would_exceed(999, 0))

    def test_reset_clears_counter(self):
        qg.elevenlabs_add_chars(50)
        qg.elevenlabs_reset()
        self.assertEqual(qg.elevenlabs_chars_used(), 0)

    def test_non_positive_add_is_noop(self):
        qg.elevenlabs_add_chars(0)
        qg.elevenlabs_add_chars(-5)
        self.assertEqual(qg.elevenlabs_chars_used(), 0)


class TestElevenLabsTtsTrip(GovernorCase):
    def test_trips_to_piper_before_elevenlabs(self):
        qg.elevenlabs_add_chars(100)
        env = {
            "ELEVENLABS_MONTHLY_CHAR_BUDGET": "100",
            "TTS_PROVIDER": "elevenlabs",
            "TTS_PIPER_MIX_EVERY": "0",
            "ELEVEN_API_KEY": "k",
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "a.mp3")
            with (
                patch.dict(os.environ, env, clear=False),
                patch.object(tts, "_piper_voice_ready", return_value=True),
                patch.object(tts, "_piper_synth", return_value=out) as piper,
                patch.object(tts, "ElevenLabs") as eleven,
            ):
                result = tts.generate_audio("hello world", out)
        piper.assert_called_once()
        eleven.assert_not_called()
        self.assertEqual(result, out)

    def test_blocks_when_piper_unavailable(self):
        qg.elevenlabs_add_chars(5)
        env = {
            "ELEVENLABS_MONTHLY_CHAR_BUDGET": "5",
            "TTS_PROVIDER": "elevenlabs",
            "TTS_PIPER_MIX_EVERY": "0",
            "ELEVEN_API_KEY": "k",
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "a.mp3")
            with (
                patch.dict(os.environ, env, clear=False),
                patch.object(tts, "_piper_voice_ready", return_value=False),
                patch.object(tts, "ElevenLabs") as eleven,
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    tts.generate_audio("hello world", out)
        eleven.assert_not_called()
        self.assertIn("character budget", str(ctx.exception).lower())

    def test_records_chars_once_on_success(self):
        script = "abcd"
        env = {
            "ELEVENLABS_MONTHLY_CHAR_BUDGET": "100000",
            "TTS_PROVIDER": "elevenlabs",
            "TTS_PIPER_MIX_EVERY": "0",
            "ELEVEN_API_KEY": "k",
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "a.mp3")
            with (
                patch.dict(os.environ, env, clear=False),
                patch.object(tts, "ElevenLabs") as eleven,
                patch.object(tts, "_word_timestamps_enabled", return_value=False),
                patch.object(tts, "resolve_tts_config", return_value=("v", "m")),
            ):
                eleven.return_value.text_to_speech.convert.return_value = [b"x"]
                tts.generate_audio(script, out)
        self.assertEqual(qg.elevenlabs_chars_used(), len(clean_script_for_tts(script)))

    def test_unset_budget_does_not_persist(self):
        env = {
            "ELEVENLABS_MONTHLY_CHAR_BUDGET": "",
            "TTS_PROVIDER": "elevenlabs",
            "TTS_PIPER_MIX_EVERY": "0",
            "ELEVEN_API_KEY": "k",
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "a.mp3")
            with (
                patch.dict(os.environ, env, clear=False),
                patch.object(tts, "ElevenLabs") as eleven,
                patch.object(tts, "_word_timestamps_enabled", return_value=False),
                patch.object(tts, "resolve_tts_config", return_value=("v", "m")),
            ):
                eleven.return_value.text_to_speech.convert.return_value = [b"x"]
                tts.generate_audio("hello world", out)
        self.assertEqual(qg.elevenlabs_chars_used(), 0)


if __name__ == "__main__":
    unittest.main()
