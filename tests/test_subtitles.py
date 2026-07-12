"""Tests for caption (SRT) generation (Phase Q)."""

import json
import os
import shutil
import tempfile
import unittest
from typing import ClassVar
from unittest.mock import patch

from video import subtitles
from video.subtitles import (
    build_srt,
    format_timestamp,
    generate_subtitle_file,
    split_script_into_lines,
)


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


class TestWordTimedCaptions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.audio = os.path.join(self.tmp, "out.mp3")
        words = [
            {"word": "Real", "start": 0.0, "end": 0.5},
            {"word": "timing.", "start": 0.5, "end": 1.1},
        ]
        with open(self.audio + ".words.json", "w", encoding="utf-8") as f:
            json.dump(words, f)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_karaoke_ass_from_sidecar(self):
        with patch.dict("os.environ", {"CAPTION_STYLE": "karaoke"}, clear=False):
            path = generate_subtitle_file("Real timing.", 5.0, audio_path=self.audio)
        self.assertTrue(path.endswith(".ass"))
        with open(path, encoding="utf-8") as f:
            self.assertIn("{\\k", f.read())

    def test_accurate_srt_from_sidecar(self):
        with patch.dict("os.environ", {"CAPTION_STYLE": "word"}, clear=False):
            path = generate_subtitle_file("Real timing.", 5.0, audio_path=self.audio)
        self.assertTrue(path.endswith(".srt"))
        with open(path, encoding="utf-8") as f:
            self.assertIn("00:00:00,000 --> 00:00:01,100", f.read())

    def test_falls_back_to_proportional_without_sidecar(self):
        with patch.dict("os.environ", {"CAPTION_STYLE": "karaoke"}, clear=False):
            path = generate_subtitle_file("no sidecar here", 5.0, audio_path=self.audio + "x")
        self.assertTrue(path.endswith(".srt"))  # plain proportional SRT

    def test_load_word_timings_missing(self):
        self.assertIsNone(subtitles._load_word_timings(None))
        self.assertIsNone(subtitles._load_word_timings(self.audio + "x"))


class TestWhisperAlignedCaptions(unittest.TestCase):
    """No ElevenLabs sidecar + CAPTION_ALIGN_BACKEND set → whisper word timings
    feed the same SRT/ASS builders; any miss falls back to proportional."""

    ENV: ClassVar[dict[str, str]] = {"CAPTION_ALIGN_BACKEND": "whisperx"}

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.audio = os.path.join(self.tmp, "local_tts.mp3")  # no .words.json sidecar

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _aligned(self):
        from core.providers import ProviderResult

        return ProviderResult.success(
            "caption_align",
            "whisperx",
            data=[
                {"word": "Real", "start": 0.0, "end": 0.5, "score": 0.99},
                {"word": "timing.", "start": 0.5, "end": 1.1, "score": 0.97},
            ],
        )

    def test_accurate_srt_from_whisper_when_sidecar_absent(self):
        env = {"CAPTION_STYLE": "word", **self.ENV}
        with (
            patch.dict("os.environ", env, clear=False),
            patch(
                "core.caption_align.transcribe_and_align", return_value=self._aligned()
            ) as mock_align,
        ):
            path = generate_subtitle_file("Real timing.", 5.0, audio_path=self.audio)
        mock_align.assert_called_once_with(self.audio)
        self.assertTrue(path.endswith(".srt"))
        with open(path, encoding="utf-8") as f:
            self.assertIn("00:00:00,000 --> 00:00:01,100", f.read())

    def test_karaoke_ass_from_whisper_when_sidecar_absent(self):
        env = {"CAPTION_STYLE": "karaoke", **self.ENV}
        with (
            patch.dict("os.environ", env, clear=False),
            patch("core.caption_align.transcribe_and_align", return_value=self._aligned()),
        ):
            path = generate_subtitle_file("Real timing.", 5.0, audio_path=self.audio)
        self.assertTrue(path.endswith(".ass"))
        with open(path, encoding="utf-8") as f:
            self.assertIn("{\\k", f.read())

    def test_sidecar_takes_precedence_over_whisper(self):
        with open(self.audio + ".words.json", "w", encoding="utf-8") as f:
            json.dump([{"word": "Sidecar", "start": 0.0, "end": 0.7}], f)
        env = {"CAPTION_STYLE": "word", **self.ENV}
        with (
            patch.dict("os.environ", env, clear=False),
            patch("core.caption_align.transcribe_and_align") as mock_align,
        ):
            path = generate_subtitle_file("Sidecar", 5.0, audio_path=self.audio)
        mock_align.assert_not_called()
        with open(path, encoding="utf-8") as f:
            self.assertIn("Sidecar", f.read())

    def test_proportional_fallback_when_backend_unset(self):
        with patch.dict("os.environ", {"CAPTION_STYLE": "word"}, clear=False):
            os.environ.pop("CAPTION_ALIGN_BACKEND", None)
            with patch("core.caption_align.transcribe_and_align") as mock_align:
                path = generate_subtitle_file("no sidecar no backend", 5.0, audio_path=self.audio)
        mock_align.assert_not_called()
        self.assertTrue(path.endswith(".srt"))
        with open(path, encoding="utf-8") as f:
            self.assertIn("--> 00:00:05,000", f.read())  # proportional: ends at duration

    def test_proportional_fallback_when_alignment_fails(self):
        from core.providers import ProviderResult

        env = {"CAPTION_STYLE": "word", **self.ENV}
        with (
            patch.dict("os.environ", env, clear=False),
            patch(
                "core.caption_align.transcribe_and_align",
                return_value=ProviderResult.fail_open("caption_align", "whisperx not installed"),
            ),
        ):
            path = generate_subtitle_file("backend fell over", 5.0, audio_path=self.audio)
        self.assertTrue(path.endswith(".srt"))
        with open(path, encoding="utf-8") as f:
            self.assertIn("--> 00:00:05,000", f.read())

    def test_plain_style_never_calls_whisper(self):
        env = {"CAPTION_STYLE": "plain", **self.ENV}
        with (
            patch.dict("os.environ", env, clear=False),
            patch("core.caption_align.transcribe_and_align") as mock_align,
        ):
            path = generate_subtitle_file("plain style", 5.0, audio_path=self.audio)
        mock_align.assert_not_called()
        self.assertTrue(path.endswith(".srt"))


if __name__ == "__main__":
    unittest.main()
