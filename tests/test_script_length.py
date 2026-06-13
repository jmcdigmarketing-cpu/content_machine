import unittest

from core.script_length import (
    count_spoken_words,
    estimate_duration_seconds,
    get_length_preset,
    word_range,
)


class TestScriptLength(unittest.TestCase):
    def test_long_preset_word_range(self):
        self.assertEqual(word_range("3"), (300, 750))

    def test_count_words(self):
        script = "one two three four five " * 20
        self.assertEqual(count_spoken_words(script), 100)

    def test_estimate_duration(self):
        script = "word " * 240
        seconds = estimate_duration_seconds(script)
        self.assertGreaterEqual(seconds, 90)

    def test_preset_targets(self):
        p = get_length_preset("3")
        self.assertEqual(p.min_seconds, 120)
        self.assertGreaterEqual(p.min_words, 300)


if __name__ == "__main__":
    unittest.main()
