"""#1025: a game's release date is stated against today.

Verified first: the RAWG line already carried "released 2026-11-19". What it did not say is
which side of today that is. A script written from "released 2026-11-19" on 2026-10-10 can
call an unreleased game out, and one written from "released 2013-09-17" can call it new. The
line now does the arithmetic the model gets wrong (#551's rule, for release dates).
"""

from __future__ import annotations

import unittest
from unittest.mock import patch


def _facts(released, name="Grand Theft Auto VI"):
    from core import signal_facts

    signals = {
        "rawg": {"connected": True, "active": True, "data": [{"name": name, "released": released}]}
    }
    with patch.object(signal_facts, "_today", return_value="2026-10-10"):
        return signal_facts.format_signal_facts(signals)


class ReleaseNoteTests(unittest.TestCase):
    def _note(self, released):
        from core.signal_facts import release_note

        return release_note(released, "2026-10-10")

    def test_a_future_date_is_not_out_yet(self):
        note = self._note("2026-11-19")
        self.assertIn("releases 2026-11-19", note)
        self.assertIn("in 40 days", note)
        self.assertIn("NOT out yet", note)

    def test_a_recent_release_counts_the_days(self):
        self.assertEqual(self._note("2026-09-30"), "released 2026-09-30 (10 days ago)")
        self.assertEqual(self._note("2026-10-10"), "released 2026-10-10 (today)")
        self.assertEqual(self._note("2026-10-09"), "released 2026-10-09 (1 day ago)")

    def test_an_old_release_counts_the_years(self):
        self.assertEqual(self._note("2013-09-17"), "released 2013-09-17 (13 years ago)")
        self.assertEqual(self._note("2026-03-01"), "released 2026-03-01 (7 months ago)")

    def test_an_unreadable_date_is_passed_through(self):
        self.assertEqual(self._note("TBA"), "released TBA")
        self.assertEqual(self._note(""), "")


class RawgLineTests(unittest.TestCase):
    def test_the_fact_line_says_it_is_not_out(self):
        text = _facts("2026-11-19")
        self.assertIn("RAWG: Grand Theft Auto VI", text)
        self.assertIn("NOT out yet", text)

    def test_the_fact_line_dates_an_old_game(self):
        self.assertIn("13 years ago", _facts("2013-09-17", "Grand Theft Auto V"))


if __name__ == "__main__":
    unittest.main()
