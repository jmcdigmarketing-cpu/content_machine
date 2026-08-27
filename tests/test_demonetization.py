"""#131 demonetization detector — estimatedRevenue cliff; missing is not $0."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from core.demonetization import detect_revenue_cliff
from storage.repositories.publish_log import PublishLogRecord


def _row(run_id: int, revenue) -> PublishLogRecord:
    metrics = {}
    if revenue is not None:
        metrics["estimated_revenue_usd"] = revenue
    return PublishLogRecord(
        id=run_id,
        content_run_id=run_id,
        channel_id="tapin",
        youtube_video_id=f"v{run_id}",
        status="uploaded",
        metrics_json=json.dumps(metrics),
    )


class TestDemonetization(unittest.TestCase):
    def test_cliff_vs_channel_baseline(self):
        repo = MagicMock()
        repo.list_timed_outcomes.return_value = [
            _row(5, 0.10),
            _row(4, 1.00),
            _row(3, 1.10),
            _row(2, 0.90),
            _row(1, 1.20),
        ]
        with patch(
            "storage.repositories.publish_log.get_publish_log_repository",
            return_value=repo,
        ):
            result = detect_revenue_cliff("tapin")
        self.assertIsNotNone(result)
        self.assertIn("cliff", result.lower())
        self.assertNotIn("$0", result)

    def test_missing_revenue_is_unmeasured_not_zero(self):
        repo = MagicMock()
        repo.list_timed_outcomes.return_value = [_row(1, None), _row(2, None)]
        with patch(
            "storage.repositories.publish_log.get_publish_log_repository",
            return_value=repo,
        ):
            result = detect_revenue_cliff("tapin")
        self.assertIsNone(result)
