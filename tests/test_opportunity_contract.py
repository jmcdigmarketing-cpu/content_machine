import inspect
import unittest

from core.opportunity import OpportunityScore, score_topic, signal_breakdown


class TestOpportunityContract(unittest.TestCase):
    def test_score_topic_signature(self):
        sig = inspect.signature(score_topic)
        params = list(sig.parameters)
        self.assertEqual(params, ["topic", "channel_id"])
        self.assertEqual(sig.parameters["channel_id"].default, None)

    def test_opportunity_score_fields(self):
        score = OpportunityScore(
            topic="Test topic",
            channel_id="tapin",
            composite_score=72.5,
            domain="gaming",
            signal_breakdown={"youtube": 18.2},
            recommended_angles=["primary storyline"],
            timings={"signals": 1.2},
        )
        d = score.to_dict()
        self.assertEqual(d["topic"], "Test topic")
        self.assertEqual(d["composite_score"], 72.5)
        self.assertIn("youtube", d["signal_breakdown"])
        self.assertIsInstance(d["recommended_angles"], list)

    def test_signal_breakdown_callable(self):
        signals = {
            "youtube": {"connected": True, "active": True, "score": 80},
        }
        breakdown = signal_breakdown(signals, "Marvel Rivals", channel_id="tapin")
        self.assertIsInstance(breakdown, dict)
        if breakdown:
            for value in breakdown.values():
                self.assertIsInstance(value, float)


if __name__ == "__main__":
    unittest.main()
