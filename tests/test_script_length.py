import unittest

from core.script_length import (
    count_spoken_words,
    estimate_duration_seconds,
    get_length_preset,
    nudge_length,
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

    def test_nudge_length_up_and_down(self):
        self.assertEqual(nudge_length("1", 1), "2")
        self.assertEqual(nudge_length("2", 1), "3")
        self.assertEqual(nudge_length("3", -1), "2")

    def test_nudge_length_clamps_to_range(self):
        self.assertEqual(nudge_length("4", 1), "4")  # can't go past Extended
        self.assertEqual(nudge_length("1", -1), "1")  # can't go below Short

    def test_nudge_length_bad_input_defaults_to_medium(self):
        self.assertEqual(nudge_length("", 1), "3")  # 2 -> 3
        self.assertEqual(nudge_length("x", -1), "1")  # 2 -> 1


if __name__ == "__main__":
    unittest.main()
