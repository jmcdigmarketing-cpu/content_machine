"""#217 the paragraph path rewrites a lexicon name before the provider speaks it.

The editor for the lexicon is not this change. Captions keep the original spelling.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from core import tts

SCRIPT = "Salkilld wins the fight.\n\nThe card is set tonight."


class TestParagraphLexicon(unittest.TestCase):
    def test_the_spoken_paragraph_uses_the_lexicon(self):
        heard: list[str] = []

        def fake_seam(spoken, spoken_for_alt, output_path, channel_id, cache_key, **kwargs):
            heard.append(spoken)
            with open(output_path, "wb") as handle:
                handle.write(b"mp3")
            return output_path

        def fake_concat(paths, dest):
            with open(dest, "wb") as handle:
                handle.write(b"joined")
            return dest

        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "out.mp3")
            with (
                patch.dict(
                    os.environ,
                    {
                        "TTS_CACHE": "true",
                        "TTS_CACHE_DIR": os.path.join(tmp, "cache"),
                        "TTS_PROVIDER": "elevenlabs",
                    },
                    clear=False,
                ),
                patch.object(tts, "_lexicon_for_channel", return_value={"Salkilld": "Sal-killed"}),
                patch.object(tts, "synthesize_to_path", side_effect=fake_seam),
                patch.object(tts, "ffmpeg_concat_ready", return_value=True),
                patch.object(tts, "concat_audio_segments", side_effect=fake_concat),
                patch.object(tts, "segment_audio_duration", return_value=1.0),
                patch.object(tts, "_tts_cache_voice", return_value="vid"),
            ):
                tts.generate_audio(SCRIPT, dest, channel_id="tapin")

        self.assertEqual(SCRIPT, "Salkilld wins the fight.\n\nThe card is set tonight.")
        self.assertEqual(heard[0], "Sal-killed wins the fight.")
        self.assertNotIn("Salkilld", heard[0])


if __name__ == "__main__":
    unittest.main()
