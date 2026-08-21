"""TTS cache by script hash — temp dir only, never data/tts_cache."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from core import tts


class TestTtsCache(unittest.TestCase):
    def test_key_stable_and_voice_sensitive(self):
        a = tts.tts_cache_key("hello", "piper", "lessac")
        b = tts.tts_cache_key("hello", "piper", "lessac")
        c = tts.tts_cache_key("hello", "piper", "other")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertEqual(len(a), 64)

    def test_roundtrip_copy_and_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"TTS_CACHE": "true", "TTS_CACHE_DIR": tmp}
            src = os.path.join(tmp, "src.mp3")
            with open(src, "wb") as f:
                f.write(b"mp3-bytes")
            with open(src + ".words.json", "w", encoding="utf-8") as f:
                f.write("[]")
            key = tts.tts_cache_key("script", "elevenlabs", "v1")
            dest = os.path.join(tmp, "out", "voice.mp3")
            with patch.dict(os.environ, env, clear=False):
                tts.tts_cache_store(key, src)
                hit = tts.tts_cache_lookup(key, dest)
            self.assertTrue(hit)
            self.assertTrue(os.path.isfile(dest))
            with open(dest, "rb") as f:
                self.assertEqual(f.read(), b"mp3-bytes")
            self.assertTrue(os.path.isfile(dest + ".words.json"))

    def test_cache_hit_flags_meter_zero(self):
        self.assertFalse(tts.last_tts_was_cache_hit())
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "TTS_CACHE": "true",
                "TTS_CACHE_DIR": tmp,
                "TTS_PROVIDER": "elevenlabs",
            }
            src = os.path.join(tmp, "src.mp3")
            with open(src, "wb") as f:
                f.write(b"mp3")
            key = tts.tts_cache_key("hello world", "elevenlabs", "")
            dest = os.path.join(tmp, "out.mp3")
            with patch.dict(os.environ, env, clear=False):
                tts.tts_cache_store(key, src)
                with (
                    patch.object(tts, "_tts_cache_voice", return_value=""),
                    patch.object(tts, "_try_alt_tts_provider", return_value=None),
                    patch.object(tts, "ElevenLabs") as eleven,
                ):
                    tts.generate_audio("hello world", dest)
            eleven.assert_not_called()
            self.assertTrue(tts.last_tts_was_cache_hit())

    def test_env_toggle(self):
        with patch.dict(os.environ, {"TTS_CACHE": "false"}, clear=False):
            self.assertFalse(tts.tts_cache_enabled())
        with patch.dict(os.environ, {"TTS_CACHE": "true"}, clear=False):
            self.assertTrue(tts.tts_cache_enabled())
        with patch.dict(os.environ, {"TTS_CACHE": ""}, clear=False):
            self.assertFalse(tts.tts_cache_enabled())

    def test_lookup_miss_when_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"TTS_CACHE": "true", "TTS_CACHE_DIR": tmp}
            dest = os.path.join(tmp, "out.mp3")
            with patch.dict(os.environ, env, clear=False):
                self.assertFalse(tts.tts_cache_lookup("deadbeef", dest))
            self.assertFalse(os.path.exists(dest))


if __name__ == "__main__":
    unittest.main()
