"""#1035 one ElevenLabs request per paragraph, with the neighbours on the payload.

The cache key is that paragraph plus those neighbours. A sentence key must not
hit. The client is a fake. Nothing talks to ElevenLabs.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from core import tts

SCRIPT = (
    "Alpha is the first paragraph. It keeps going.\n\n"
    "Beta is the second paragraph.\n\n"
    "Gamma is the third."
)


class TestParagraphRequests(unittest.TestCase):
    def test_the_middle_request_names_both_neighbours(self):
        client = MagicMock()
        client.text_to_speech.convert.return_value = [b"mp3"]

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
                patch.object(tts, "segment_audio_duration", return_value=1.0),
            ):
                tts.generate_audio(SCRIPT, dest, channel_id="tapin")

        calls = client.text_to_speech.convert.call_args_list
        self.assertEqual(len(calls), 3)
        middle = calls[1].kwargs
        self.assertEqual(middle["text"], "Beta is the second paragraph.")
        self.assertEqual(middle["previous_text"], "Alpha is the first paragraph. It keeps going.")
        self.assertEqual(middle["next_text"], "Gamma is the third.")
        self.assertNotIn("previous_text", calls[0].kwargs)
        self.assertEqual(calls[0].kwargs["next_text"], "Beta is the second paragraph.")

    def test_the_cache_key_includes_the_neighbours(self):
        seen: list[str] = []

        def fake_lookup(key, dest):
            seen.append(key)
            return False

        def fake_seam(spoken, spoken_for_alt, output_path, channel_id, cache_key, **kwargs):
            with open(output_path, "wb") as handle:
                handle.write(b"mp3")
            return output_path

        def fake_concat(paths, dest):
            with open(dest, "wb") as handle:
                handle.write(b"joined")
            return dest

        beta = "Beta is the second paragraph."
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
            ):
                tts.generate_audio(SCRIPT, dest, channel_id="tapin")

        expected = tts.tts_cache_key(
            tts.paragraph_cache_text(
                beta,
                "Alpha is the first paragraph. It keeps going.",
                "Gamma is the third.",
            ),
            "elevenlabs",
            "vid",
        )
        sentence_only = tts.tts_cache_key(beta, "elevenlabs", "vid")
        self.assertIn(expected, seen)
        self.assertNotIn(sentence_only, seen)


if __name__ == "__main__":
    unittest.main()
