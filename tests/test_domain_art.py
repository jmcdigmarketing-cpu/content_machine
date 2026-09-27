"""#898: every topic domain has an art panel, and the franchise art matches whole words.

`core/ui._DOMAIN_ART` covered gaming, ufc, nba, nfl and finance, so a soccer, pop
culture, anime or music topic printed nothing. `_FRANCHISE_ART` held Mario alone, matched
by substring. The franchise keywords added here include "ufc 5" and "gta", which a
substring test would fire on "UFC 500" and inside other words.
"""

from __future__ import annotations

import os
import unicodedata
import unittest
from unittest.mock import patch


def _columns(line: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in line)


class DomainArtTests(unittest.TestCase):
    def test_every_domain_has_a_panel(self):
        from apis.topic_scorer import _LEARNED_PROFILES
        from core.ui import _DOMAIN_ART

        missing = sorted(set(_LEARNED_PROFILES) - {"neutral"} - set(_DOMAIN_ART))
        self.assertEqual(missing, [])

    def test_every_small_panel_fits_a_narrow_terminal(self):
        """Mario is a full-size piece loaded from `core/data/`; the inline panels are not."""
        from core import ui

        panels = [
            *ui._DOMAIN_ART.items(),
            ("gta", ui._GTA_ART),
            ("marvel rivals", ui._MARVEL_RIVALS_ART),
            ("madden", ui._MADDEN_ART),
            ("nba 2k", ui._NBA_2K_ART),
            ("ufc 5", ui._UFC_5_ART),
        ]
        for name, art in panels:
            with self.subTest(panel=name):
                self.assertTrue(art.strip())
                self.assertLessEqual(len(art.splitlines()), 8)
                self.assertLessEqual(max(_columns(line) for line in art.splitlines()), 30)

    def test_a_soccer_topic_prints_the_soccer_panel(self):
        from core.ui import _DOMAIN_ART, print_domain_art

        out: list[str] = []
        with patch.dict(os.environ, {"CONTENT_UI_ASCII": "true", "CONTENT_UI_COLOR": "false"}):
            print_domain_art(
                "gaming",
                topic="Premier League title race goes to the last day",
                print_fn=lambda *a: out.append(a[0] if a else ""),
            )
        self.assertEqual([line for line in out if line], _DOMAIN_ART["soccer"].splitlines())

    def test_nothing_prints_with_ascii_off(self):
        from core.ui import print_domain_art

        out: list[str] = []
        with patch.dict(os.environ, {"CONTENT_UI_ASCII": "false"}):
            print_domain_art(
                "gaming", topic="GTA 6 trailer 3 breakdown", print_fn=lambda *a: out.append(a)
            )
        self.assertEqual(out, [])


class FranchiseArtTests(unittest.TestCase):
    def _art(self, topic: str):
        from core.ui import _franchise_art_for

        found = _franchise_art_for(topic)
        return found[0] if found else None

    def test_each_franchise_has_its_own_art(self):
        from core import ui

        cases = {
            "GTA 6 trailer 3 breakdown": ui._GTA_ART,
            "Grand Theft Auto VI delay rumours": ui._GTA_ART,
            "Marvel Rivals season 4 tier list": ui._MARVEL_RIVALS_ART,
            "Madden 26 ratings reveal": ui._MADDEN_ART,
            "NBA 2K26 MyCareer changes": ui._NBA_2K_ART,
            "UFC 5 adds three fighters": ui._UFC_5_ART,
        }
        for topic, art in cases.items():
            with self.subTest(topic=topic):
                self.assertTrue(art)
                self.assertEqual(self._art(topic), art)

    def test_the_arts_are_distinct(self):
        from core import ui

        arts = [ui._GTA_ART, ui._MARVEL_RIVALS_ART, ui._MADDEN_ART, ui._NBA_2K_ART, ui._UFC_5_ART]
        self.assertEqual(len(set(arts)), len(arts))

    def test_ufc_500_is_not_the_ufc_5_game(self):
        self.assertIsNone(self._art("UFC 500 results"))

    def test_keywords_match_whole_words(self):
        self.assertIsNone(self._art("A maddening loss for the Bills"))
        self.assertIsNone(self._art("Agatha tops the streaming chart"))

    def test_mario_still_matches(self):
        from core import ui

        self.assertEqual(self._art("Super Mario Galaxy remaster"), ui._SUPER_MARIO_GALAXY)


if __name__ == "__main__":
    unittest.main()
