import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from analytics.post_timing import (
    PostScheduleConfig,
    PostSlot,
    learn_slots_from_analytics,
)
from storage.repositories.publish_log import PublishLogRecord


class TestLearnPostTiming(unittest.TestCase):
    def test_returns_none_without_samples(self):
        with patch("storage.repositories.publish_log.get_publish_log_repository") as repo:
            repo.return_value.list_timed_outcomes.return_value = []
            self.assertIsNone(learn_slots_from_analytics("tapin"))

    def test_learns_from_timed_publish_outcomes(self):
        tz = timezone.utc
        rows = []
        slot_times = [
            (2025, 1, 16, 18, 0.32),
            (2025, 1, 23, 18, 0.30),
            (2025, 1, 30, 18, 0.28),
            (2025, 1, 17, 17, 0.12),
            (2025, 1, 24, 17, 0.10),
            (2025, 1, 18, 19, 0.27),
            (2025, 1, 25, 19, 0.25),
            (2025, 1, 19, 18, 0.26),
        ]
        for i, (y, m, d, hr, rate) in enumerate(slot_times):
            when = datetime(y, m, d, hr, 0, tzinfo=tz)
            rows.append(
                PublishLogRecord(
                    id=i + 1,
                    content_run_id=0,
                    channel_id="tapin",
                    status="imported",
                    metrics_json=json.dumps(
                        {"engaged_rate": rate, "domain": "gaming", "title": f"V{i}"}
                    ),
                    published_at=when,
                )
            )

        static = PostScheduleConfig(timezone="UTC", slots=(PostSlot(0, 12, 0),))

        with (
            patch("storage.repositories.publish_log.get_publish_log_repository") as repo,
            patch("analytics.post_timing._load_static_post_schedule", return_value=static),
        ):
            repo.return_value.list_timed_outcomes.return_value = rows
            learned = learn_slots_from_analytics("tapin", min_samples=8)

        self.assertIsNotNone(learned)
        top = learned.slots[0]
        self.assertEqual((top.weekday, top.hour), (3, 18))


class TestJobScheduledDelay(unittest.TestCase):
    def test_pending_job_not_claimed_before_scheduled_at(self):
        from storage.repositories.jobs import JOBS_FILE, JsonJobRepository

        with tempfile.TemporaryDirectory() as tmp:
            jobs_path = os.path.join(tmp, "jobs.json")
            with patch("storage.repositories.jobs.JOBS_FILE", jobs_path):
                repo = JsonJobRepository()
                future = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=2)
                repo.enqueue(
                    {
                        "channel_id": "tapin",
                        "job_type": "upload",
                        "payload_json": json.dumps({"file_path": "x.mp4", "title": "T"}),
                        "scheduled_at": future,
                    }
                )
                self.assertIsNone(repo.claim_next())

                repo.update(
                    1,
                    {
                        "scheduled_at": (
                            datetime.now(timezone.utc) - timedelta(minutes=5)
                        ).isoformat()
                    },
                )
                claimed = repo.claim_next()
                self.assertIsNotNone(claimed)
                self.assertEqual(claimed.id, 1)


if __name__ == "__main__":
    unittest.main()
