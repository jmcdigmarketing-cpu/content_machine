"""Tests for the length recommender's confidence surfacing + sample threshold."""

import unittest
from unittest.mock import patch

from core.length_recommender import get_recommended_length


def _samples(spec):
    """spec: dict of length_choice -> count, all with a fixed engaged_rate."""
    out = []
    for choice, count in spec.items():
        out.extend({"length_choice": choice, "engaged_rate": 0.30} for _ in range(count))
    return out


class TestLengthRecommenderConfidence(unittest.TestCase):
    def _recommend(self, samples):
        with patch("core.length_recommender._collect_length_samples", return_value=samples):
            return get_recommended_length("tapin", "Marvel Rivals update")

    def test_four_samples_no_longer_flips_to_analytics(self):
        # Regression: 4 length samples used to read as authoritative analytics.
        # Below the raised min_total it must fall back to a default instead.
        rec = self._recommend(_samples({"2": 4}))
        self.assertEqual(rec.source, "default")

    def test_thin_bucket_is_flagged_low_or_moderate(self):
        # 6 total (meets min_total); winning bucket has 3 -> moderate/low caveat.
        rec = self._recommend(_samples({"2": 3, "3": 3}))
        self.assertEqual(rec.source, "analytics")
        self.assertIn("confidence", rec.rationale)

    def test_solid_bucket_has_no_caveat(self):
        rec = self._recommend(_samples({"2": 8, "3": 3}))
        self.assertEqual(rec.source, "analytics")
        self.assertEqual(rec.supporting_runs, 8)
        self.assertNotIn("confidence", rec.rationale)


if __name__ == "__main__":
    unittest.main()
