import unittest
from unittest.mock import patch

from apis.signal_corroboration import assess_corroboration, corroboration_score_adjustment
from core.analyst_explain import build_explainability
from core.opportunity_window import WINDOW_OPEN, assess_opportunity_window
from core.topic_trajectory import compute_trajectory, record_topic_snapshot


class TestAnalystIntelligence(unittest.TestCase):
    def test_corroboration_multi_source(self):
        signals = {
            "youtube": {"connected": True, "active": True, "score": 70},
            "blog_rss": {"connected": True, "active": True, "score": 55},
            "trends": {"connected": True, "active": True, "score": 40},
        }
        result = assess_corroboration(signals)
        self.assertEqual(result["source_count"], 3)
        self.assertGreater(result["confidence"], 0.65)
        boosted = corroboration_score_adjustment(70.0, result)
        self.assertGreater(boosted, 70.0)

    def test_corroboration_single_source_low(self):
        signals = {
            "youtube": {"connected": True, "active": True, "score": 80},
        }
        result = assess_corroboration(signals)
        self.assertEqual(result["source_count"], 1)
        self.assertLess(result["confidence"], 0.5)

    def test_opportunity_window_open(self):
        window = assess_opportunity_window(
            "obscure indie game launch",
            composite_score=72,
            competitor_titles=[],
            corroboration_confidence=0.7,
        )
        self.assertEqual(window["window_status"], WINDOW_OPEN)
        self.assertGreater(window["gap_score"], 0.4)

    def test_trajectory_insufficient_data(self):
        with patch("core.topic_trajectory._load_store", return_value={}):
            traj = compute_trajectory("tapin", "brand new topic xyz")
        self.assertEqual(traj["phase"], "insufficient_data")

    def test_trajectory_rising(self):
        import time

        now = time.time()
        store = {
            "tapin::rising topic": [
                {"ts": now - 7200, "composite_score": 40},
                {"ts": now - 3600, "composite_score": 55},
                {"ts": now, "composite_score": 72},
            ]
        }
        with patch("core.topic_trajectory._load_store", return_value=store):
            traj = compute_trajectory("tapin", "rising topic")
        self.assertIn(traj["phase"], ("rising", "peaking", "stable"))

    def test_explainability_block(self):
        exp = build_explainability(
            topic="Test topic",
            composite_score=68.0,
            signals={
                "youtube": {"connected": True, "active": True, "score": 70, "confidence": 0.8}
            },
            signal_breakdown={"youtube": 0.35},
            corroboration={"label": "moderate", "confidence": 0.58, "source_count": 2},
            trajectory={"summary": "Rising.", "phase": "rising"},
            opportunity_window={"summary": "Open window.", "window_status": "open"},
            research_brief={"debate_angles": ["Angle A", "Angle B"]},
        )
        self.assertIn("why_now", exp)
        self.assertIn("youtube", exp["why_this"])
        self.assertTrue(exp["signals_fired"])


if __name__ == "__main__":
    unittest.main()
