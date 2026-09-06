"""Unit tests for the shared recommender confidence bands."""

import unittest

from core.recommender_confidence import (
    MODERATE_SAMPLES,
    SOLID_SAMPLES,
    confidence_level,
    confidence_note,
)


class TestConfidenceLevel(unittest.TestCase):
    def test_high_at_or_above_solid(self):
        self.assertEqual(confidence_level(SOLID_SAMPLES), "high")
        self.assertEqual(confidence_level(SOLID_SAMPLES + 5), "high")

    def test_moderate_band(self):
        self.assertEqual(confidence_level(MODERATE_SAMPLES), "moderate")
        self.assertEqual(confidence_level(SOLID_SAMPLES - 1), "moderate")

    def test_low_below_moderate(self):
        self.assertEqual(confidence_level(MODERATE_SAMPLES - 1), "low")
        self.assertEqual(confidence_level(0), "low")


class TestConfidenceNote(unittest.TestCase):
    def test_high_is_silent(self):
        self.assertEqual(confidence_note(SOLID_SAMPLES), "")

    def test_moderate_names_level_and_count(self):
        note = confidence_note(MODERATE_SAMPLES)
        self.assertIn("moderate confidence", note)
        self.assertIn(f"{MODERATE_SAMPLES} sample", note)

    def test_low_is_flagged(self):
        self.assertIn("low confidence", confidence_note(2))

    def test_singular_plural(self):
        self.assertIn("1 sample)", confidence_note(1))
        self.assertIn("2 samples)", confidence_note(2))

    def test_note_is_cp1252_safe(self):
        """#655. Candidate 250: a bare cp1252 console raises UnicodeEncodeError
        on ⚠. The app configures UTF-8; scripts and one-liners do not."""
        confidence_note(1).encode("cp1252")
        confidence_note(MODERATE_SAMPLES).encode("cp1252")


class TestConfidenceInterval(unittest.TestCase):
    """#351: a sample count says how much evidence there is; an interval says
    whether the number means anything. `30.6% across 2 videos` reads as a finding
    until you see it is 30.6% +/- 22."""

    def test_wide_spread_on_few_samples_is_a_wide_interval(self):
        from core.recommender_confidence import confidence_interval

        half = confidence_interval([0.10, 0.52])
        self.assertIsNotNone(half)
        assert half is not None
        self.assertGreater(half, 0.20, "two far-apart samples must not look precise")

    def test_tight_spread_on_many_samples_is_a_narrow_interval(self):
        from core.recommender_confidence import confidence_interval

        half = confidence_interval([0.30, 0.31, 0.29, 0.30, 0.31, 0.30, 0.29, 0.30])
        self.assertIsNotNone(half)
        assert half is not None
        self.assertLess(half, 0.02)

    def test_a_single_sample_has_no_interval(self):
        """n=1 is the case that matters most and the one where an interval cannot
        be computed. Returning 0.0 would read as certainty."""
        from core.recommender_confidence import confidence_interval

        self.assertIsNone(confidence_interval([0.39]))
        self.assertIsNone(confidence_interval([]))

    def test_identical_samples_give_a_zero_width_interval_not_none(self):
        from core.recommender_confidence import confidence_interval

        self.assertEqual(confidence_interval([0.3, 0.3, 0.3]), 0.0)


class TestIntervalNote(unittest.TestCase):
    def test_it_reports_the_plus_minus_in_points(self):
        from core.recommender_confidence import interval_note

        note = interval_note([0.10, 0.52])
        self.assertIn("+/-", note)
        # Points, not "%": the rates print as percentages already, and
        # "30.6% +/- 22%" invites reading the 22 as relative to the 30.6.
        self.assertIn("pp", note)

    def test_a_single_sample_says_so_instead_of_implying_precision(self):
        from core.recommender_confidence import interval_note

        self.assertEqual(interval_note([0.39]), "")

    def test_the_run_71_case_is_visibly_noise(self):
        """The backlog's own example: 30.6% +/- 22 across a handful of videos."""
        from core.recommender_confidence import interval_note

        note = interval_note([0.06, 0.55, 0.31])
        self.assertIn("+/-", note)


if __name__ == "__main__":
    unittest.main()
