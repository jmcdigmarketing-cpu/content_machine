"""Tests for the future-dated junk-fact filter (core/fact_recency)."""

import datetime
import unittest

from core import fact_recency as fr

_TODAY = datetime.date(2026, 6, 23)


class TestFactRecency(unittest.TestCase):
    def test_drops_future_dated_past_event(self):
        text = "Du Plessis lost to Usman on July 18.\nKape won on June 1."
        kept, dropped = fr.drop_future_dated(text, _TODAY)
        self.assertTrue(any("July 18" in d for d in dropped))
        self.assertIn("Kape won on June 1", kept)
        self.assertNotIn("Du Plessis lost", kept)

    def test_keeps_future_event_preview(self):
        # Future date but NO completed-action verb — a legit preview, not a claim.
        self.assertFalse(fr.is_future_dated_claim("The card is set for July 18.", _TODAY))

    def test_keeps_past_event_on_past_date(self):
        self.assertFalse(
            fr.is_future_dated_claim("Kape defeated Horiguchi on June 1, 2026.", _TODAY)
        )

    def test_flags_explicit_future_year(self):
        self.assertTrue(fr.is_future_dated_claim("Smith signed on March 1, 2027.", _TODAY))

    def test_flags_day_month_year_form(self):
        self.assertTrue(fr.is_future_dated_claim("He retired on 5 December 2027.", _TODAY))

    def test_no_date_is_kept(self):
        kept, dropped = fr.drop_future_dated("Kape is a flyweight contender.", _TODAY)
        self.assertEqual(dropped, [])
        self.assertIn("Kape is a flyweight contender.", kept)

    def test_empty_input(self):
        self.assertEqual(fr.drop_future_dated("", _TODAY), ("", []))


if __name__ == "__main__":
    unittest.main()
