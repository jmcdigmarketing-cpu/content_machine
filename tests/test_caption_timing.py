"""Tests for word-level caption timing (video/caption_timing) + TTS sidecar."""

import base64
import json
import os
import shutil
import tempfile
import unittest
from typing import ClassVar
from unittest.mock import MagicMock, patch

from core.providers import ProviderResult
from video import caption_timing as ct


def _words():
    return [
        {"word": "One", "start": 0.0, "end": 0.4},
        {"word": "two.", "start": 0.4, "end": 0.9},
        {"word": "Three", "start": 0.9, "end": 1.3},
        {"word": "four", "start": 1.3, "end": 1.7},
        {"word": "five", "start": 1.7, "end": 2.1},
    ]


class TestWordsFromAlignment(unittest.TestCase):
    def test_groups_chars_into_words(self):
        chars = ["H", "i", " ", "b", "y", "e"]
        starts = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
        ends = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
        words = ct.words_from_alignment(chars, starts, ends)
        self.assertEqual([w["word"] for w in words], ["Hi", "bye"])
        self.assertAlmostEqual(words[0]["start"], 0.0)
        self.assertAlmostEqual(words[0]["end"], 0.2)
        self.assertAlmostEqual(words[1]["start"], 0.3)


class TestGrouping(unittest.TestCase):
    def test_breaks_on_sentence_end_and_length(self):
        lines = ct.group_into_lines(_words(), max_words=3)
        # "two." ends a sentence → first line is [One, two.]
        self.assertEqual([w["word"] for w in lines[0]], ["One", "two."])
        self.assertEqual([w["word"] for w in lines[1]], ["Three", "four", "five"])


class TestSrt(unittest.TestCase):
    def test_uses_real_timestamps(self):
        srt = ct.build_srt_from_words(_words(), max_words=3)
        self.assertIn("00:00:00,000 --> 00:00:00,900", srt)
        self.assertIn("One two.", srt)
        self.assertIn("Three four five", srt)

    def test_none_word_timing_does_not_collapse_block(self):
        # whisper can drop the last word's end time — the cue must still have span,
        # not collapse to a zero/negative-duration block at the line start.
        line = [
            {"word": "hello", "start": 1.0, "end": 1.4},
            {"word": "world", "start": 1.4, "end": None},
        ]
        start, end = ct._line_span(line)
        self.assertEqual(start, 1.0)
        self.assertGreater(end, start)


class TestAss(unittest.TestCase):
    def test_karaoke_tags_and_header(self):
        ass = ct.build_ass_karaoke(_words(), max_words=2)
        self.assertIn("[V4+ Styles]", ass)
        self.assertIn("Dialogue:", ass)
        self.assertIn("{\\k", ass)  # per-word karaoke timing

    def test_escapes_braces_in_words(self):
        ass = ct.build_ass_karaoke([{"word": "a{b}c", "start": 0.0, "end": 0.2}], max_words=2)
        self.assertNotIn("a{b}c", ass)
        self.assertIn("a(b)c", ass)


class TestWordsFromCaptionAlign(unittest.TestCase):
    """Wiring of the whisper alignment seam (core/caption_align) — fail-open."""

    ENV: ClassVar[dict[str, str]] = {"CAPTION_ALIGN_BACKEND": "whisperx"}

    def _success(self, data):
        return ProviderResult.success("caption_align", "whisperx", data=data)

    def test_converts_word_segments_when_backend_ok(self):
        segments = [
            {"word": " Hello", "start": 0.0, "end": 0.4, "score": 0.98},
            {"word": "world.", "start": 0.5, "end": 1.1, "score": 0.95},
        ]
        with (
            patch.dict(os.environ, self.ENV, clear=False),
            patch(
                "core.caption_align.transcribe_and_align", return_value=self._success(segments)
            ) as mock_align,
        ):
            words = ct.words_from_caption_align("audio.mp3")
        mock_align.assert_called_once_with("audio.mp3")
        self.assertEqual(
            words,
            [
                {"word": "Hello", "start": 0.0, "end": 0.4},
                {"word": "world.", "start": 0.5, "end": 1.1},
            ],
        )

    def test_keeps_untimed_words_and_skips_empty(self):
        segments = [
            {"word": "Top", "start": 0.0, "end": 0.3},
            {"word": "5", "score": 0.0},  # whisperx leaves numerals untimed
            {"word": "  ", "start": 0.4, "end": 0.5},  # no text → dropped
            {"word": "picks", "start": "bad", "end": 0.9},  # garbage start → None
            "not-a-dict",
        ]
        with (
            patch.dict(os.environ, self.ENV, clear=False),
            patch("core.caption_align.transcribe_and_align", return_value=self._success(segments)),
        ):
            words = ct.words_from_caption_align("audio.mp3")
        self.assertEqual(
            words,
            [
                {"word": "Top", "start": 0.0, "end": 0.3},
                {"word": "5", "start": None, "end": None},
                {"word": "picks", "start": None, "end": 0.9},
            ],
        )

    def test_none_when_backend_unset_and_backend_not_called(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CAPTION_ALIGN_BACKEND", None)
            with patch("core.caption_align.transcribe_and_align") as mock_align:
                self.assertIsNone(ct.words_from_caption_align("audio.mp3"))
        mock_align.assert_not_called()

    def test_none_on_fail_open_result(self):
        with (
            patch.dict(os.environ, self.ENV, clear=False),
            patch(
                "core.caption_align.transcribe_and_align",
                return_value=ProviderResult.fail_open("caption_align", "no whisperx"),
            ),
        ):
            self.assertIsNone(ct.words_from_caption_align("audio.mp3"))

    def test_none_on_empty_or_malformed_data(self):
        for data in ([], "oops", None, [{"word": ""}]):
            with (
                patch.dict(os.environ, self.ENV, clear=False),
                patch("core.caption_align.transcribe_and_align", return_value=self._success(data)),
            ):
                self.assertIsNone(ct.words_from_caption_align("audio.mp3"))

    def test_never_raises_when_backend_raises(self):
        with (
            patch.dict(os.environ, self.ENV, clear=False),
            patch("core.caption_align.transcribe_and_align", side_effect=RuntimeError("boom")),
        ):
            self.assertIsNone(ct.words_from_caption_align("audio.mp3"))

    def test_none_for_missing_audio_path(self):
        self.assertIsNone(ct.words_from_caption_align(None))
        self.assertIsNone(ct.words_from_caption_align(""))


class TestTtsSidecar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "out.mp3")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _client(self):
        align = MagicMock()
        align.characters = ["H", "i"]
        align.character_start_times_seconds = [0.0, 0.1]
        align.character_end_times_seconds = [0.1, 0.2]
        result = MagicMock()
        result.audio_base_64 = base64.b64encode(b"AUDIO").decode()
        result.alignment = align
        client = MagicMock()
        client.text_to_speech.convert_with_timestamps.return_value = result
        return client

    def test_writes_audio_and_sidecar(self):
        from core import tts

        ok = tts._save_word_timestamps(self._client(), "v", "m", "Hi", self.path)
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(self.path))
        with open(tts.word_timing_path(self.path), encoding="utf-8") as f:
            words = json.load(f)
        self.assertEqual(words[0]["word"], "Hi")

    def test_falls_back_on_error(self):
        from core import tts

        client = MagicMock()
        client.text_to_speech.convert_with_timestamps.side_effect = RuntimeError("no timestamps")
        ok = tts._save_word_timestamps(client, "v", "m", "Hi", self.path)
        self.assertFalse(ok)
        self.assertFalse(os.path.exists(self.path))  # nothing written → caller falls back


if __name__ == "__main__":
    unittest.main()
