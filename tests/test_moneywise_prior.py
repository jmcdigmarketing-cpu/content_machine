"""#81 MoneyWise cold-start prior from TapIn shape, never topics, never wrong-domain averages."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from core.length_recommender import get_recommended_length


class TestMoneywiseLengthPrior(unittest.TestCase):
    def test_cold_start_uses_tapin_length_shape_not_topics(self):
        tapin = [{"length_choice": "3", "engaged_rate": 0.4} for _ in range(8)]
        with (
            patch(
                "core.length_recommender._collect_length_samples",
                side_effect=lambda cid: tapin if cid == "tapin" else [],
            ),
        ):
            rec = get_recommended_length("moneywise", "Fed rate cut and savings APY")
        self.assertEqual(rec.length_choice, "3")
        self.assertEqual(rec.source, "cross_channel_prior")
        self.assertIn("TapIn", rec.rationale)
        self.assertNotIn("Marvel", rec.rationale)
        self.assertNotIn("GTA", rec.rationale)

    def test_own_n_does_not_borrow_tapin(self):
        money = [{"length_choice": "2", "engaged_rate": 0.3} for _ in range(8)]
        tapin = [{"length_choice": "3", "engaged_rate": 0.9} for _ in range(8)]

        def samples(cid):
            return money if cid == "moneywise" else tapin

        with patch("core.length_recommender._collect_length_samples", side_effect=samples):
            rec = get_recommended_length("moneywise", "Fed rate cut and savings APY")
        self.assertEqual(rec.source, "analytics")
        self.assertEqual(rec.length_choice, "2")

    def test_never_invents_a_finance_average_from_gaming_topic_mix(self):
        # TapIn samples exist but we still must not copy a gaming topic into finance.
        tapin = [{"length_choice": "3", "engaged_rate": 0.4} for _ in range(8)]
        with patch(
            "core.length_recommender._collect_length_samples",
            side_effect=lambda cid: tapin if cid == "tapin" else [],
        ):
            rec = get_recommended_length("moneywise", "What the Fed's rate cut means")
        self.assertNotEqual(rec.source, "analytics")
        self.assertIn("prior", rec.source)


class TestMoneywisePostTimePrior(unittest.TestCase):
    def test_cold_start_post_time_uses_tapin_slot_shape(self):
        from analytics.post_timing import PostScheduleConfig, PostSlot, get_recommended_time

        tapin_learned = PostScheduleConfig(
            timezone="America/New_York",
            slots=(PostSlot(3, 18, 0),),
        )
        with (
            patch("analytics.post_timing._use_learned_post_slots", return_value=True),
            patch(
                "analytics.post_timing.learn_slots_from_analytics",
                side_effect=lambda cid, **kw: tapin_learned if cid == "tapin" else None,
            ),
            patch("analytics.post_timing._collect_timed_samples", return_value=[]),
            patch("analytics.upload_queue.get_reserved_publish_times", return_value=[]),
        ):
            rec = get_recommended_time("moneywise", "Fed rate cut")
        self.assertEqual(rec.source, "cross_channel_prior")
        self.assertIn("TapIn", rec.rationale)
        self.assertNotIn("Marvel", rec.rationale)


if __name__ == "__main__":
    unittest.main()
