"""#1036 a later paragraph starts when the previous paragraph's last word ends.

The file is longer than the last word (trailing silence). The joined sidecar must
not use that file duration, and it must not keep a segment's own leading gap.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from core import tts


class TestParagraphWordAnchor(unittest.TestCase):
    def test_paragraph_two_starts_at_paragraph_ones_last_word(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            chunks = [
                [{"word": "Alpha", "start": 0.0, "end": 1.0}],
                [{"word": "Beta", "start": 0.2, "end": 0.8}],
                [{"word": "Gamma", "start": 0.1, "end": 0.4}],
            ]
            for i, words in enumerate(chunks):
                seg = os.path.join(tmp, f"p{i}.mp3")
                with open(seg, "wb") as handle:
                    handle.write(b"mp3")
                with open(seg + ".words.json", "w", encoding="utf-8") as handle:
                    json.dump(words, handle)
                paths.append(seg)
            dest = os.path.join(tmp, "out.mp3")
            tts._write_concat_word_sidecar(paths, dest)
            with open(dest + ".words.json", encoding="utf-8") as handle:
                merged = json.load(handle)

        self.assertEqual(merged[1]["word"], "Beta")
        self.assertAlmostEqual(merged[1]["start"], 1.0)
        self.assertEqual(merged[2]["word"], "Gamma")
        self.assertAlmostEqual(merged[2]["start"], 1.6)


if __name__ == "__main__":
    unittest.main()
