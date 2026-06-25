"""Tests for word-level caption timing (video/caption_timing) + TTS sidecar."""

import base64
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock

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
