"""#409: a per-channel brand-safety file, not the odds-only strip.

A sentence that contains a shipped phrase is dropped. Ordinary gaming copy
the odds module already leaves alone stays. A one-word line is not a phrase.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class BrandLexiconTests(unittest.TestCase):
    def test_the_shipped_tapin_file_drops_its_phrase(self):
        from core.odds_language import apply_brand_lexicon, lexicon_phrases

        phrases = lexicon_phrases("tapin")
        self.assertTrue(phrases)
        self.assertTrue(all(" " in phrase for phrase in phrases))
        phrase = phrases[0]
        script = (
            f"Topuria took the first round. This is a {phrase} offer. The rematch is in December."
        )
        out, notes = apply_brand_lexicon(script, channel_id="tapin")
        self.assertNotIn(phrase, out.lower())
        self.assertIn("Topuria took the first round", out)
        self.assertIn("December", out)
        self.assertTrue(any("1" in note for note in notes))

    def test_ordinary_gaming_copy_stays(self):
        from core.odds_language import apply_brand_lexicon

        script = "He is a fan favorite. Lock it in before the patch."
        out, notes = apply_brand_lexicon(script, channel_id="tapin")
        self.assertEqual(out, script)
        self.assertEqual(notes, [])

    def test_a_channel_with_no_file_is_unchanged(self):
        from core.odds_language import apply_brand_lexicon

        script = "A guaranteed profit is still just a sentence."
        out, notes = apply_brand_lexicon(script, channel_id="no-such-channel")
        self.assertEqual(out, script)
        self.assertEqual(notes, [])

    def test_a_one_word_line_does_not_drop_a_sentence(self):
        from core.odds_language import apply_brand_lexicon

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tapin.txt"
            path.write_text("kill\n", encoding="utf-8")
            with patch("core.odds_language.lexicon_path", return_value=path):
                out, notes = apply_brand_lexicon(
                    "They kill the round with a jab.", channel_id="tapin"
                )
        self.assertIn("kill", out)
        self.assertEqual(notes, [])
