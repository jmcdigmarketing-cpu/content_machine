"""#1009: chapter titles come from the chapter and are checked.

Run 119's YouTube description carried "2:21 UFC 305 adds Kamaru Usman vs Shavkat Rakhmonov
fantasy matchup hype" - no such booking exists and the script never says it. Measured cause:
`core/angle_chapters.locate_chapters` titled every chapter `angle_headline(angle)`, the text
written at the angle menu before any facts, and nothing checked it; `refine_run_chapters` and
the chapter Shorts reused the stored title. Now the locator's one call also returns a title
built from what each chapter says, and every candidate passes a check against its own section
(numbers and names it does not say, a past year predicted, a numbered event that happened).
The angle headline is the fallback, and a label from the chapter's first sentence the last.
"""

from __future__ import annotations

import datetime
import unittest
from unittest.mock import patch

TODAY = datetime.date(2026, 10, 9)
RUN_119_ANGLE = "UFC 305 adds Kamaru Usman vs Shavkat Rakhmonov fantasy matchup hype"
CH1 = (
    "Shavkat Rakhmonov has never lost a professional fight. He is 19-0, with eight knockouts "
    "and ten submissions, and the nineteenth win went the distance against Ian Machado Garry. "
    "That record is why every contender keeps finding a reason to be busy. "
)
CH2 = (
    "The welterweight belt is the only fight left that means anything for him. Belal Muhammad "
    "holds it, and the division has run out of excuses to keep Rakhmonov waiting. A title shot "
    "is the next step, and the numbers say he has earned it twice over by now."
)
SCRIPT = CH1 + CH2
ANGLES = ["Rakhmonov's perfect record explained", RUN_119_ANGLE]


class TitleProblemTests(unittest.TestCase):
    def test_run_119_chapter_title_is_refused(self):
        from core.angle_chapters import chapter_title_problem

        problem = chapter_title_problem(RUN_119_ANGLE, CH2, today=TODAY)
        self.assertTrue(problem)
        self.assertTrue("305" in problem or "Kamaru Usman" in problem, problem)

    def test_a_title_the_chapter_supports_passes(self):
        from core.angle_chapters import chapter_title_problem

        self.assertEqual(chapter_title_problem("Rakhmonov is 19-0", CH1, today=TODAY), "")
        self.assertEqual(
            chapter_title_problem("The Welterweight Belt Is Next", CH2, today=TODAY), ""
        )

    def test_title_case_alone_is_not_a_name(self):
        from core.angle_chapters import chapter_title_problem

        section = "The hype train for GTA 6 has never been bigger. Delivering is the real test."
        self.assertEqual(
            chapter_title_problem("GTA 6's Hype Train: Will It Crash or Deliver?", section), ""
        )

    def test_a_past_year_prediction_is_refused(self):
        from core.angle_chapters import chapter_title_problem

        section = "Modders already blend games with AI tools, and studios mostly look away."
        self.assertTrue(
            chapter_title_problem("AI will make mods obsolete by 2025", section, today=TODAY)
        )


class LocateTitleTests(unittest.TestCase):
    def _locate(self, payload):
        from core.angle_chapters import locate_chapters

        with (
            patch("core.llm_router.complete_json", **payload),
            patch("core.facts.event_dates._today", return_value=TODAY),
        ):
            return locate_chapters(SCRIPT, ANGLES)

    def test_the_title_comes_from_the_chapter(self):
        reply = {
            "starts": ["Shavkat Rakhmonov has never lost", "The welterweight belt is the only"],
            "titles": ["Why Rakhmonov is 19-0", "The belt is the only fight left"],
        }
        chapters = self._locate({"return_value": reply})
        self.assertEqual([c.title for c in chapters],
                         ["Why Rakhmonov is 19-0", "The belt is the only fight left"])  # fmt: skip
        self.assertEqual(chapters[1].title_source, "chapter")
        self.assertIn("not in the chapter", chapters[1].title_note)

    def test_a_model_title_that_invents_falls_back(self):
        reply = {
            "starts": ["Shavkat Rakhmonov has never lost", "The welterweight belt is the only"],
            "titles": ["Why Rakhmonov is 19-0", "Kamaru Usman calls out Rakhmonov"],
        }
        chapters = self._locate({"return_value": reply})
        self.assertNotIn("Usman", chapters[1].title)
        self.assertNotIn("305", chapters[1].title)
        self.assertEqual(chapters[1].title_source, "sentence")
        self.assertTrue(chapters[1].title.startswith("The welterweight belt"))

    def test_no_model_titles_keep_a_clean_angle_and_replace_a_bad_one(self):
        chapters = self._locate({"side_effect": RuntimeError("extract down")})
        self.assertEqual(chapters[0].title, "Rakhmonov's perfect record explained")
        self.assertEqual(chapters[0].title_source, "angle")
        self.assertNotIn("305", chapters[1].title)
        self.assertEqual(chapters[1].angle, RUN_119_ANGLE)

    def test_title_source_survives_storage_and_opener_trim(self):
        from core.angle_chapters import (
            chapters_from_features,
            features_from_chapters,
            trim_chapter_openers,
        )

        chapters = self._locate({"side_effect": RuntimeError("extract down")})
        back = chapters_from_features(features_from_chapters(chapters))
        self.assertEqual([c.title_source for c in back], [c.title_source for c in chapters])
        _script, trimmed, _notes = trim_chapter_openers("So " + SCRIPT, back)
        self.assertEqual([c.title_note for c in trimmed], [c.title_note for c in chapters])


class CardLineTests(unittest.TestCase):
    def test_the_run_card_says_a_chapter_was_retitled(self):
        from core.angle_chapters import chapter_card_lines

        lines = chapter_card_lines(
            {
                "angle_chapters": [
                    {"index": 1, "title": "The welterweight belt is next", "angle": RUN_119_ANGLE,
                     "title_source": "sentence",
                     "title_note": "'305' is not in the chapter"},
                ]
            }
        )  # fmt: skip
        self.assertEqual(len(lines), 1)
        self.assertIn("Chapter 2 retitled", lines[0])
        self.assertIn("305", lines[0])


if __name__ == "__main__":
    unittest.main()
