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


if __name__ == "__main__":
    unittest.main()
