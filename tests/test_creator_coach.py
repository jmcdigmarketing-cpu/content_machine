"""Tests for the daily creator coach view (Phase S, core/creator_coach.py)."""

import unittest
from unittest.mock import patch

from core.creator_coach import build_coach, render_coach


def _snapshot(**overrides):
    base = {
        "channel_id": "tapin",
        "ideas": [
            {
                "topic": "NBA offseason trade grades",
                "domain": "nba",
                "source": "trending",
                "why": "trending on ESPN now",
            },
            {
                "topic": "Marvel Rivals meta",
                "domain": "gaming",
                "source": "analytics",
                "why": "18% engagement on a past gaming video",
            },
        ],
        "post_time": {"local": "Thu 18:00 ET", "why": "best historical slot"},
        "length": {"label": "Medium", "why": "medium engages 2x short"},
        "title_patterns": [{"tag": "question", "avg": 0.22, "n": 4}],
        "cadence": {"total": 2, "cap": 5, "window_days": 7, "ok": True},
        "retention_dropoff": 0.45,
    }
    base.update(overrides)
    return base


class TestBuildCoach(unittest.TestCase):
    def test_fail_open_when_subsystems_missing(self):
        # Every recommender raising must still yield a renderable snapshot.
        with (
            patch("core.best_bet.get_best_bets", side_effect=RuntimeError),
            patch("analytics.post_timing.get_recommended_time", side_effect=RuntimeError),
            patch("core.length_recommender.get_recommended_length", side_effect=RuntimeError),
            patch("core.title_experiments.pattern_leaderboard", side_effect=RuntimeError),
            patch("core.cadence.cadence_status", side_effect=RuntimeError),
            patch("core.retention.drop_off_ratio", side_effect=RuntimeError),
        ):
            data = build_coach("tapin")
        self.assertEqual(data["ideas"], [])
        text = render_coach(data)
        self.assertIn("Creator coach", text)

    def test_ideas_come_from_best_bets(self):
        from core.best_bet import BestBetResult

        bets = [
            BestBetResult(
                topic="UFC 320 fallout",
                domain="ufc",
                avg_engaged_rate=0.2,
                source="analytics",
                supporting_runs=3,
                rationale="ufc averages 20% engagement",
            )
        ]
        with patch("core.best_bet.get_best_bets", return_value=bets):
            data = build_coach("tapin")
        self.assertEqual(data["ideas"][0]["topic"], "UFC 320 fallout")
        self.assertIn("20%", data["ideas"][0]["why"])


class TestRenderCoach(unittest.TestCase):
    def test_full_snapshot_renders_all_sections(self):
        text = render_coach(_snapshot())
        self.assertIn("NBA offseason trade grades", text)
        self.assertIn("why: trending on ESPN now", text)
        self.assertIn("Medium", text)
        self.assertIn("Thu 18:00 ET", text)
        self.assertIn("question", text)
        self.assertIn("45% in", text)
        self.assertIn("room for 3 more", text)

    def test_at_cadence_cap_warns(self):
        text = render_coach(
            _snapshot(cadence={"total": 5, "cap": 5, "window_days": 7, "ok": False})
        )
        self.assertIn("at the cap", text)

    def test_no_ideas_message(self):
        text = render_coach(_snapshot(ideas=[]))
        self.assertIn("none yet", text)


if __name__ == "__main__":
    unittest.main()
