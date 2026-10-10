"""#1007 — an award race stays a race, and the brief names that year's contenders."""

from __future__ import annotations

import unittest

from apis.topic_variants import AWARD_FRAMES, award_contender_facts, frames_for

_GOTY = "Game of the year 2027 predictions"
_RELEASES = [
    {"name": "GTA VI", "released": "2027-03-12"},
    {"name": "Wolverine", "released": "2026-11-01"},
    {"name": "The 1994 one", "released": "1994-01-01"},
]


class AwardRaceTests(unittest.TestCase):
    def test_an_award_topic_gets_contender_frames_not_one_game(self) -> None:
        frames = frames_for(_GOTY, "default")
        self.assertEqual(frames, AWARD_FRAMES)
        self.assertIn("the_contenders", frames)
        self.assertNotIn("patch_or_update_hook", frames)
        for phrase in (
            "GOTY 2027",
            "The Game Awards 2027",
            "MVP race 2027",
            "Ballon d'Or 2026",
            "Rookie of the Year 2027",
        ):
            self.assertEqual(frames_for(phrase, "default"), AWARD_FRAMES, phrase)

    def test_a_named_take_still_uses_the_take_table(self) -> None:
        self.assertIsNone(frames_for("GOTY hot take", "take"))

    def test_the_brief_lists_that_years_releases(self) -> None:
        lines = award_contender_facts(_GOTY, _RELEASES)
        self.assertEqual(lines, ["GTA VI released 2027-03-12 (RAWG)"])
        self.assertEqual(award_contender_facts("Chargers week 5", _RELEASES), [])
