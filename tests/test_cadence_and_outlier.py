"""Tests for the cadence guardrail and competitor-outlier surface."""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from core.cadence import CadenceStatus, cadence_status, max_videos_per_week
from core.outlier import get_competitor_outlier


def _row(published_at):
    r = MagicMock()
    r.published_at = published_at
    return r


class TestCadence(unittest.TestCase):
    def test_default_cap(self):
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("MAX_VIDEOS_PER_WEEK", None)
            self.assertEqual(max_videos_per_week(), 5)

    def test_cap_from_env(self):
        with patch.dict("os.environ", {"MAX_VIDEOS_PER_WEEK": "3"}):
            self.assertEqual(max_videos_per_week(), 3)

    def test_status_ok_under_cap(self):
        s = CadenceStatus(recent=1, upcoming=1, cap=5, window_days=7)
        self.assertEqual(s.total, 2)
        self.assertTrue(s.ok)

    def test_status_blocks_at_cap(self):
        s = CadenceStatus(recent=3, upcoming=2, cap=5, window_days=7)
        self.assertEqual(s.total, 5)
        self.assertFalse(s.ok)

    def test_counts_recent_and_upcoming_in_window(self):
        now = datetime.now(timezone.utc)
        repo = MagicMock()
        repo.list_uploaded_for_channel.return_value = [
            _row(now - timedelta(days=2)),  # in window
            _row(now - timedelta(days=10)),  # out of window
            _row(None),  # no date
        ]
        repo.list_future_scheduled.return_value = [
            _row(now + timedelta(days=3)),  # in window
            _row(now + timedelta(days=20)),  # out of window
        ]
        with patch(
            "storage.repositories.publish_log.get_publish_log_repository",
            return_value=repo,
        ):
            s = cadence_status("tapin", cap=5)
        self.assertEqual(s.recent, 1)
        self.assertEqual(s.upcoming, 1)


class TestOutlier(unittest.TestCase):
    def test_none_when_signal_inactive(self):
        self.assertIsNone(get_competitor_outlier({"youtube_competitors": {"active": False}}))

    def test_none_when_missing(self):
        self.assertIsNone(get_competitor_outlier({}))

    def test_picks_highest_velocity(self):
        signals = {
            "youtube_competitors": {
                "active": True,
                "data": {
                    "videos": [
                        {"title": "Slow one", "velocity": 1000, "views": 5000, "channel": "A"},
                        {
                            "title": "Surging one",
                            "velocity": 68000,
                            "views": 480000,
                            "channel": "B",
                        },
                    ]
                },
            }
        }
        outlier = get_competitor_outlier(signals)
        self.assertIsNotNone(outlier)
        self.assertEqual(outlier.title, "Surging one")
        self.assertEqual(outlier.channel, "B")
        self.assertIn("68,000 views/day", outlier.prompt_line())

    def test_none_when_zero_velocity(self):
        signals = {
            "youtube_competitors": {
                "active": True,
                "data": {"videos": [{"title": "x", "velocity": 0}]},
            }
        }
        self.assertIsNone(get_competitor_outlier(signals))


if __name__ == "__main__":
    unittest.main()
