import unittest
from unittest.mock import patch

from apis.topic_scorer import composite_score
from core.opportunity import score_topic


class TestOpportunitySmoke(unittest.TestCase):
    @patch("core.opportunity.recommended_angles", return_value=["primary storyline"])
    @patch("core.opportunity.build_registry")
    def test_composite_matches_topic_scorer(self, mock_registry, _mock_angles):
        signals = {
            "youtube": {"connected": True, "active": True, "score": 60},
            "blog_rss": {"connected": True, "active": True, "score": 40},
        }
        mock_registry.return_value = signals
        topic = "Marvel Rivals meta shift"

        result = score_topic(topic, channel_id="tapin")
        expected = composite_score(signals, topic, "tapin")

        self.assertEqual(result.composite_score, expected)
        self.assertEqual(result.topic, topic)
        self.assertEqual(result.channel_id, "tapin")
        self.assertIn("youtube", result.signal_breakdown)
        mock_registry.assert_called_once_with(topic)

    @patch("core.opportunity.recommended_angles", return_value=[])
    @patch("core.opportunity.build_registry", return_value={})
    def test_zero_score_when_no_active_signals(self, _mock_registry, _mock_angles):
        result = score_topic("empty signals topic", channel_id="default")
        self.assertEqual(result.composite_score, 0.0)
        self.assertEqual(result.signal_breakdown, {})


if __name__ == "__main__":
    unittest.main()
