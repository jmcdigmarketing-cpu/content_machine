"""Yesterday-has-metrics gate — fake rows only, no real publish_log."""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from core.metrics_gate import metrics_gate_reason


def _row(day_offset: int, *, views=0, engaged=None) -> SimpleNamespace:
    published = datetime.now(timezone.utc) - timedelta(days=day_offset)
    metrics = {}
    if views:
        metrics["views"] = views
    if engaged is not None:
        metrics["engaged_rate"] = engaged
    import json

    return SimpleNamespace(published_at=published, metrics_json=json.dumps(metrics))


class TestMetricsGate(unittest.TestCase):
    def test_default_off(self):
        with patch.dict(os.environ, {"METRICS_BEFORE_NEXT": ""}, clear=False):
            self.assertIsNone(metrics_gate_reason("tapin", rows=[_row(1, views=0)]))

    def test_no_yesterday_upload_passes(self):
        env = {"METRICS_BEFORE_NEXT": "true"}
        with patch.dict(os.environ, env, clear=False):
            self.assertIsNone(metrics_gate_reason("tapin", rows=[_row(3, views=0)]))
            self.assertIsNone(metrics_gate_reason("tapin", rows=[]))

    def test_yesterday_without_views_blocks(self):
        env = {"METRICS_BEFORE_NEXT": "true"}
        with patch.dict(os.environ, env, clear=False):
            reason = metrics_gate_reason("tapin", rows=[_row(1, views=0)])
        self.assertIsNotNone(reason)
        self.assertIn("yesterday", reason)

    def test_yesterday_with_views_passes(self):
        env = {"METRICS_BEFORE_NEXT": "true"}
        with patch.dict(os.environ, env, clear=False):
            self.assertIsNone(metrics_gate_reason("tapin", rows=[_row(1, views=12)]))

    def test_engaged_rate_counts_as_metrics(self):
        env = {"METRICS_BEFORE_NEXT": "1"}
        with patch.dict(os.environ, env, clear=False):
            self.assertIsNone(metrics_gate_reason("tapin", rows=[_row(1, views=0, engaged=0.4)]))


if __name__ == "__main__":
    unittest.main()
