"""#46 seasonal calendar as a $0 best-bet source — local file, frozen now=, no HTTP."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from core.best_bet import get_best_bets
from storage.repositories.content_runs import ContentRunRecord
from storage.repositories.publish_log import PublishLogRecord


class TestSeasonalCalendar(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._path = os.path.join(self._tmp.name, "seasonal_calendar.json")
        payload = {
            "tapin": [
                {
                    "date": "2026-11-14",
                    "topic": "UFC 322 card breakdown",
                    "domain": "ufc",
                },
                {
                    "date": "2026-01-01",
                    "topic": "Expired New Year recap",
                    "domain": "gaming",
                },
            ]
        }
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        import config.paths as paths

        self._patch = patch.object(paths, "SEASONAL_CALENDAR_FILE", self._path)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def _repos(self):
        run = ContentRunRecord(
            id=1,
            channel_id="tapin",
            input_topic="Marvel Rivals patch notes",
            selected_topic="Marvel Rivals patch notes",
            status="rendered",
            composite_score=70.0,
        )
        run_repo = MagicMock()
        run_repo.list_for_channel.return_value = [run]
        log_repo = MagicMock()
        log_repo.list_timed_outcomes.return_value = [
            PublishLogRecord(id=1, content_run_id=1, channel_id="tapin", status="uploaded")
        ]
        return run_repo, log_repo

    def test_due_item_surfaces_on_its_date(self):
        from core.seasonal_calendar import due_topics

        now = datetime(2026, 11, 14, 15, 0, tzinfo=timezone.utc)
        due = due_topics("tapin", now=now)
        self.assertEqual(due[0]["topic"], "UFC 322 card breakdown")
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
            patch("core.seasonal_calendar._now", return_value=now),
        ):
            bets = get_best_bets("tapin", 5)
        self.assertTrue(any(b.source == "calendar" and "UFC 322" in b.topic for b in bets))

    def test_past_dates_are_expired(self):
        from core.seasonal_calendar import due_topics

        now = datetime(2026, 11, 14, tzinfo=timezone.utc)
        topics = [d["topic"] for d in due_topics("tapin", now=now)]
        self.assertNotIn("Expired New Year recap", topics)
