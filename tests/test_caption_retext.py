"""Captions take timing from whisper and text from the script.

The defect this closes is on disk in two halves: `output/samples/piper_lessac_run65.srt`
(what whisper heard) beside the ElevenLabs `.words.json` sidecar for the same script
(what was actually said). The fixtures below are those two texts, verbatim — including
the fused `win—is` token the real script carries.

Pure and offline (tests/CLAUDE.md): no model, no audio, no network.
"""

import unittest
from unittest.mock import patch

from video.caption_retext import (
    matched_pairs,
    normalize_token,
    retext_words_from_script,
)


def _asr(text: str, *, start: float = 0.0, per_word: float = 0.4) -> list[dict]:
    """Evenly-spaced word segments in the shape `caption_align` returns."""
    words = []
    clock = start
    for token in text.split():
        words.append({"word": token, "start": round(clock, 3), "end": round(clock + per_word, 3)})
        clock += per_word
    return words


def _text(words: list[dict]) -> str:
    return " ".join(w["word"] for w in words)


class TestRun65Regression(unittest.TestCase):
    """The names that stopped the last wave: 'Salkal', 'Mattius Gamarat', 'Quill and'."""

    SCRIPT = (
        "Salkilld jumps to 10 after one win—is the system broken? "
        "Quillan Salkilld just submitted Mateusz Gamrot in round one, and the UFC "
        "rewarded him with a top-10 lightweight ranking."
    )
    HEARD = (
        "Salkal jumps to ten after one win is the system broken, Quill and Salkal just "
        "submitted Mattius Gamarat and round one, and UFC rewarded him with a top ten "
        "lightweight ranking."
    )

    def setUp(self):
        self.words = retext_words_from_script(_asr(self.HEARD), self.SCRIPT)

    def test_the_mangled_names_are_gone(self):
        out = _text(self.words)
        for wrong in ("Salkal", "Mattius", "Gamarat", "Quill and"):
            self.assertNotIn(wrong, out)

    def test_the_real_names_are_there(self):
        out = _text(self.words)
        for right in ("Salkilld", "Quillan Salkilld", "Mateusz Gamrot", "top-10"):
            self.assertIn(right, out)

    def test_every_script_word_survives_exactly_once(self):
        from core.utils import clean_script_for_tts

        self.assertEqual([w["word"] for w in self.words], clean_script_for_tts(self.SCRIPT).split())

    def test_timings_stay_inside_the_transcript_span(self):
        heard = _asr(self.HEARD)
        starts = [w["start"] for w in self.words]
        self.assertTrue(all(s is not None for s in starts))
        self.assertGreaterEqual(starts[0], heard[0]["start"])
        self.assertLessEqual(self.words[-1]["end"], heard[-1]["end"] + 0.001)

    def test_time_never_runs_backwards(self):
        starts = [w["start"] for w in self.words]
        self.assertEqual(starts, sorted(starts))

    def test_the_split_name_lands_on_the_right_span(self):
        # "Quillan Salkilld" (2 script words) shares the span of "Quill and Salkal" (3),
        # which is the whole reason a positional zip cannot work here.
        heard = _asr(self.HEARD)
        self.assertEqual(self.words[10]["word"], "Quillan")
        self.assertEqual(self.words[11]["word"], "Salkilld")
        self.assertEqual((heard[11]["word"], heard[13]["word"]), ("Quill", "Salkal"))
        self.assertAlmostEqual(self.words[10]["start"], heard[11]["start"], places=3)
        self.assertAlmostEqual(self.words[11]["end"], heard[13]["end"], places=3)

    def test_punctuation_comes_from_the_script(self):
        # Whisper wrote "broken," — the script asks a question, and caption line breaks
        # key off sentence-end punctuation.
        self.assertIn("broken?", _text(self.words))


class TestNumberWords(unittest.TestCase):
    """Whisper writes numerals as words; this channel is made of rankings and rounds."""

    def test_digits_and_words_normalize_together(self):
        self.assertEqual(normalize_token("10"), normalize_token("ten"))
        self.assertEqual(normalize_token("One,"), normalize_token("1"))

    def test_a_numeral_keeps_the_spoken_words_timing(self):
        heard = _asr("he is ranked ten now")
        out = retext_words_from_script(heard, "He is ranked 10 now.")
        self.assertEqual([w["word"] for w in out], ["He", "is", "ranked", "10", "now."])
        self.assertAlmostEqual(out[3]["start"], heard[3]["start"], places=3)

    def test_hyphenated_numeral_absorbs_two_spoken_words(self):
        heard = _asr("a top ten fighter")
        out = retext_words_from_script(heard, "a top-10 fighter")
        self.assertEqual([w["word"] for w in out], ["a", "top-10", "fighter"])
        self.assertAlmostEqual(out[1]["start"], heard[1]["start"], places=3)
        self.assertAlmostEqual(out[1]["end"], heard[2]["end"], places=3)


class TestMissingAndInventedWords(unittest.TestCase):
    def test_a_word_whisper_dropped_still_gets_a_time(self):
        heard = _asr("alpha bravo delta echo")  # "charlie" never transcribed
        out = retext_words_from_script(heard, "alpha bravo charlie delta echo")
        self.assertEqual([w["word"] for w in out], ["alpha", "bravo", "charlie", "delta", "echo"])
        charlie = out[2]
        self.assertIsNotNone(charlie["start"])
        self.assertGreaterEqual(charlie["start"], out[1]["start"])
        self.assertLessEqual(charlie["start"], out[3]["start"])

    def test_a_word_whisper_invented_is_dropped(self):
        heard = _asr("alpha bravo umm charlie")
        out = retext_words_from_script(heard, "alpha bravo charlie")
        self.assertEqual([w["word"] for w in out], ["alpha", "bravo", "charlie"])

    def test_a_dropped_run_at_the_end_still_gets_times(self):
        # No later word to interpolate towards — the run extends past the last known end.
        heard = _asr("alpha bravo charlie delta echo foxtrot")
        out = retext_words_from_script(heard, "alpha bravo charlie delta echo foxtrot golf hotel")
        self.assertTrue(all(w["start"] is not None for w in out))
        starts = [w["start"] for w in out]
        self.assertEqual(starts, sorted(starts))
        self.assertGreater(out[-1]["end"], heard[-1]["end"])

    def test_a_dropped_run_at_the_start_still_gets_times(self):
        # No earlier word to interpolate from — the run backs off the first known start.
        heard = _asr("charlie delta echo foxtrot golf hotel", start=2.0)
        out = retext_words_from_script(heard, "alpha bravo charlie delta echo foxtrot golf hotel")
        self.assertTrue(all(w["start"] is not None for w in out))
        self.assertGreaterEqual(out[0]["start"], 0.0)
        self.assertLessEqual(out[0]["start"], out[2]["start"])


class TestExactTranscript(unittest.TestCase):
    def test_timings_are_passed_through_untouched(self):
        heard = _asr("the system is broken today")
        out = retext_words_from_script(heard, "the system is broken today")
        self.assertEqual(
            [(w["word"], w["start"], w["end"]) for w in out],
            [(w["word"], w["start"], w["end"]) for w in heard],
        )


class TestDeclinesRatherThanGuesses(unittest.TestCase):
    def test_an_unrelated_transcript_returns_none(self):
        heard = _asr("completely different audio about something else entirely")
        self.assertIsNone(
            retext_words_from_script(heard, "Rockstar delayed GTA VI again this morning.")
        )

    def test_the_threshold_is_configurable(self):
        heard = _asr("alpha bravo zulu yankee")  # 2 of 4 match = 0.5
        script = "alpha bravo charlie delta"
        with patch.dict("os.environ", {"CAPTION_RETEXT_MIN_MATCH": "0.9"}, clear=False):
            self.assertIsNone(retext_words_from_script(heard, script))
        with patch.dict("os.environ", {"CAPTION_RETEXT_MIN_MATCH": "0.4"}, clear=False):
            self.assertIsNotNone(retext_words_from_script(heard, script))

    def test_a_junk_threshold_falls_back_to_the_default(self):
        heard = _asr("alpha bravo charlie")
        with patch.dict("os.environ", {"CAPTION_RETEXT_MIN_MATCH": "banana"}, clear=False):
            self.assertIsNotNone(retext_words_from_script(heard, "alpha bravo charlie"))


class TestEscapeHatches(unittest.TestCase):
    def test_no_script_means_no_change(self):
        heard = _asr("whatever was heard")
        self.assertEqual(retext_words_from_script(heard, ""), heard)
        self.assertEqual(retext_words_from_script(heard, "   "), heard)

    def test_off_switch_keeps_raw_asr(self):
        heard = _asr("Salkal jumps")
        with patch.dict("os.environ", {"CAPTION_RETEXT": "off"}, clear=False):
            self.assertEqual(retext_words_from_script(heard, "Salkilld jumps"), heard)

    def test_no_words_returns_none(self):
        self.assertIsNone(retext_words_from_script([], "a script"))
        self.assertIsNone(retext_words_from_script([{"word": "  "}], "a script"))

    def test_markdown_is_stripped_the_same_way_tts_strips_it(self):
        # generate_audio runs clean_script_for_tts, so captions must align to that text.
        heard = _asr("the big reveal")
        out = retext_words_from_script(heard, "the **big** reveal")
        self.assertEqual([w["word"] for w in out], ["the", "big", "reveal"])


class TestMatchedPairs(unittest.TestCase):
    """The shared matcher — `scripts/bench_caption_align.py` measures with this too."""

    def test_pairs_survive_an_insertion(self):
        pairs = matched_pairs(["alpha", "bravo", "charlie"], ["alpha", "umm", "bravo", "charlie"])
        self.assertEqual(pairs, [(0, 0), (1, 2), (2, 3)])

    def test_pairs_survive_a_deletion(self):
        pairs = matched_pairs(["alpha", "bravo", "charlie"], ["alpha", "charlie"])
        self.assertEqual(pairs, [(0, 0), (2, 1)])

    def test_nothing_in_common_pairs_nothing(self):
        self.assertEqual(matched_pairs(["alpha"], ["zulu"]), [])


if __name__ == "__main__":
    unittest.main()
