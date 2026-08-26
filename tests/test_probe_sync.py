"""Candidate 44: the intro-offset explanation must be reproducible, not relearned.

A finished render looks out of sync with its own SRT — cue 3 says 3.220s, the frame at
4.2s still shows cue 2 — because `prepend_channel_intro` runs *after* ffmpeg and pushes
audio and burned subtitles later together. The pure helpers below encode that reasoning
so the next person gets a sentence instead of an afternoon.

No ffmpeg: only the pure parsers/verdict are exercised (tests/CLAUDE.md).
"""

import unittest
from unittest.mock import patch

from scripts import probe_sync


class TestSrtParsing(unittest.TestCase):
    SRT = (
        "1\n00:00:00,000 --> 00:00:01,400\nSalkilld jumps to 10 after\n\n"
        "2\n00:00:01,400 --> 00:00:02,900\none win-is the system broken?\n\n"
        "3\n00:00:03,220 --> 00:00:05,119\nQuillan Salkilld just submitted Mateusz\n"
    )

    def test_first_cue_start(self):
        self.assertAlmostEqual(probe_sync.parse_srt_first_cue(self.SRT), 0.0, places=3)

    def test_offset_first_cue(self):
        srt = "1\n00:00:03,220 --> 00:00:05,119\ntext\n"
        self.assertAlmostEqual(probe_sync.parse_srt_first_cue(srt), 3.220, places=3)

    def test_dot_millis_accepted(self):
        srt = "1\n00:00:02.500 --> 00:00:04.000\ntext\n"
        self.assertAlmostEqual(probe_sync.parse_srt_first_cue(srt), 2.5, places=3)

    def test_no_timecode(self):
        self.assertIsNone(probe_sync.parse_srt_first_cue("nothing here"))
        self.assertIsNone(probe_sync.parse_srt_first_cue(""))


class TestVerdict(unittest.TestCase):
    """The whole point: say IN SYNC when the pad is the intro."""

    def test_pad_matching_the_intro_is_in_sync(self):
        # The real TapIn numbers: 2.15s sting, ~2.167s after re-encode.
        v = probe_sync.verdict(first_cue=3.220, silence=2.167, intro=2.15)
        self.assertIn("IN SYNC", v)
        self.assertIn("2.15", v)
        self.assertIn("prepend_channel_intro", v)

    def test_reports_where_the_cue_actually_lands(self):
        v = probe_sync.verdict(first_cue=3.220, silence=2.167, intro=2.15)
        self.assertIn("5.39", v)  # 3.220 + 2.167

    def test_pad_without_a_matching_intro_is_flagged(self):
        v = probe_sync.verdict(first_cue=1.0, silence=4.0, intro=2.15)
        self.assertIn("does NOT match", v)
        self.assertIn("genuinely adrift", v)

    def test_no_pad_means_srt_times_are_the_truth(self):
        v = probe_sync.verdict(first_cue=1.0, silence=None, intro=0.0)
        self.assertIn("No leading pad", v)

    def test_codec_padding_is_not_an_intro(self):
        v = probe_sync.verdict(first_cue=1.0, silence=0.02, intro=2.15)
        self.assertIn("No leading pad", v)

    def test_missing_srt_says_so(self):
        self.assertIn("No timecode", probe_sync.verdict(None, 2.1, 2.15))


class TestIntroOffset(unittest.TestCase):
    def test_no_intro_configured_is_zero(self):
        with patch("video.channel_intro.resolve_intro_path", return_value=None):
            self.assertEqual(probe_sync.intro_offset_seconds("tapin"), 0.0)

    def test_uses_the_probed_duration(self):
        with (
            patch("video.channel_intro.resolve_intro_path", return_value="intro.mp4"),
            patch("video.channel_intro._probe_duration", return_value=2.15),
        ):
            self.assertAlmostEqual(probe_sync.intro_offset_seconds("tapin"), 2.15, places=3)

    def test_probe_failure_is_not_fatal(self):
        with patch("video.channel_intro.resolve_intro_path", side_effect=OSError("boom")):
            self.assertEqual(probe_sync.intro_offset_seconds("tapin"), 0.0)


class TestNewestRender(unittest.TestCase):
    def test_skips_the_intro_asset(self):
        import os
        import shutil
        import tempfile

        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        for name in ("channel_intro.mp4", "real_render.mp4"):
            with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                fh.write("x")
        newest = probe_sync.newest_render(tmp)
        self.assertIsNotNone(newest)
        self.assertIn("real_render", newest)


if __name__ == "__main__":
    unittest.main()
