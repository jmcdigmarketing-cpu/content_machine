"""#658: one synthesize-this-text-to-this-path seam under generate_audio."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from core import tts


class TestSynthSeam(unittest.TestCase):
    def setUp(self):
        tts._last_cache_hit = False
        tts._last_piper_mix = False

    def test_cache_hit_does_not_call_the_synth_seam(self):
        """generate_audio still owns lookup; a hit must not synthesize."""
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
                    patch.object(tts, "synthesize_to_path") as seam,
                ):
                    tts.generate_audio("hello world", dest)
            seam.assert_not_called()
            self.assertTrue(tts.last_tts_was_cache_hit())

    def test_cache_miss_delegates_to_synthesize_to_path(self):
        dest_holder = {}

        def fake_seam(spoken, spoken_for_alt, output_path, channel_id, cache_key):
            dest_holder["path"] = output_path
            with open(output_path, "wb") as f:
                f.write(b"ID3")
            return output_path

        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "out.mp3")
            with (
                patch.dict(
                    os.environ,
                    {"TTS_CACHE": "false", "TTS_PROVIDER": "elevenlabs"},
                    clear=False,
                ),
                patch.object(tts, "synthesize_to_path", side_effect=fake_seam) as seam,
            ):
                out = tts.generate_audio("hello world", dest, channel_id="tapin")
            seam.assert_called_once()
            self.assertEqual(out, dest)
            self.assertTrue(os.path.isfile(dest))

    def test_alt_provider_success_stores_the_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "out.mp3")
            cache_dir = os.path.join(tmp, "cache")

            def fake_alt(spoken, output_path, channel_id=None):
                with open(output_path, "wb") as f:
                    f.write(b"alt")
                return output_path

            env = {
                "TTS_CACHE": "true",
                "TTS_CACHE_DIR": cache_dir,
                "TTS_PROVIDER": "piper",
                "FREE_MODE_STRICT": "",
            }
            with patch.dict(os.environ, env, clear=False):
                with (
                    patch.object(tts, "_try_alt_tts_provider", side_effect=fake_alt),
                    patch.object(tts, "_tts_cache_voice", return_value="lessac"),
                ):
                    tts.synthesize_to_path(
                        "hello",
                        "hello",
                        dest,
                        "tapin",
                        tts.tts_cache_key("hello", "piper", "lessac"),
                    )
                key = tts.tts_cache_key("hello", "piper", "lessac")
                dest2 = os.path.join(tmp, "out2.mp3")
                self.assertTrue(tts.tts_cache_lookup(key, dest2))
                with open(dest2, "rb") as f:
                    self.assertEqual(f.read(), b"alt")

    def test_elevenlabs_plain_stores_the_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "out.mp3")
            cache_dir = os.path.join(tmp, "cache")
            env = {
                "TTS_CACHE": "true",
                "TTS_CACHE_DIR": cache_dir,
                "TTS_PROVIDER": "elevenlabs",
                "ELEVEN_API_KEY": "k",
                "FREE_MODE_STRICT": "",
            }
            audio = MagicMock()
            audio.__iter__ = lambda self: iter([b"el"])
            client = MagicMock()
            client.text_to_speech.convert.return_value = audio

            with patch.dict(os.environ, env, clear=False):
                with (
                    patch.object(tts, "_try_alt_tts_provider", return_value=None),
                    patch.object(tts, "_should_piper_mix", return_value=False),
                    patch.object(tts, "_elevenlabs_quota_would_exceed", return_value=False),
                    patch.object(tts, "_word_timestamps_enabled", return_value=False),
                    patch.object(tts, "resolve_tts_config", return_value=("vid", "mid")),
                    patch.object(tts, "_elevenlabs_record_chars"),
                    patch.object(tts, "ElevenLabs", return_value=client),
                    patch.object(tts, "_tts_cache_voice", return_value="vid"),
                ):
                    tts.synthesize_to_path(
                        "hello",
                        "hello",
                        dest,
                        "tapin",
                        tts.tts_cache_key("hello", "elevenlabs", "vid"),
                    )
                key = tts.tts_cache_key("hello", "elevenlabs", "vid")
                dest2 = os.path.join(tmp, "out2.mp3")
                self.assertTrue(tts.tts_cache_lookup(key, dest2))


class TestSentenceCache(unittest.TestCase):
    def setUp(self):
        tts._last_cache_hit = False
        tts._last_piper_mix = False
        tts._last_cache_fraction = 0.0

    def test_two_sentences_call_the_seam_once_each(self):
        script = "First sentence. Second sentence."
        calls: list[str] = []

        def fake_seam(spoken, spoken_for_alt, output_path, channel_id, cache_key, **kwargs):
            calls.append(spoken)
            with open(output_path, "wb") as f:
                f.write(b"seg")
            return output_path

        def fake_concat(paths, dest):
            with open(dest, "wb") as out:
                for path in paths:
                    with open(path, "rb") as f:
                        out.write(f.read())
            return dest

        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "out.mp3")
            with (
                patch.dict(
                    os.environ,
                    {"TTS_CACHE": "true", "TTS_CACHE_DIR": os.path.join(tmp, "cache")},
                    clear=False,
                ),
                patch.object(tts, "synthesize_to_path", side_effect=fake_seam),
                patch.object(tts, "concat_audio_segments", side_effect=fake_concat),
                patch.object(tts, "_tts_cache_voice", return_value=""),
            ):
                tts.generate_audio(script, dest, channel_id="tapin")
            self.assertEqual(len(calls), 2)
            self.assertTrue(os.path.isfile(dest))

    def test_partial_sentence_hit_is_fractional_not_free(self):
        """A 50% char hit must not report a full cache hit (which meters $0)."""
        a = "AAAAAAAAAA."
        b = "BBBBBBBBBB."
        script = f"{a} {b}"
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = os.path.join(tmp, "cache")
            env = {
                "TTS_CACHE": "true",
                "TTS_CACHE_DIR": cache_dir,
                "TTS_PROVIDER": "elevenlabs",
            }
            key_a = tts.tts_cache_key(a, "elevenlabs", "")
            src = os.path.join(tmp, "a.mp3")
            with open(src, "wb") as f:
                f.write(b"aaa")
            with open(src + ".words.json", "w", encoding="utf-8") as f:
                f.write('[{"word":"A","start":0.0,"end":0.5}]')

            def fake_seam(spoken, spoken_for_alt, output_path, channel_id, cache_key, **kwargs):
                with open(output_path, "wb") as fh:
                    fh.write(b"bbb")
                with open(output_path + ".words.json", "w", encoding="utf-8") as fh:
                    fh.write('[{"word":"B","start":0.0,"end":0.5}]')
                return output_path

            def fake_concat(paths, dest):
                with open(dest, "wb") as out:
                    for path in paths:
                        with open(path, "rb") as fh:
                            out.write(fh.read())
                return dest

            with patch.dict(os.environ, env, clear=False):
                tts.tts_cache_store(key_a, src)
                dest = os.path.join(tmp, "out.mp3")
                with (
                    patch.object(tts, "synthesize_to_path", side_effect=fake_seam) as seam,
                    patch.object(tts, "concat_audio_segments", side_effect=fake_concat),
                    patch.object(tts, "_tts_cache_voice", return_value=""),
                    patch.object(tts, "segment_audio_duration", return_value=0.5),
                ):
                    tts.generate_audio(script, dest, channel_id="tapin")
            self.assertEqual(seam.call_count, 1)
            self.assertFalse(tts.last_tts_was_cache_hit())
            self.assertAlmostEqual(tts.last_tts_cache_fraction(), 0.5, places=2)

    def test_the_sentence_path_is_off_when_the_cache_is_off(self):
        """With the cache off, `tts_cache_lookup` always misses and store is a
        no-op, so splitting buys nothing. Pin false explicitly — empty now means on.
        """
        script = "First sentence. Second sentence. Third sentence."
        calls: list[str] = []

        def fake_seam(spoken, spoken_for_alt, output_path, channel_id, cache_key, **kwargs):
            calls.append(spoken)
            with open(output_path, "wb") as f:
                f.write(b"whole")
            return output_path

        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "out.mp3")
            with (
                patch.dict(os.environ, {"TTS_CACHE": "false"}, clear=False),
                patch.object(tts, "synthesize_to_path", side_effect=fake_seam),
                patch.object(tts, "concat_audio_segments") as concat,
                patch.object(tts, "_tts_cache_voice", return_value=""),
            ):
                tts.generate_audio(script, dest, channel_id="tapin")

        self.assertEqual(calls, [script], "the script was split with the cache disabled")
        concat.assert_not_called()

    def test_a_concat_failure_records_every_character_it_billed(self):
        """Cursor flagged this one itself: if concat fails after the segments are
        synthesized, the fallback synthesizes the whole script *again* — so the
        provider is billed roughly twice.

        The spend is hard to prevent once it has happened, but the ledger must
        not lie about it. `_record_actual(len(spoken_for_alt))` on the fallback
        path reports only the second synthesis and erases the first, which is the
        same defect shape as #657.
        """
        from core import tts_char_cap

        a, b = "AAAAAAAAAA.", "BBBBBBBBBB."
        script = f"{a} {b}"

        def fake_seam(spoken, spoken_for_alt, output_path, channel_id, cache_key, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"seg")
            return output_path

        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "TTS_CACHE": "true",
                "TTS_CACHE_DIR": os.path.join(tmp, "cache"),
                "TTS_PROVIDER": "elevenlabs",
            }
            dest = os.path.join(tmp, "out.mp3")
            with patch.dict(os.environ, env, clear=False):
                tts_char_cap.reset_tts_forecast()
                with (
                    patch.object(tts, "synthesize_to_path", side_effect=fake_seam),
                    patch.object(
                        tts, "concat_audio_segments", side_effect=RuntimeError("ffmpeg missing")
                    ),
                    patch.object(tts, "_tts_cache_voice", return_value=""),
                ):
                    tts.generate_audio(script, dest, channel_id="tapin")
                snap = tts_char_cap.last_tts_forecast() or {}

        billed = snap.get("actual_chars") or 0
        self.assertGreaterEqual(
            billed,
            len(a) + len(b) + len(script),
            f"ledger recorded {billed} chars but the segments were billed too",
        )

    def test_a_failed_concat_preflight_synths_the_script_once(self):
        """#666. Concat failure after the segments are billed double-charges.
        ffmpeg being missing is knowable for free, so the run must take the
        whole-script path *before* any segment synth — one seam call, one bill.
        """
        script = "First sentence. Second sentence. Third sentence."
        calls: list[str] = []

        def fake_seam(spoken, spoken_for_alt, output_path, channel_id, cache_key, **kwargs):
            calls.append(spoken)
            with open(output_path, "wb") as f:
                f.write(b"whole")
            return output_path

        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "out.mp3")
            with (
                patch.dict(
                    os.environ,
                    {"TTS_CACHE": "true", "TTS_CACHE_DIR": os.path.join(tmp, "cache")},
                    clear=False,
                ),
                patch.object(tts, "synthesize_to_path", side_effect=fake_seam),
                patch.object(tts, "concat_audio_segments") as concat,
                patch.object(tts, "_tts_cache_voice", return_value=""),
                patch.object(tts.shutil, "which", return_value=None),
            ):
                tts.generate_audio(script, dest, channel_id="tapin")

        self.assertEqual(calls, [script], "preflight fail still entered the segment loop")
        concat.assert_not_called()

    def test_offset_word_timings_shifts_start_and_end(self):
        shifted = tts.offset_word_timings(
            [{"word": "Hi", "start": 0.1, "end": 0.2}],
            1.5,
        )
        self.assertEqual(shifted[0]["start"], 1.6)
        self.assertEqual(shifted[0]["end"], 1.7)


if __name__ == "__main__":
    unittest.main()
