"""Tests for caption (SRT) generation (Phase Q)."""

import unittest

from video.subtitles import build_srt, format_timestamp, split_script_into_lines


class TestSplit(unittest.TestCase):
    def test_chunks_respect_max_words(self):
        lines = split_script_into_lines("one two three four five six seven", max_words=3)
        self.assertEqual(lines, ["one two three", "four five six", "seven"])

    def test_sentence_boundaries_not_crossed(self):
        lines = split_script_into_lines("One two three. Four five.", max_words=5)
        # The two sentences must not be merged into one caption line.
        self.assertEqual(lines, ["One two three.", "Four five."])

    def test_empty(self):
        self.assertEqual(split_script_into_lines(""), [])


class TestTimestamp(unittest.TestCase):
    def test_format(self):
        self.assertEqual(format_timestamp(0), "00:00:00,000")
        self.assertEqual(format_timestamp(61.5), "00:01:01,500")

    def test_negative_clamped(self):
        self.assertEqual(format_timestamp(-5), "00:00:00,000")


class TestBuildSrt(unittest.TestCase):
    def test_proportional_timing(self):
        # Two lines, 4 words then 1 word, over 10s -> ~8s / ~2s split.
        srt = build_srt("a b c d. e.", 10.0, max_words=5)
        self.assertIn("1\n00:00:00,000 --> 00:00:08,000", srt)
        # Last line must end exactly at duration.
        self.assertIn("--> 00:00:10,000", srt)

    def test_block_count_matches_lines(self):
        srt = build_srt("one two three four five six", 6.0, max_words=2)
        # 6 words / 2 per line = 3 blocks.
        self.assertEqual(srt.count("-->"), 3)

    def test_empty_script_returns_empty(self):
        self.assertEqual(build_srt("", 10.0), "")

    def test_last_subtitle_ends_at_duration(self):
        srt = build_srt("hello world this is a test caption line", 12.0, max_words=3)
        self.assertIn("--> 00:00:12,000", srt)


if __name__ == "__main__":
    unittest.main()
