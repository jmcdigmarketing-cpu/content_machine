"""TTS cache by script hash — temp dir only, never data/tts_cache."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from core import tts


class TestTtsCache(unittest.TestCase):
    def setUp(self):
        """`_last_cache_hit` / `_last_piper_mix` are module globals that
        `generate_audio` only resets when it is *called*, so a test asserting
        "no hit yet" was really asserting "no earlier test in this class called
        generate_audio" — it passed on alphabetical ordering, not on behaviour.
        Reset explicitly so the order of these tests cannot decide the result."""
        tts._last_cache_hit = False
        tts._last_piper_mix = False

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

    def test_a_cache_hit_records_zero_synthesized_characters(self):
        """Found while scoping #402. `record_tts_actual` is called *before*
        `tts_cache_lookup`, so a cached render stamps a full script's worth of
        "actual synth chars" for characters nothing synthesized — and
        `core/pipeline.py:48` persists that as `tts_actual_chars` into the run
        ledger, which is the number the operator and the analytics layer read.

        Same class as the run-71 claim-verifier defect: a measurement that
        reports clean while measuring the wrong thing.
        """
        from core import tts_char_cap

        script = "hello world"
        with tempfile.TemporaryDirectory() as tmp:
            env = {"TTS_CACHE": "true", "TTS_CACHE_DIR": tmp, "TTS_PROVIDER": "elevenlabs"}
            src = os.path.join(tmp, "src.mp3")
            with open(src, "wb") as f:
                f.write(b"mp3")
            key = tts.tts_cache_key(script, "elevenlabs", "")
            with patch.dict(os.environ, env, clear=False):
                tts.tts_cache_store(key, src)
                tts_char_cap.reset_tts_forecast()
                with (
                    patch.object(tts, "_tts_cache_voice", return_value=""),
                    patch.object(tts, "_try_alt_tts_provider", return_value=None),
                    patch.object(tts, "ElevenLabs"),
                ):
                    tts.generate_audio(script, os.path.join(tmp, "out.mp3"))
                snap = tts_char_cap.last_tts_forecast() or {}

        self.assertTrue(tts.last_tts_was_cache_hit())
        self.assertEqual(
            snap.get("actual_chars"),
            0,
            f"a cache hit billed {snap.get('actual_chars')} chars it never synthesized",
        )

    def test_env_toggle(self):
        with patch.dict(os.environ, {"TTS_CACHE": "false"}, clear=False):
            self.assertFalse(tts.tts_cache_enabled())
        with patch.dict(os.environ, {"TTS_CACHE": "true"}, clear=False):
            self.assertTrue(tts.tts_cache_enabled())
        with patch.dict(os.environ, {"TTS_CACHE": ""}, clear=False):
            self.assertTrue(tts.tts_cache_enabled())

    def test_unset_env_defaults_the_cache_on(self):
        """#809. Empty/absent is production-on, the BACKGROUND_FAST_CUT polarity.
        The suite still pins TTS_CACHE=false in tests/__init__.py."""
        env = {k: v for k, v in os.environ.items() if k != "TTS_CACHE"}
        with patch.dict(os.environ, env, clear=True):
            self.assertTrue(tts.tts_cache_enabled())

    def test_cache_status_line_reports_hits_from_injected_flags(self):
        """Never open the operator's data/traces from this test."""
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "abc.mp3"), "wb") as handle:
                handle.write(b"x")
            snap = tts.tts_cache_status(cache_dir=tmp, cached_flags=[True, True, False])
            line = tts.format_tts_cache_line(snap)
        self.assertEqual(snap["files"], 1)
        self.assertAlmostEqual(snap["hit_rate"], 2 / 3)
        self.assertIn("TTS cache:", line)
        self.assertIn("2/3 hits", line)

    def test_overnight_skip_path_prints_the_cache_line(self) -> None:
        from core.overnight import OvernightResult, render_overnight

        text = render_overnight(OvernightResult(channel_id="tapin", requested=0))
        self.assertIn("TTS cache:", text)

    def test_lookup_miss_when_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"TTS_CACHE": "true", "TTS_CACHE_DIR": tmp}
            dest = os.path.join(tmp, "out.mp3")
            with patch.dict(os.environ, env, clear=False):
                self.assertFalse(tts.tts_cache_lookup("deadbeef", dest))
            self.assertFalse(os.path.exists(dest))


if __name__ == "__main__":
    unittest.main()
