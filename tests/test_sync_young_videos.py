"""#918: the metrics sync pulls every young video, not only the three newest.

`sync_channel(limit=3)` synced the three most recent live videos. At five a week, a video
could age past the 24h snapshot window (36 h) and past its first days of views-by-day
(#563) before its turn came. Now every live video published within `SYNC_YOUNG_DAYS`
(default 8) is synced, plus the newest `limit`; a scheduled video still in the future is
never synced.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

NOW = datetime.now(timezone.utc)


def _row(i, days_ago, status="uploaded"):
    return {
        "id": i, "content_run_id": i, "channel_id": "tapin", "youtube_video_id": f"v{i}",
        "status": status, "published_at": (NOW - timedelta(days=days_ago)).isoformat(),
        "metrics_json": "{}",
    }  # fmt: skip


class SyncTests(unittest.TestCase):
    def setUp(self):
        rows = [_row(i, d) for i, d in enumerate([1, 2, 3, 4, 6], 1)]
        rows += [_row(6, 30), _row(7, 45), _row(8, 60)]
        rows.append(_row(9, -2, status="scheduled"))  # goes public in two days
        self._tmp = tempfile.TemporaryDirectory()
        path = os.path.join(self._tmp.name, "publish_log.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rows, f)
        self._patches = [
            patch("storage.repositories.publish_log.LOG_FILE", path),
            patch("storage.repositories.publish_log._repo", None),
            patch("storage.repositories.publish_log.postgres_authoritative", return_value=False),
            patch.dict(os.environ, {"SYNC_YOUNG_DAYS": ""}),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        self._tmp.cleanup()

    def _synced(self, limit=3):
        from analytics import sync_metrics

        with (
            patch.object(sync_metrics, "_analytics_enabled", return_value=True),
            patch.object(sync_metrics, "_probe_analytics_api", return_value=(True, "")),
            patch.object(sync_metrics, "refresh_publish_metrics", return_value={}) as refresh,
            patch("builtins.print"),
        ):
            sync_metrics.sync_channel("tapin", limit=limit)
        return [c.kwargs["youtube_video_id"] for c in refresh.call_args_list]

    def test_every_young_video_is_synced(self):
        synced = self._synced(limit=3)
        self.assertEqual(sorted(synced), ["v1", "v2", "v3", "v4", "v5"])

    def test_the_newest_are_still_synced_when_none_are_young(self):
        synced = self._synced(limit=6)
        self.assertEqual(synced[:5], ["v1", "v2", "v3", "v4", "v5"])
        self.assertIn("v6", synced)
        self.assertNotIn("v8", synced)

    def test_a_future_slot_is_never_synced(self):
        self.assertNotIn("v9", self._synced(limit=20))

    def test_the_window_can_be_set(self):
        with patch.dict(os.environ, {"SYNC_YOUNG_DAYS": "2.5"}):
            self.assertEqual(sorted(self._synced(limit=1)), ["v1", "v2"])


if __name__ == "__main__":
    unittest.main()
