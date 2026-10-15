"""#404: dead air on generated audio moves the words by the time actually removed.

Leading and trailing silence go. An internal gap longer than 0.4s shrinks to
0.15s. A shorter breath stays, so a pause between words is not eaten.
"""

from __future__ import annotations

import unittest


class DeadAirTimingTests(unittest.TestCase):
    def test_long_gaps_shift_the_words_and_a_short_breath_does_not(self):
        from core.voice.dead_air import cuts_for_silence, shift_word_timings

        words = [
            {"word": "a", "start": 0.55, "end": 1.1},
            {"word": "b", "start": 2.0, "end": 2.1},
            {"word": "c", "start": 2.45, "end": 2.9},
        ]
        silences = [(0.0, 0.5), (1.2, 1.9), (2.15, 2.35), (3.0, 3.4)]
        cuts = cuts_for_silence(silences, words)
        shifted, removed = shift_word_timings(words, cuts)
        self.assertAlmostEqual(removed, 0.5 + 0.55 + 0.4)
        self.assertAlmostEqual(shifted[0]["start"], 0.05)
        self.assertAlmostEqual(shifted[1]["start"], 0.95)
        self.assertAlmostEqual(shifted[2]["start"], 1.4)
        self.assertEqual(shifted[2]["word"], "c")
