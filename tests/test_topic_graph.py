"""#47 franchise arcs: get_best_bets continues week-1 → week-2, not franchise replay."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from core.best_bet import get_best_bets
from storage.repositories.content_runs import ContentRunRecord
from storage.repositories.publish_log import PublishLogRecord


def _run(run_id: int, topic: str) -> ContentRunRecord:
    return ContentRunRecord(
        id=run_id,
        channel_id="tapin",
        input_topic=topic,
        selected_topic=topic,
        status="rendered",
        composite_score=80.0,
    )


def _log(run_id: int) -> PublishLogRecord:
    return PublishLogRecord(
        id=run_id,
        content_run_id=run_id,
        channel_id="tapin",
        youtube_video_id=f"vid{run_id}",
        status="uploaded",
        metrics_json="{}",
    )


class TopicGraphCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        import config.paths as paths

        self._file = os.path.join(self._tmp.name, "topic_graph.json")
        self._patch = patch.object(paths, "TOPIC_GRAPH_FILE", self._file, create=True)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def _repos(self, topic: str = "GTA 6 leak week 1"):
        run_repo = MagicMock()
        run_repo.list_for_channel.return_value = [_run(71, topic)]
        log_repo = MagicMock()
        log_repo.list_timed_outcomes.return_value = [_log(71)]
        return run_repo, log_repo

    def test_week_two_follows_week_one_on_the_same_arc(self):
        from core.topic_graph import record_published_topic

        record_published_topic("tapin", "GTA 6 leak week 1")
        run_repo, log_repo = self._repos()
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=run_repo,
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=log_repo,
            ),
            patch("core.best_bet._fresh_candidates", return_value=[]),
            patch("core.topic_db.graveyard_topics", return_value=set()),
            patch("core.best_bet.recent_input_topics", return_value=["GTA 6 leak week 1"]),
        ):
            bets = get_best_bets("tapin", 3)
        self.assertTrue(bets)
        lead = bets[0]
        self.assertEqual(lead.source, "arc")
        self.assertIn("week 2", lead.topic.lower())
        self.assertIn("gta", lead.topic.lower())

    def test_empty_graph_fails_open_to_existing_best_bets(self):
        run_repo, log_repo = self._repos()
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=run_repo,
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=log_repo,
            ),
            patch("core.best_bet._fresh_candidates", return_value=[]),
            patch("core.topic_db.graveyard_topics", return_value=set()),
            patch("core.best_bet.recent_input_topics", return_value=[]),
        ):
            bets = get_best_bets("tapin", 3)
        self.assertTrue(bets)
        self.assertFalse(any(b.source == "arc" for b in bets))

    def test_graveyarded_follow_up_is_not_suggested(self):
        from core.topic_graph import follow_up_seed, record_published_topic

        record_published_topic("tapin", "GTA 6 leak week 1")
        nxt = follow_up_seed("tapin")
        self.assertIsNotNone(nxt)
        run_repo, log_repo = self._repos()
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=run_repo,
            ),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=log_repo,
            ),
            patch("core.best_bet._fresh_candidates", return_value=[]),
            patch("core.topic_db.graveyard_topics", return_value={nxt.topic.lower()}),
            patch("core.best_bet.recent_input_topics", return_value=["GTA 6 leak week 1"]),
        ):
            bets = get_best_bets("tapin", 3)
        self.assertFalse(any(b.source == "arc" for b in bets))
        self.assertFalse(any(b.topic.lower() == nxt.topic.lower() for b in bets))


if __name__ == "__main__":
    unittest.main()
