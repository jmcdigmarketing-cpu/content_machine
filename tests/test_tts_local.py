"""Local TTS provider chain (Pillar 6 #1) — render-ready mp3 contract + fail-open.

The render pipeline ignores generate_audio's return and reads `mp3_path` directly, so a
local provider MUST leave a real mp3 at the requested output_path. These tests lock that
contract without any heavy backend installed: the synth + ffmpeg are mocked.
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from core import tts


class TestIsLocalProvider(unittest.TestCase):
    def test_truth_table(self):
        for provider, expected in (
            ("kokoro", True),
            ("xtts", True),
            ("piper", True),
            ("PIPER", True),  # case-insensitive
            ("elevenlabs", False),
            ("", False),
        ):
            with patch.dict(os.environ, {"TTS_PROVIDER": provider}, clear=False):
                self.assertEqual(tts.is_local_tts_provider(), expected, provider)
        os.environ.pop("TTS_PROVIDER", None)
        self.assertFalse(tts.is_local_tts_provider())  # unset ⇒ elevenlabs


class TestTranscodeToMp3(unittest.TestCase):
    def test_success_returns_mp3_and_removes_wav(self):
        with tempfile.TemporaryDirectory() as tmp:
            wav = os.path.join(tmp, "a.tmp.wav")
            mp3 = os.path.join(tmp, "a.mp3")
            open(wav, "wb").close()

            def _fake_run(cmd, **kw):
                open(mp3, "wb").close()  # ffmpeg "creates" the mp3
                return MagicMock(returncode=0, stderr="")

            with patch("subprocess.run", side_effect=_fake_run):
                self.assertEqual(tts._transcode_to_mp3(wav, mp3), mp3)
            self.assertFalse(os.path.exists(wav))  # temp wav cleaned up
            self.assertTrue(os.path.exists(mp3))

    def test_nonzero_exit_fails_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            wav = os.path.join(tmp, "a.tmp.wav")
            mp3 = os.path.join(tmp, "a.mp3")
            open(wav, "wb").close()
            with patch("subprocess.run", return_value=MagicMock(returncode=1, stderr="boom")):
                self.assertIsNone(tts._transcode_to_mp3(wav, mp3))

    def test_missing_output_fails_open(self):
        # rc=0 but no file produced (bad codec build) must still fail open.
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stderr="")):
            self.assertIsNone(tts._transcode_to_mp3("x.tmp.wav", "definitely/missing/a.mp3"))

    def test_ffmpeg_not_launchable_fails_open(self):
        with patch("subprocess.run", side_effect=FileNotFoundError("no ffmpeg")):
            self.assertIsNone(tts._transcode_to_mp3("x.tmp.wav", "a.mp3"))


class TestAltProviderChain(unittest.TestCase):
    def test_local_provider_returns_the_mp3_path(self):
        # Regression: the chain must hand back the mp3 the pipeline reads — never a .wav.
        def _fake_synth(script, output_path, channel_id):
            open(output_path, "wb").close()
            return output_path

        with tempfile.TemporaryDirectory() as tmp:
            mp3 = os.path.join(tmp, "out.mp3")
            with (
                patch.dict(os.environ, {"TTS_PROVIDER": "piper"}, clear=False),
                patch.dict(tts._ALT_TTS, {"piper": _fake_synth}),
            ):
                result = tts._try_alt_tts_provider("hello world", mp3, "tapin")
        self.assertEqual(result, mp3)
        self.assertTrue(result.endswith(".mp3"))

    def test_provider_failure_falls_back_to_none(self):
        def _boom(script, output_path, channel_id):
            raise RuntimeError("model missing")

        with (
            patch.dict(os.environ, {"TTS_PROVIDER": "piper"}, clear=False),
            patch.dict(tts._ALT_TTS, {"piper": _boom}),
        ):
            self.assertIsNone(tts._try_alt_tts_provider("hi", "out.mp3", "tapin"))

    def test_piper_without_voice_model_returns_none(self):
        # PIPER_VOICE unset ⇒ None (ElevenLabs fallback), even if piper is importable.
        with patch.dict(os.environ, {"TTS_PROVIDER": "piper", "PIPER_VOICE": ""}, clear=False):
            self.assertIsNone(tts._try_alt_tts_provider("hi", "out.mp3", "tapin"))

    def test_unset_provider_is_noop(self):
        os.environ.pop("TTS_PROVIDER", None)
        self.assertIsNone(tts._try_alt_tts_provider("hi", "out.mp3", "tapin"))


if __name__ == "__main__":
    unittest.main()
