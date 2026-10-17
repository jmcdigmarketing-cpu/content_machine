"""Correction to Cursor's e207cc3 (#1039 + #1056), found reviewing it before the push.

The script prompt now asks for "*emphasis*" and "..." marks, and only the voice request strips
them. The hook card TapIn turned on shows the script's first sentence for the first second - it
read "A sleep therapist designed *Pokemon's* new body pillows..." - and the title generator and
the no-timing caption fallback read the same raw text.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

MARKED = "A sleep therapist designed *Pokemon's* new body pillows... That's not merch."


class MarksOffScreenTests(unittest.TestCase):
    def test_the_hook_line_has_no_asterisks(self):
        from core.title_generator import _hook_line

        line = _hook_line(MARKED)
        self.assertNotIn("*", line)
        self.assertIn("Pokemon's", line)

    def test_captions_without_timings_have_no_asterisks(self):
        from video import subtitles

        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(subtitles, "SUBTITLE_DIR", tmp),
                patch.object(subtitles, "resolve_word_timings", return_value=None),
            ):
                path = subtitles.generate_subtitle_file(MARKED, 6.0, channel_id="tapin")
            with open(path, encoding="utf-8") as f:
                text = f.read()
        self.assertNotIn("*", text)
        self.assertIn("Pokemon's", text)

    def test_the_voice_still_reads_the_marks(self):
        from core.voice.delivery import delivery_for

        spoken = delivery_for(MARKED, hook=True, speed=1.0)
        self.assertEqual(spoken["style"], 0.35)
        self.assertNotIn("*", spoken["text"])


if __name__ == "__main__":
    unittest.main()
