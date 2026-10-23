"""#1473 (S18): every health line reads a field some production path writes.

Health read RED on 10-16 on a number nobody stored. Its tests fed `run_engagement_map`,
`channel_economics`, `cadence_status` and the rest hand-made shapes, so a line could read a key
no writer produced - or one a writer stopped producing: the metrics sync froze a video's numbers
at its first day for two weeks (#1542) and every engagement test still passed.

Each test here writes the field the way production does - into real JSON stores in a temp
folder - and then the real `channel_health` line reads it back:

| line         | writer                                         | reader                 |
|--------------|------------------------------------------------|------------------------|
| engagement   | `refresh_publish_metrics`, synced twice        | `_engagement_sub`      |
| cadence      | `privacy_sync.sync_privacy`'s slot (#1519)     | `_cadence_sub`         |
| authenticity | `build_quality` + `persist_quality`            | `_authenticity_sub`    |
| reliability  | `quota_governor.apify_mark_exhausted`          | `_reliability_sub`     |
| cost         | `estimate_run_cost` + `merge_features`         | `_cost_sub`            |
| data quality | `run_trace.write_run_trace`                    | `_data_quality_sub`    |
"""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests.isolation import IsolatedQuotaStore

SCRIPT = (
    "Herbert threw for 312 yards on Sunday. The Chargers are 4-2. Harbaugh said the line held "
    "up. Next week is Denver."
)


class _Stores(IsolatedQuotaStore, unittest.TestCase):
    """Real JSON stores for runs, the publish log and traces, in a temp folder."""

    def setUp(self):
        super().setUp()
        from core import run_trace
        from storage.repositories import content_runs, publish_log

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for patcher in (
            patch.object(content_runs, "RUNS_FILE", os.path.join(tmp.name, "runs.json")),
            patch.object(content_runs, "_repo", content_runs.JsonContentRunRepository()),
            patch.object(publish_log, "LOG_FILE", os.path.join(tmp.name, "publish_log.json")),
            patch.object(publish_log, "_repo", publish_log.JsonPublishLogRepository()),
            patch.object(run_trace, "TRACES_DIR", os.path.join(tmp.name, "traces")),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.runs = content_runs.get_content_run_repository()
        self.log = publish_log.get_publish_log_repository()

    def _run(self, **extra):
        return self.runs.create(
            {"channel_id": "tapin", "input_topic": "Chargers", "selected_topic": "Chargers",
             "status": "published", "title": "Chargers 4-2", **extra}
        )  # fmt: skip

    def _upload(self, run_id, *, published_at, status="uploaded", privacy="public"):
        return self.log.create(
            {"channel_id": "tapin", "content_run_id": run_id, "youtube_video_id": f"v{run_id}",
             "status": status, "privacy_status": privacy, "published_at": published_at,
             "metrics_json": "{}", "idempotency_key": f"run:tapin:{run_id}"}
        )  # fmt: skip

    def assertReads(self, sub):
        from core import channel_health as ch

        self.assertNotEqual(sub.status, ch.UNKNOWN, sub.detail)
        self.assertNotIn("collecting", sub.detail)


class EngagementTests(_Stores):
    def test_the_sync_writes_what_engagement_reads(self):
        from analytics import youtube_metrics
        from core import channel_health as ch

        now = datetime.now(timezone.utc)
        rows = []
        for _ in range(3):
            run = self._run()
            rows.append(self._upload(run.id, published_at=now - timedelta(hours=20)))

        def sync(fetched):
            for row in rows:
                with (
                    patch.object(
                        youtube_metrics, "fetch_video_metrics", return_value=dict(fetched)
                    ),
                    patch.object(youtube_metrics, "record_publish_outcome"),
                    patch.object(youtube_metrics, "infer_domain", return_value="sports"),
                    patch("core.predictions.ledger.frozen_engagement", return_value=None),
                    patch("core.events.emit_event"),
                ):
                    youtube_metrics.refresh_publish_metrics(
                        content_run_id=row.content_run_id, youtube_video_id=row.youtube_video_id,
                        channel_id="tapin", title="Chargers 4-2", publish_log_id=row.id,
                    )  # fmt: skip

        sync({"views": 8, "engaged_rate": 0.3})  # day one: under the 20-view floor
        sync({"views": 500, "engaged_rate": 0.4})  # a later sync (#1542)
        self.assertReads(ch._engagement_sub("tapin"))


class CadenceTests(_Stores):
    def test_the_slot_youtube_holds_is_what_cadence_counts(self):
        from analytics import privacy_sync
        from core import channel_health as ch

        now = datetime.now(timezone.utc)
        run = self._run()
        self._upload(run.id, published_at=now - timedelta(days=1), status="scheduled")
        slot = (now + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        service = MagicMock()
        service.videos.return_value.list.return_value.execute.return_value = {
            "items": [
                {"id": f"v{run.id}", "status": {"privacyStatus": "private", "publishAt": slot}}
            ]
        }
        with patch("apis.youtube_quota.record_usage"):
            privacy_sync.sync_privacy("tapin", service=service)
        sub = ch._cadence_sub("tapin")
        self.assertReads(sub)
        self.assertIn("1 scheduled in the next 7", sub.detail)


class AuthenticityTests(_Stores):
    def test_the_quality_written_is_the_quality_read(self):
        from core import channel_health as ch
        from core.run_quality import build_quality, persist_quality

        features = {"fact_lines": ["Herbert threw for 312 yards", "Chargers are 4-2"]}
        for _ in range(3):
            run = self._run()
            quality = build_quality(script=SCRIPT, channel_id="tapin", features=features,
                                    title="Chargers 4-2")  # fmt: skip
            persist_quality(run.id, quality)
        self.assertReads(ch._authenticity_sub("tapin"))


class ReliabilityTests(_Stores):
    def test_a_breaker_the_governor_trips_is_read(self):
        from core import channel_health as ch
        from core.quota_governor import apify_mark_exhausted

        apify_mark_exhausted("main", "monthly credit used", 3600)
        sub = ch._reliability_sub()
        self.assertReads(sub)
        self.assertIn("Apify off", sub.detail)


class CostTests(_Stores):
    def _videos(self, *, costed):
        from core.cost_meter import estimate_run_cost
        from core.run_features import merge_features

        now = datetime.now(timezone.utc)
        for i in range(3):
            run = self._run(features_json="{}")
            if i < costed:
                merge_features(run.id, {"cost": estimate_run_cost(script=SCRIPT, rendered=True)})
            self._upload(run.id, published_at=now - timedelta(days=3))

    def test_the_cost_written_is_the_cost_read(self):
        from core import channel_health as ch

        self._videos(costed=3)
        with patch("core.money.ledger.total_spent", return_value={"total": 0, "count": 0}):
            sub = ch._cost_sub("tapin")
        self.assertReads(sub)
        self.assertNotIn("no recorded cost", sub.detail)

    def test_a_run_with_no_cost_recorded_is_said(self):
        # #1473: channel_economics read a missing cost as $0.00 - a free video, leaning GREEN
        from core import channel_health as ch

        self._videos(costed=2)
        with patch("core.money.ledger.total_spent", return_value={"total": 0, "count": 0}):
            sub = ch._cost_sub("tapin")
        self.assertIn("1 of 3 with no recorded cost", sub.detail)


class DataQualityTests(_Stores):
    def test_the_trace_written_is_the_trace_read(self):
        from core import channel_health as ch
        from core.run_trace import write_run_trace

        for run_id in (11, 12, 13):
            write_run_trace(
                run_id=run_id, channel_id="tapin", input_topic="Chargers",
                selected_topic="Chargers", status="completed",
                signals={"news": {"status": "error", "connected": False, "active": False}},
            )  # fmt: skip
        sub = ch._data_quality_sub("tapin")
        self.assertReads(sub)
        self.assertIn("signal 'news' not-ok in the last 3 runs", sub.detail)


class SourcesTests(unittest.TestCase):
    def test_each_line_names_everything_it_reads(self):
        from core.channel_health import HEALTH_SOURCES

        self.assertIn("features", HEALTH_SOURCES["engagement"])
        self.assertIn("revenue", HEALTH_SOURCES["cost"])


if __name__ == "__main__":
    unittest.main()
