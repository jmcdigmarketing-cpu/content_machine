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

    def test_estimate_duration_matches_measured_delivery(self):
        # Run 66 rendered 243 words as 70.2s of audio. The old constant (2.4 w/s)
        # predicted 101s — a 38% error the operator saw before deciding to render.
        seconds = estimate_duration_seconds("word " * 243)
        self.assertAlmostEqual(seconds, 70.2, delta=8.0)

    def test_preset_seconds_are_derived_from_words(self):
        # Durations used to be stored beside the word range and silently disagreed with
        # it ("Extended (420-900s)" really produced ~300-600s). They are computed now,
        # so the two can never drift apart again.
        from core.script_length import WORDS_PER_SECOND

        for preset in (get_length_preset(c) for c in ("1", "2", "3", "4")):
            self.assertEqual(preset.min_seconds, round(preset.min_words / WORDS_PER_SECOND))
            self.assertEqual(preset.max_seconds, round(preset.max_words / WORDS_PER_SECOND))

    def test_long_preset_shape(self):
        p = get_length_preset("3")
        self.assertGreaterEqual(p.min_words, 300)
        self.assertLess(p.min_seconds, p.max_seconds)

    def test_rate_reflects_measurement(self):
        # Guards against a silent revert: measured median was 3.29 w/s over 14 renders
        # (py -m scripts.bench_script_duration).
        from core.script_length import WORDS_PER_SECOND

        self.assertAlmostEqual(WORDS_PER_SECOND, 3.3, delta=0.4)

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
