"""#915: a scheduled video counts as published once its time has passed.

The publisher logs a scheduled upload as `status="scheduled"` and nothing ever moved it
to "uploaded". `list_uploaded_for_channel` (what `sync_channel` pulls analytics for) and
`list_timed_outcomes` (what the recommenders, the prediction ledger and the experiments
learn from) took only uploaded / imported rows, so every video the scheduler placed -
the whole automatic path - was never synced, never scored and never learned from, and
`cadence_status` stopped counting it the moment its slot passed. Read-side fix: a
scheduled row whose `published_at` is in the past is live. No stored row is rewritten.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

NOW = datetime.now(timezone.utc)
PAST = NOW - timedelta(days=2)
FUTURE = NOW + timedelta(days=2)


def _rows():
    metrics = json.dumps({"views": 900, "engaged_rate": 0.41})
    return [
        {"id": 1, "content_run_id": 11, "channel_id": "tapin", "youtube_video_id": "vUP",
         "status": "uploaded", "published_at": (NOW - timedelta(days=3)).isoformat(),
         "metrics_json": metrics},
        {"id": 2, "content_run_id": 12, "channel_id": "tapin", "youtube_video_id": "vPAST",
         "status": "scheduled", "published_at": PAST.isoformat(), "metrics_json": metrics},
        {"id": 3, "content_run_id": 13, "channel_id": "tapin", "youtube_video_id": "vFUT",
         "status": "scheduled", "published_at": FUTURE.isoformat(), "metrics_json": "{}"},
        {"id": 4, "content_run_id": 14, "channel_id": "tapin", "youtube_video_id": "",
         "status": "failed", "published_at": PAST.isoformat(), "metrics_json": "{}"},
    ]  # fmt: skip


class HelperTests(unittest.TestCase):
    def test_counts_as_live(self):
        from storage.repositories.publish_log import counts_as_live

        self.assertTrue(counts_as_live("uploaded", None, NOW))
        self.assertTrue(counts_as_live("imported", PAST, NOW))
        self.assertTrue(counts_as_live("scheduled", PAST, NOW))
        self.assertFalse(counts_as_live("scheduled", FUTURE, NOW))
        self.assertFalse(counts_as_live("scheduled", None, NOW))
        self.assertFalse(counts_as_live("failed", PAST, NOW))
        self.assertFalse(counts_as_live("pending", PAST, NOW))


class _JsonLog(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        path = os.path.join(self._tmp.name, "publish_log.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_rows(), f)
        self._patches = [
            patch("storage.repositories.publish_log.LOG_FILE", path),
            patch("storage.repositories.publish_log._repo", None),
            patch("storage.repositories.publish_log.postgres_authoritative", return_value=False),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        self._tmp.cleanup()


class JsonRepoTests(_JsonLog):
    def test_a_past_scheduled_video_is_uploaded(self):
        from storage.repositories.publish_log import JsonPublishLogRepository

        ids = [
            r.youtube_video_id
            for r in JsonPublishLogRepository().list_uploaded_for_channel("tapin")
        ]
        self.assertEqual(sorted(ids), ["vPAST", "vUP"])

    def test_a_past_scheduled_video_is_an_outcome(self):
        from storage.repositories.publish_log import JsonPublishLogRepository

        runs = [r.content_run_id for r in JsonPublishLogRepository().list_timed_outcomes("tapin")]
        self.assertEqual(sorted(runs), [11, 12])

    def test_future_stays_reserved_not_live(self):
        from storage.repositories.publish_log import JsonPublishLogRepository

        repo = JsonPublishLogRepository()
        self.assertEqual(
            [r.youtube_video_id for r in repo.list_future_scheduled("tapin")], ["vFUT"]
        )

    def test_the_recommenders_see_its_outcome(self):
        from core.engagement_predictor import run_engagement_map

        self.assertEqual(run_engagement_map("tapin"), {11: 0.41, 12: 0.41})

    def test_cadence_keeps_counting_it_after_its_slot(self):
        from core.cadence import cadence_status

        status = cadence_status("tapin", cap=5)
        self.assertEqual((status.recent, status.upcoming), (2, 1))

    def test_sync_pulls_its_analytics(self):
        from analytics import sync_metrics

        with (
            patch.object(sync_metrics, "_analytics_enabled", return_value=True),
            patch.object(sync_metrics, "_probe_analytics_api", return_value=(True, "")),
            patch.object(sync_metrics, "refresh_publish_metrics", return_value={}) as refresh,
            patch("builtins.print"),
        ):
            sync_metrics.sync_channel("tapin", limit=5)
        pulled = sorted(c.kwargs["youtube_video_id"] for c in refresh.call_args_list)
        self.assertEqual(pulled, ["vPAST", "vUP"])


class SqlRepoTests(unittest.TestCase):
    """The same condition in SQL, driven against a temp SQLite file."""

    def setUp(self):
        import storage.db as db
        from config.settings import Settings
        from storage.models import Base

        self._tmp = tempfile.TemporaryDirectory()
        path = os.path.join(self._tmp.name, "log.sqlite3")
        self._env = patch.object(Settings, "database_url", f"sqlite:///{path}")
        self._env.start()
        db.get_engine.cache_clear()
        db._engine = None
        db._SessionLocal = None
        self.db = db
        Base.metadata.create_all(db.get_engine())

    def tearDown(self):
        try:
            self.db.get_engine().dispose()
        except Exception as exc:
            print(f"engine dispose skipped: {exc}")
        self.db.get_engine.cache_clear()
        self.db._engine = None
        self.db._SessionLocal = None
        self._env.stop()
        self._tmp.cleanup()

    def _repo(self):
        from storage.repositories.publish_log import PostgresPublishLogRepository

        repo = PostgresPublishLogRepository()
        for row in _rows():
            data = {k: v for k, v in row.items() if k != "id"}
            data["content_run_id"] = None
            data["published_at"] = datetime.fromisoformat(row["published_at"])
            data["idempotency_key"] = row["youtube_video_id"] or f"k{row['id']}"
            repo.create(data)
        return repo

    def test_both_lists_take_a_past_scheduled_video(self):
        repo = self._repo()
        uploaded = sorted(r.youtube_video_id for r in repo.list_uploaded_for_channel("tapin"))
        outcomes = sorted(r.youtube_video_id for r in repo.list_timed_outcomes("tapin"))
        self.assertEqual(uploaded, ["vPAST", "vUP"])
        self.assertEqual(outcomes, ["vPAST", "vUP"])


if __name__ == "__main__":
    unittest.main()
