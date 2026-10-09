"""#1010: a chosen chapter cannot go missing.

Run 120: five angles chosen at Extended; the script stopped inside chapter 4 at 1,010 words
with no closer, chapter 5 ("legal gray zone") was never written, the description listed four
chapters and the Shorts list offered chapter 4 at "0:06 fits". Measured cause: the trim pass
(`core/content_engine.py`) capped the script at `tts_char_cap.max_chars()` - 5,000 characters,
the Long ceiling - instead of the Extended ceiling `effective_cap(length_choice=)` (12,000), and
`trim_overlength` dropped sentences from the end down to the 1,000-word floor, closer first.
The chapter locator then placed the unwritten chapter on a late sentence anyway.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

ANGLES = [
    "Modders are already blending games with AI",
    "Why studios quietly tolerate AI mods",
    "The tools making cross-game mods possible",
    "What players actually want from AI mods",
    "The legal gray zone nobody has settled",
]


def _chapter(topic: str, n: int, words: int = 10) -> list[str]:
    filler = " ".join(["detail"] * (words - 4))
    return [f"{topic} point {i} {filler}." for i in range(n)]


def _script(chapters: int = 5, per: int = 28) -> str:
    keys = ["Modders blending", "Studios tolerate", "Tools cross-game", "Players want",
            "Legal gray zone"]  # fmt: skip
    parts: list[str] = []
    for i in range(chapters):
        parts.extend(_chapter(keys[i], per))
    parts.append("That is the whole fight, and the next patch decides it.")
    return " ".join(parts)


class TrimCapTests(unittest.TestCase):
    def test_extended_is_trimmed_against_the_extended_ceiling(self):
        from core.content_engine import _trim_to_cap

        script = _script()
        self.assertGreater(len(script), 5000)  # over the Long ceiling, under Extended's
        env = {"SCRIPT_TRIM": "true", "TTS_MAX_CHARS": "5000"}
        with patch.dict(os.environ, env):
            out, removed = _trim_to_cap(script, max_words=2000, min_words=1000, length_choice="4")
        self.assertEqual(removed, 0)
        self.assertIn("Legal gray zone", out)
        self.assertTrue(out.endswith("the next patch decides it."))

    def test_long_keeps_the_long_ceiling(self):
        from core.content_engine import _trim_to_cap

        script = _script()
        with patch.dict(os.environ, {"SCRIPT_TRIM": "true", "TTS_MAX_CHARS": "5000"}):
            out, removed = _trim_to_cap(script, max_words=2000, min_words=100, length_choice="3")
        self.assertGreater(removed, 0)
        self.assertLessEqual(len(out), 5000)


class TrimKeepsCloserTests(unittest.TestCase):
    def test_the_last_sentence_survives_a_trim(self):
        from core.script_length import trim_overlength

        script = (
            "Hook line with a fact. Second point about the team. Third point about the coach. "
            "Fourth point about the schedule. Closer: watch Sunday."
        )
        with patch.dict(os.environ, {"SCRIPT_TRIM": "true"}):
            out, removed = trim_overlength(script, max_words=15, min_words=5)
        self.assertGreater(removed, 0)
        self.assertTrue(out.startswith("Hook line"))
        self.assertTrue(out.endswith("Closer: watch Sunday."), out)


class UncoveredAngleTests(unittest.TestCase):
    def test_an_unwritten_last_chapter_is_found(self):
        from core.angle_chapters import uncovered_angles

        self.assertEqual(uncovered_angles(_script(chapters=4), ANGLES), [4])
        self.assertEqual(uncovered_angles(_script(chapters=5), ANGLES), [])

    def test_the_opening_chapter_is_never_missing(self):
        from core.angle_chapters import uncovered_angles

        self.assertNotIn(0, uncovered_angles("Nothing about any of it.", ANGLES))


class MissingChapterPassTests(unittest.TestCase):
    FACTS = "VERIFIED FACTS:\n- Modders blend games with AI.\n- The legal gray zone is unsettled."

    def _run(self, reply):
        from core import content_engine as ce

        with patch.object(ce, "complete_json", return_value=reply):
            return ce._write_missing_chapters(
                _script(chapters=4),
                ANGLES,
                topic="AI game mods",
                max_words=2000,
                length_choice="4",
                grounding_text=self.FACTS,
                ungrounded=[],
            )

    def test_the_missing_chapter_is_written_before_the_closer(self):
        base = _script(chapters=4)
        body, closer = base.rsplit(". ", 1)
        added = "The legal gray zone is unsettled, and nobody has tested it in court yet."
        script, ungrounded, extra = self._run({"script": f"{body}. {added} {closer}"})
        self.assertIn("legal gray zone", script)
        self.assertEqual(extra["missing"], [5])
        self.assertTrue(extra["written"])
        self.assertEqual(ungrounded, [])

    def test_a_rewrite_that_invents_a_name_is_refused(self):
        base = _script(chapters=4)
        added = "Legal gray zone: Judge Ramirez ruled for Nintendo in Ohio last week."
        script, _u, extra = self._run({"script": f"{base} {added}"})
        self.assertEqual(script, base)
        self.assertFalse(extra["written"])

    def test_nothing_missing_makes_no_call(self):
        from core import content_engine as ce

        with patch.object(ce, "complete_json") as call:
            _script_out, _u, extra = ce._write_missing_chapters(
                _script(),
                ANGLES,
                topic="AI game mods",
                max_words=2000,
                length_choice="4",
                grounding_text=self.FACTS,
                ungrounded=[],
            )
        call.assert_not_called()
        self.assertEqual(extra["missing"], [])


class LocatorTests(unittest.TestCase):
    def test_an_angle_the_model_says_is_absent_gets_no_chapter(self):
        from core.angle_chapters import locate_chapters

        script = _script(chapters=4)
        starts = ["Modders blending point 0", "Studios tolerate point 0",
                  "Tools cross-game point 0", "Players want point 0", ""]  # fmt: skip
        with patch("core.llm_router.complete_json", return_value={"starts": starts}):
            chapters = locate_chapters(script, ANGLES)
        self.assertEqual([c.angle for c in chapters], ANGLES[:4])
        self.assertEqual({c.placed_by for c in chapters}, {"llm"})

    def test_a_chapter_too_short_to_be_a_section_is_folded_back(self):
        from core.angle_chapters import AngleChapter, drop_thin_chapters

        script = _script(chapters=4)
        last = script.index("That is the whole fight")
        chapters = [
            AngleChapter(0, "a", "a", 0, 0),
            AngleChapter(1, "b", "b", 0, script.index("Studios tolerate")),
            AngleChapter(2, "c", "c", 0, script.index("Tools cross-game")),
            AngleChapter(3, "d", "d", 0, script.index("Players want")),
            AngleChapter(4, "e", "e", 0, last),
        ]
        kept, dropped = drop_thin_chapters(script, chapters)
        self.assertEqual([c.title for c in kept], ["a", "b", "c", "d"])
        self.assertEqual([c.title for c in dropped], ["e"])


class CardLineTests(unittest.TestCase):
    def test_the_run_card_names_a_chapter_left_out(self):
        from core.angle_chapters import chapter_card_lines

        lines = chapter_card_lines(
            {
                "chapters_written": {"missing": [5], "written": False},
                "chapters_missing": ["The legal gray zone nobody has settled"],
            }
        )
        self.assertEqual(
            lines,
            ["Chapter not written, left out of the chapter list: "
             "The legal gray zone nobody has settled"],
        )  # fmt: skip
        self.assertIn("written from the facts",
                      chapter_card_lines({"chapters_written": {"missing": [5], "written": True}})[0])  # fmt: skip
        self.assertEqual(chapter_card_lines({}), [])


class ShortsMinimumTests(unittest.TestCase):
    def test_a_six_second_chapter_is_not_a_short(self):
        from core.chapter_shorts import SHORTS_MIN_SECONDS, ChapterSpan

        self.assertEqual(SHORTS_MIN_SECONDS, 20.0)
        self.assertFalse(ChapterSpan(3, "t", "a", 100.0, 106.0, "x").fits_shorts)
        self.assertTrue(ChapterSpan(3, "t", "a", 100.0, 140.0, "x").fits_shorts)

    def test_the_report_says_why(self):
        from core.angle_chapters import AngleChapter
        from core.chapter_shorts import ChapterSpan, chapter_report_lines

        lines = chapter_report_lines(
            [AngleChapter(0, "Short one", "a", 0, 0, "llm")],
            [ChapterSpan(0, "Short one", "a", 0.0, 6.0, "x")],
        )
        self.assertIn("under the 0:20 Shorts minimum", lines[0])


if __name__ == "__main__":
    unittest.main()
