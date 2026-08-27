"""Candidates 327/328: the record rule must not eat ranges, and one bad match must not
silence the whole pass.

`expand_spoken_numbers` runs unconditionally in `generate_audio` for **every** channel,
so whatever it rewrites is what the voice actually says. Its record rule was
`\\b(\\d{1,2})-(\\d{1,2})\\b` — correct for "Gaethje is now 25-4", and also a match for
every range and percentage in the language. Measured before the fix:

    "Expect 5-10 years of compounding."  -> "Expect five ten years of compounding."
    "Returns of 10-15% are typical."     -> "Returns of ten fifteen% are typical."
    "She worked a 9-5 for a decade."     -> "She worked a nine five for a decade."

Worst on MoneyWise, which is made of ranges and percentages and has just been given its
own voice. `core/fact_grounding.py` had already solved this exact ambiguity 40 lines
away — *"Fighter records only … Bare 10-9 / 29-28 round scores must not fire"* — by
requiring a verb cue. That guard is reused here rather than reinvented.

328: `_UFC_RE` accepted 2-4 digits while the event-number speller indexes a 20-entry
tuple, so `UFC 2000` raised `IndexError`. The call site swallows the whole pass at
`logger.debug`, so *every* expansion silently stopped for that script and the operator
saw nothing at the default WARNING level.
"""

import unittest

from core.spoken_numbers import expand_spoken_numbers


class TestRangesAreNotRecords(unittest.TestCase):
    """The cases the original pattern also caught — none of these is a fight record."""

    def test_year_range_is_left_alone(self):
        text = "Expect 5-10 years of compounding."
        self.assertEqual(expand_spoken_numbers(text), text)

    def test_percentage_range_is_left_alone(self):
        text = "Returns of 10-15% are typical."
        self.assertEqual(expand_spoken_numbers(text), text)

    def test_the_nine_to_five_is_left_alone(self):
        text = "She worked a 9-5 for a decade."
        self.assertEqual(expand_spoken_numbers(text), text)

    def test_round_range_is_left_alone(self):
        # A scheduled range, not a record — the same distinction fact_grounding makes.
        text = "The fight is scheduled for 3-5 rounds."
        self.assertEqual(expand_spoken_numbers(text), text)

    def test_bare_round_score_is_left_alone(self):
        text = "Judges scored it 10-9."
        self.assertEqual(expand_spoken_numbers(text), text)


class TestRealRecordsStillExpand(unittest.TestCase):
    """The intended case must keep working, or the guard is too strong."""

    def test_is_cue(self):
        self.assertIn("twenty-five four", expand_spoken_numbers("Gaethje is 25-4 after the win."))

    def test_now_cue(self):
        self.assertIn("twenty-nine one", expand_spoken_numbers("He went 29-1 in the promotion."))

    def test_record_of_cue(self):
        self.assertIn("fifteen zero", expand_spoken_numbers("A record of 15-0 coming in."))

    def test_three_part_record(self):
        self.assertIn("twenty-four three", expand_spoken_numbers("He is now 24-3-1 lifetime."))


class TestEventNumberRange(unittest.TestCase):
    """328: an out-of-range event number must not take the whole pass down with it."""

    def test_four_digit_event_does_not_raise(self):
        self.assertEqual(expand_spoken_numbers("UFC 2000 someday."), "UFC 2000 someday.")

    def test_a_bad_match_does_not_stop_the_others(self):
        # The purse and the record in the same script must still be spoken.
        out = expand_spoken_numbers("UFC 2000 someday, but he is 25-4 for a $50k purse.")
        self.assertIn("twenty-five four", out)
        self.assertIn("fifty thousand dollars", out)

    def test_real_event_numbers_still_expand(self):
        self.assertIn("three twenty", expand_spoken_numbers("UFC 320 is set."))
        self.assertIn("ninety-nine", expand_spoken_numbers("UFC 99 was great."))


class TestPursesUnchanged(unittest.TestCase):
    def test_money_k_still_expands(self):
        self.assertIn("fifty thousand dollars", expand_spoken_numbers("a $50k purse"))

    def test_unmatched_text_is_untouched(self):
        text = "No numbers here at all."
        self.assertEqual(expand_spoken_numbers(text), text)


if __name__ == "__main__":
    unittest.main()
