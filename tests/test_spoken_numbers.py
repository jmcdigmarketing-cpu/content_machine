"""#123 number/SSML reading rules — TTS spoken form changes; captions keep digits."""

from __future__ import annotations

import unittest

from core.spoken_numbers import expand_spoken_numbers
from core.utils import clean_script_for_tts


class TestSpokenNumbers(unittest.TestCase):
    def test_fight_record_and_event_and_purse(self):
        spoken = expand_spoken_numbers("He went 29-1 at UFC 317 for a $50k purse.")
        self.assertIn("twenty-nine one", spoken.lower())
        self.assertIn("three seventeen", spoken.lower())
        self.assertIn("fifty thousand dollars", spoken.lower())
        self.assertNotIn("29-1", spoken)
        self.assertNotIn("$50k", spoken.lower())

    def test_captions_keep_digits(self):
        script = "He went 29-1 at UFC 317 for a $50k purse."
        cleaned = clean_script_for_tts(script)
        self.assertIn("29-1", cleaned)
        self.assertIn("UFC 317", cleaned)
        self.assertIn("$50k", cleaned)

    def test_unmatched_text_is_unchanged(self):
        raw = "Gaethje just submitted Gamrot."
        self.assertEqual(expand_spoken_numbers(raw), raw)
