"""Local-TTS voice variety (Pillar 6) — per-channel/pool voice resolution + delivery
jitter, fail-open to today's single-env behavior.

No heavy backend is installed in CI: these lock the *resolution* logic (which voice a
channel gets) and the pure jitter helper, and assert the Piper synth still fails open to
None (ElevenLabs fallback) when no voice resolves. The synth backends themselves are the
existing test_tts_local.py contract.
"""

import os
import unittest
from unittest.mock import patch

from config.channels import ChannelProfile
from core import tts


def _profile(cid: str = "tapin", **kw) -> ChannelProfile:
    return ChannelProfile(id=cid, **kw)


class TestResolveLocalVoice(unittest.TestCase):
    def test_per_channel_single_voice_wins(self):
        prof = _profile(local_tts_voice="voices/tapin.onnx")
        with patch("core.tts.get_channel_profile", return_value=prof):
            self.assertEqual(tts.resolve_local_voice("piper", "tapin"), "voices/tapin.onnx")

    def test_distinct_channels_get_distinct_voices(self):
        voices = {"tapin": "a.onnx", "moneywise": "b.onnx"}

        def _fake(cid=None):
            return _profile(cid or "default", local_tts_voice=voices.get(cid))

        with patch("core.tts.get_channel_profile", side_effect=_fake):
            self.assertEqual(tts.resolve_local_voice("piper", "tapin"), "a.onnx")
            self.assertEqual(tts.resolve_local_voice("piper", "moneywise"), "b.onnx")

    def test_pool_rotation_picks_only_from_pool(self):
        prof = _profile(local_tts_voices=("a.onnx", "b.onnx", "c.onnx"))
        with patch("core.tts.get_channel_profile", return_value=prof):
            picks = {tts.resolve_local_voice("piper", "tapin") for _ in range(40)}
        self.assertTrue(picks)
        self.assertTrue(picks.issubset({"a.onnx", "b.onnx", "c.onnx"}))

    def test_pool_beats_single_when_both_set(self):
        prof = _profile(local_tts_voice="single.onnx", local_tts_voices=("p.onnx",))
        with patch("core.tts.get_channel_profile", return_value=prof):
            self.assertEqual(tts.resolve_local_voice("piper", "tapin"), "p.onnx")

    def test_env_pool_used_when_no_channel_config(self):
        prof = _profile()
        with (
            patch("core.tts.get_channel_profile", return_value=prof),
            patch("core.tts.load_local_voice_pool", return_value={}),
            patch.dict(os.environ, {"PIPER_VOICES": "x.onnx, y.onnx"}, clear=False),
        ):
            picks = {tts.resolve_local_voice("piper", "tapin") for _ in range(40)}
        self.assertTrue(picks.issubset({"x.onnx", "y.onnx"}))

    def test_fail_open_to_env_single(self):
        # No per-channel config + no catalog + no pool → the exact PIPER_VOICE value.
        prof = _profile()
        with (
            patch("core.tts.get_channel_profile", return_value=prof),
            patch("core.tts.load_local_voice_pool", return_value={}),
            patch.dict(os.environ, {"PIPER_VOICE": "solo.onnx", "PIPER_VOICES": ""}, clear=False),
        ):
            self.assertEqual(tts.resolve_local_voice("piper", "tapin"), "solo.onnx")

    def test_nothing_configured_returns_none(self):
        prof = _profile()
        with (
            patch("core.tts.get_channel_profile", return_value=prof),
            patch("core.tts.load_local_voice_pool", return_value={}),
            patch.dict(os.environ, {"PIPER_VOICE": "", "PIPER_VOICES": ""}, clear=False),
        ):
            self.assertIsNone(tts.resolve_local_voice("piper", "tapin"))

    def test_non_local_provider_returns_none(self):
        self.assertIsNone(tts.resolve_local_voice("elevenlabs", "tapin"))
        self.assertIsNone(tts.resolve_local_voice("", "tapin"))

    def test_profile_error_falls_back_to_env(self):
        with (
            patch("core.tts.get_channel_profile", side_effect=RuntimeError("boom")),
            patch.dict(os.environ, {"KOKORO_VOICE": "af_bella"}, clear=False),
        ):
            os.environ.pop("KOKORO_VOICES", None)
            self.assertEqual(tts.resolve_local_voice("kokoro", "tapin"), "af_bella")


class TestVarietySpeedFactor(unittest.TestCase):
    def test_off_by_default_is_identity(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TTS_VOICE_VARIETY", None)
            self.assertEqual(tts._variety_speed_factor("tapin", seed="v1"), 1.0)

    def test_within_band_when_enabled(self):
        with patch.dict(os.environ, {"TTS_VOICE_VARIETY": "true"}, clear=False):
            for seed in ("a", "b", "c", "d", "e", "f", "g", "h"):
                factor = tts._variety_speed_factor("tapin", seed=seed)
                self.assertGreaterEqual(factor, tts._VARIETY_MIN)
                self.assertLessEqual(factor, tts._VARIETY_MAX)

    def test_deterministic_in_seed(self):
        with patch.dict(os.environ, {"TTS_VOICE_VARIETY": "1"}, clear=False):
            self.assertEqual(
                tts._variety_speed_factor("tapin", seed="same"),
                tts._variety_speed_factor("tapin", seed="same"),
            )

    def test_varies_across_seeds(self):
        with patch.dict(os.environ, {"TTS_VOICE_VARIETY": "yes"}, clear=False):
            vals = {tts._variety_speed_factor("tapin", seed=str(i)) for i in range(25)}
        self.assertGreater(len(vals), 1)


class TestPiperSynConfig(unittest.TestCase):
    def test_identity_factor_returns_none(self):
        self.assertIsNone(tts._piper_syn_config(1.0))

    def test_non_identity_never_raises(self):
        # piper may be absent in CI (→ None) or present (→ a config object). Never raises.
        tts._piper_syn_config(0.95)


class TestPiperSynthVoiceResolution(unittest.TestCase):
    def test_missing_resolved_voice_returns_none(self):
        # A resolved voice that isn't a real file must fail open to None (ElevenLabs
        # fallback) without importing piper or raising.
        prof = _profile(local_tts_voice="does/not/exist.onnx")
        with patch("core.tts.get_channel_profile", return_value=prof):
            self.assertIsNone(tts._piper_synth("hello", "out.mp3", "tapin"))


class TestPiperWriteWav(unittest.TestCase):
    def test_prefers_synthesize_wav_with_syn_config(self):
        seen = {}

        class _Voice:
            def synthesize_wav(self, text, wav_file, syn_config=None):
                seen["text"], seen["syn_config"] = text, syn_config

            def synthesize(self, text, wav_file):  # must not be used when _wav exists
                seen["legacy"] = True

        tts._piper_write_wav(_Voice(), "hi", object(), "CFG")
        self.assertEqual(seen.get("text"), "hi")
        self.assertEqual(seen.get("syn_config"), "CFG")
        self.assertNotIn("legacy", seen)

    def test_synthesize_wav_without_config(self):
        seen = {}

        class _Voice:
            def synthesize_wav(self, text, wav_file, syn_config=None):
                seen["syn_config"] = syn_config

        tts._piper_write_wav(_Voice(), "hi", object(), None)
        self.assertIsNone(seen.get("syn_config"))

    def test_legacy_fallback_when_no_synthesize_wav(self):
        seen = {}

        class _Voice:
            def synthesize(self, text, wav_file):
                seen["called"] = True

        tts._piper_write_wav(_Voice(), "hi", object(), None)
        self.assertTrue(seen.get("called"))


class TestChannelLocalVoiceConfig(unittest.TestCase):
    def test_local_voice_fields_parsed_from_tts_block(self):
        import config.channels as ch

        raw = {
            "channels": {
                "tapin": {"tts": {"local_voice": "t.onnx"}},
                "moneywise": {"tts": {"local_voices": ["m1.onnx", "m2.onnx"]}},
            }
        }
        ch.get_channel_profiles.cache_clear()
        try:
            with patch.object(ch, "_load_channels_file", return_value=raw):
                profs = ch.get_channel_profiles()
                self.assertEqual(profs["tapin"].local_tts_voice, "t.onnx")
                self.assertIsNone(profs["tapin"].local_tts_voices)
                self.assertEqual(profs["moneywise"].local_tts_voices, ("m1.onnx", "m2.onnx"))
        finally:
            ch.get_channel_profiles.cache_clear()

    def test_defaults_are_none_when_unconfigured(self):
        prof = ChannelProfile(id="x")
        self.assertIsNone(prof.local_tts_voice)
        self.assertIsNone(prof.local_tts_voices)


if __name__ == "__main__":
    unittest.main()
