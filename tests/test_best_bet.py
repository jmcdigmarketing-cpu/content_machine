import unittest
from unittest.mock import MagicMock, patch

from core.best_bet import get_best_bet
from storage.repositories.content_runs import ContentRunRecord


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
