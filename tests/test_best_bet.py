import unittest
from unittest.mock import MagicMock, patch

from core.best_bet import get_best_bet, get_best_bets
from storage.repositories.content_runs import ContentRunRecord

_ENTRIES = [
    {"topic": "old ufc topic", "engaged_rate": 0.39, "composite_score": 60, "domain": "ufc"},
    {"topic": "old gaming topic", "engaged_rate": 0.25, "composite_score": 50, "domain": "gaming"},
]


class TestFreshBestBets(unittest.TestCase):
    def test_fresh_headlines_preferred_and_ranked_by_domain(self):
        fresh = [
            {"topic": "Gaethje turns top 10 P4P", "domain": "ufc", "source": "ESPN MMA"},
            {"topic": "New roguelike hits Steam", "domain": "gaming", "source": "IGN"},
        ]
        with (
            patch("core.best_bet._build_entries", return_value=_ENTRIES),
            patch("core.best_bet.recent_input_topics", return_value=[]),
            patch("core.best_bet._fresh_candidates", return_value=fresh),
        ):
            bets = get_best_bets("tapin", 3)
        # UFC (39%) outranks gaming (25%); both are fresh/trending, not historical.
        self.assertEqual(bets[0].topic, "Gaethje turns top 10 P4P")
        self.assertEqual(bets[0].source, "trending")
        self.assertIn("trending", bets[0].rationale)

    def test_recently_covered_topics_excluded(self):
        with (
            patch("core.best_bet._build_entries", return_value=_ENTRIES),
            patch(
                "core.best_bet.recent_input_topics",
                return_value=["Gaethje turns top 10 P4P"],
            ),
            # The helper itself excludes recent topics, so it returns none here.
            patch("core.best_bet._fresh_candidates", return_value=[]),
        ):
            bets = get_best_bets("tapin", 3)
        # Falls back to historical; the recent topic is not re-suggested.
        self.assertTrue(all("Gaethje turns top 10" not in b.topic for b in bets))

    def test_falls_back_to_historical_without_fresh(self):
        with (
            patch("core.best_bet._build_entries", return_value=_ENTRIES),
            patch("core.best_bet.recent_input_topics", return_value=[]),
            patch("core.best_bet._fresh_candidates", return_value=[]),
        ):
            bets = get_best_bets("tapin", 3)
        self.assertTrue(bets)
        self.assertEqual(bets[0].source, "analytics")

    def test_fresh_disabled_via_env(self):
        with (
            patch.dict("os.environ", {"BEST_BET_FRESH": "false"}, clear=False),
            patch("core.best_bet._build_entries", return_value=_ENTRIES),
            patch("core.best_bet.recent_input_topics", return_value=[]),
            patch("core.best_bet._fresh_candidates") as mock_fresh,
        ):
            get_best_bets("tapin", 3)
            mock_fresh.assert_not_called()


class TestBestBet(unittest.TestCase):
    def test_prefers_marvel_rivals_continuity_on_tapin(self):
        runs = [
            ContentRunRecord(
                id=23,
                channel_id="tapin",
                input_topic="Marvel rivals update",
                selected_topic="Primary Storyline: Marvel's Game-Changing Rivalries",
                status="done",
                composite_score=100.0,
            ),
            ContentRunRecord(
                id=19,
                channel_id="tapin",
                input_topic="State of Gaming 2026. Marvel Rivals, terraria, cod",
                selected_topic="Marvel Rivals Takes the Gaming World by Storm",
                status="done",
                composite_score=86.8,
            ),
            ContentRunRecord(
                id=16,
                channel_id="tapin",
                input_topic="The fall of COD Zombies from the glory days",
                selected_topic="Overlooked Gems: COD Zombies",
                status="done",
                composite_score=100.0,
            ),
        ]

        mock_repo = MagicMock()
        mock_repo.list_for_channel.return_value = runs
        mock_log_repo = MagicMock()
        mock_log_repo.list_timed_outcomes.return_value = []

        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=mock_repo,
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=mock_log_repo,
            ),
        ):
            result = get_best_bet("tapin")

        self.assertIsNotNone(result)
        self.assertIn("marvel rivals", result.topic.lower())
        self.assertEqual(result.source, "continuity")

    def test_score_fallback_uses_input_topic_not_variant_title(self):
        runs = [
            ContentRunRecord(
                id=5,
                channel_id="tapin",
                input_topic="GTA VI Online Wishlist",
                selected_topic="Hidden Gems: Features We Need in GTA VI",
                status="done",
                composite_score=90.0,
            ),
        ]

        mock_repo = MagicMock()
        mock_repo.list_for_channel.return_value = runs
        mock_log_repo = MagicMock()
        mock_log_repo.list_timed_outcomes.return_value = []

        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=mock_repo,
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=mock_log_repo,
            ),
            patch("core.best_bet._continuity_seed", return_value=None),
        ):
            result = get_best_bet("tapin")

        self.assertEqual(result.topic, "GTA VI Online Wishlist")
        self.assertEqual(result.source, "score")


if __name__ == "__main__":
    unittest.main()
