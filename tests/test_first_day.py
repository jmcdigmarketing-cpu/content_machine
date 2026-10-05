"""#49: a first-day alert - a video far below (or above) the channel's usual first day.

The metrics sync freezes a 24-hour snapshot of every video (wave 23) and nothing compared it
with anything: a video that died on day one was found at the weekly report. When a sync first
captures a video's 24h snapshot, `analytics/first_day.judge` compares its organic views (paid
views taken out, #954) with the median of the channel's other 24h snapshots:

- below `FIRST_DAY_LOW` (0.5) x the median -> low; above `FIRST_DAY_HIGH` (2) x -> high;
- fewer than `FIRST_DAY_MIN_BASELINE` (5) other videos -> collecting, and nothing is said.

The verdict is stored once as `metrics["first_day"]` (kept by #958's merge), the sync prints
a line for each low or high video, `ops status` repeats it for a week, and an automation
webhook gets a `first_day_anomaly` event (only when `EVENT_WEBHOOK_URL` is set).
"""

from __future__ import annotations

import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

NOW = datetime(2026, 10, 5, 18, 0, tzinfo=timezone.utc)


def _row(rid, views, *, paid=0, age_days=10, title=None, first_day=None):
    snap = {"views": views, "captured_at": (NOW - timedelta(days=age_days)).isoformat()}
    if paid:
        snap["paid_views"] = paid
    metrics = {"views": views, "snapshots": {"24h": snap}}
    if first_day:
        metrics["first_day"] = first_day
    return SimpleNamespace(
        id=rid, content_run_id=100 + rid, youtube_video_id=f"v{rid}", detail=title or f"Video {rid}",
        published_at=NOW - timedelta(days=age_days), metrics_json=json.dumps(metrics),
    )  # fmt: skip


class JudgeTests(unittest.TestCase):
    def test_low_high_normal_and_collecting(self):
        from analytics.first_day import judge

        base = [400, 380, 420, 500, 300]
        self.assertEqual(judge(100, base)["verdict"], "low")
        self.assertEqual(judge(1000, base)["verdict"], "high")
        self.assertEqual(judge(390, base)["verdict"], "normal")
        self.assertEqual(judge(100, base[:4])["verdict"], "collecting")
        got = judge(100, base)
        self.assertEqual((got["baseline"], got["n"]), (400, 5))
        self.assertAlmostEqual(got["ratio"], 0.25)

    def test_the_thresholds_can_be_set(self):
        from analytics.first_day import judge

        with patch.dict(os.environ, {"FIRST_DAY_LOW": "0.2", "FIRST_DAY_MIN_BASELINE": "3"}):
            self.assertEqual(judge(100, [400, 400, 400])["verdict"], "normal")

    def test_the_baseline_is_organic(self):
        from analytics.first_day import organic_first_day

        self.assertEqual(organic_first_day({"views": 3000, "paid_views": 2900}), 100)
        self.assertEqual(organic_first_day({"views": 300}), 300)
        self.assertIsNone(organic_first_day({}))


class _Repo:
    def __init__(self, rows):
        self.rows = rows
        self.updates: dict[int, dict] = {}

    def list_uploaded_for_channel(self, _channel):
        return self.rows

    def find_by_idempotency(self, _key):
        return None

    def update(self, rid, fields):
        self.updates[rid] = fields
        for row in self.rows:
            if row.id == rid:
                row.metrics_json = fields["metrics_json"]


class SyncTests(unittest.TestCase):
    def _refresh(self, repo, row, fetched):
        from analytics import youtube_metrics

        with (
            patch.object(youtube_metrics, "fetch_video_metrics", return_value=fetched),
            patch.object(youtube_metrics, "get_publish_log_repository", return_value=repo),
            patch("analytics.first_day._repo", return_value=repo),
            patch("analytics.first_day._now", return_value=NOW),
            patch.object(youtube_metrics, "record_publish_outcome"),
            patch.object(youtube_metrics, "infer_domain", return_value="gaming"),
            patch.object(youtube_metrics, "_now", return_value=NOW),
            patch("core.predictions.ledger.frozen_engagement", return_value=None),
            patch("core.events.emit_event") as emit,
        ):
            youtube_metrics.refresh_publish_metrics(
                content_run_id=row.content_run_id, youtube_video_id=row.youtube_video_id,
                channel_id="tapin", title=row.detail, publish_log_id=row.id,
            )  # fmt: skip
        return json.loads(row.metrics_json), emit

    def _young(self):
        young = SimpleNamespace(
            id=9, content_run_id=109, youtube_video_id="v9", detail="Heat preseason",
            published_at=NOW - timedelta(hours=20), metrics_json="{}",
        )  # fmt: skip
        rows = [_row(i, v) for i, v in enumerate([400, 380, 420, 500, 300], start=1)]
        return young, _Repo([*rows, young])

    def test_a_dead_first_day_is_flagged_once(self):
        young, repo = self._young()
        metrics, emit = self._refresh(repo, young, {"views": 90, "engaged_rate": 0.4})
        self.assertEqual(metrics["first_day"]["verdict"], "low")
        self.assertEqual(metrics["first_day"]["views"], 90)
        emit.assert_called_once()
        self.assertEqual(emit.call_args.args[0], "first_day_anomaly")
        self.assertEqual(emit.call_args.args[1]["verdict"], "low")
        # A second sync in the same window does not judge again.
        metrics, emit = self._refresh(repo, young, {"views": 2000, "engaged_rate": 0.4})
        self.assertEqual(metrics["first_day"]["views"], 90)
        emit.assert_not_called()

    def test_a_normal_first_day_sends_nothing(self):
        young, repo = self._young()
        metrics, emit = self._refresh(repo, young, {"views": 410, "engaged_rate": 0.4})
        self.assertEqual(metrics["first_day"]["verdict"], "normal")
        emit.assert_not_called()

    def test_a_snapshot_taken_before_this_is_not_judged(self):
        # A video whose 24h snapshot predates #49 would otherwise be judged - and alerted -
        # on the first sync after the upgrade, days after its first day.
        _young, repo = self._young()
        old = repo.rows[0]
        metrics, emit = self._refresh(repo, old, {"views": 5, "engaged_rate": 0.4})
        self.assertNotIn("first_day", metrics)
        emit.assert_not_called()

    def test_an_old_video_is_not_judged(self):
        young, repo = self._young()
        young.published_at = NOW - timedelta(days=20)
        metrics, emit = self._refresh(repo, young, {"views": 5, "engaged_rate": 0.4})
        self.assertNotIn("first_day", metrics)
        emit.assert_not_called()


class LinesTests(unittest.TestCase):
    def test_flags_from_the_last_week_are_listed(self):
        from analytics.first_day import recent_lines

        low = {"verdict": "low", "views": 90, "baseline": 400, "ratio": 0.225, "n": 5,
               "judged_at": (NOW - timedelta(days=1)).isoformat()}  # fmt: skip
        old = dict(low, judged_at=(NOW - timedelta(days=30)).isoformat())
        normal = dict(low, verdict="normal")
        repo = _Repo([_row(1, 90, title="Heat preseason", first_day=low),
                      _row(2, 90, first_day=old), _row(3, 400, first_day=normal)])  # fmt: skip
        with patch("analytics.first_day._repo", return_value=repo),\
             patch("analytics.first_day._now", return_value=NOW):  # fmt: skip
            lines = recent_lines("tapin")
        self.assertEqual(len(lines), 1)
        self.assertIn("Heat preseason", lines[0])
        self.assertIn("90", lines[0])
        self.assertIn("400", lines[0])

    def test_status_shows_them(self):
        from core.status import build_status_lines

        with patch("analytics.first_day.recent_lines", return_value=["First day: X low"]):
            lines = build_status_lines("tapin")
        self.assertIn("First day: X low", lines)


if __name__ == "__main__":
    unittest.main()
