"""#352: small samples shrink toward the channel mean in every recommender, not one.

`core/best_bet._adjusted_domain_rates` already ranked domains on an empirical-Bayes mean
(prior strength `MODERATE_SAMPLES`) - the backlog item predates it. The length and
post-time recommenders still ranked on raw means, so three lucky videos in one bucket
outranked eight steady ones. The formula moves to `recommender_confidence.shrunk_mean`
and all three rank on it; the printed average stays the raw one, with the ranking basis
named when it differs.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch


class ShrunkMeanTests(unittest.TestCase):
    def test_the_formula(self):
        from core.recommender_confidence import MODERATE_SAMPLES, shrunk_mean

        self.assertAlmostEqual(
            shrunk_mean([0.306, 0.306], prior=0.15),
            (0.612 + MODERATE_SAMPLES * 0.15) / (2 + MODERATE_SAMPLES),
        )
        self.assertLess(shrunk_mean([0.306, 0.306], prior=0.15), 0.306)
        self.assertEqual(shrunk_mean([], prior=0.2), 0.2)

    def test_best_bet_is_unchanged(self):
        from core.best_bet import _adjusted_domain_rates

        entries = [
            {"domain": "ufc", "engaged_rate": 0.39},
            {"domain": "gaming", "engaged_rate": 0.11},
            {"domain": "gaming", "engaged_rate": 0.12},
            {"domain": "gaming", "engaged_rate": 0.10},
        ]
        prior = (0.39 + 0.11 + 0.12 + 0.10) / 4
        self.assertAlmostEqual(_adjusted_domain_rates(entries)["ufc"], (0.39 + 4 * prior) / 5)


def _length(samples):
    from core import length_recommender

    rows = [{"length_choice": c, "engaged_rate": r} for c, r in samples]
    with patch.object(length_recommender, "_collect_length_samples", return_value=rows):
        return length_recommender.get_recommended_length("tapin", "")


class LengthTests(unittest.TestCase):
    SAMPLES = (
        [("1", 0.36)] * 3  # three lucky videos
        + [("2", 0.33)] * 8  # eight steady ones
        + [("3", 0.10)] * 8
    )

    def test_eight_steady_videos_beat_three_lucky_ones(self):
        rec = _length(self.SAMPLES)
        self.assertEqual(rec.length_choice, "2")

    def test_the_rationale_prints_the_raw_average_and_the_ranking_basis(self):
        rec = _length([("1", 0.36)] * 3 + [("2", 0.33)] * 3 + [("3", 0.10)] * 8)
        self.assertIn("averages", rec.rationale)
        self.assertIn("shrunk toward the channel mean", rec.rationale)

    def test_equal_samples_keep_the_raw_winner(self):
        rec = _length([("1", 0.36)] * 4 + [("2", 0.33)] * 4)
        self.assertEqual(rec.length_choice, "1")


class PostTimeTests(unittest.TestCase):
    def test_a_one_post_slot_does_not_outrank_a_five_post_slot(self):
        from analytics.post_timing import _bucket_averages

        a, b, c = (0, 9, 0), (1, 18, 0), (2, 12, 0)
        sums = {a: 0.40, b: 1.50, c: 0.25}
        counts = {a: 1, b: 5, c: 5}
        avg = _bucket_averages(sums, counts, 1)
        self.assertGreater(avg[b], avg[a])

    def test_equal_counts_keep_the_raw_order(self):
        from analytics.post_timing import _bucket_averages

        a, b = (0, 9, 0), (1, 18, 0)
        avg = _bucket_averages({a: 1.2, b: 1.0}, {a: 3, b: 3}, 1)
        self.assertGreater(avg[a], avg[b])


if __name__ == "__main__":
    unittest.main()
