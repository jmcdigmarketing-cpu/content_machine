import os
import unittest
from unittest.mock import MagicMock, patch

from analytics.youtube_metrics import fetch_video_metrics, refresh_publish_metrics


class TestYoutubeMetrics(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=False)
    def test_fetch_disabled_without_env(self):
        self.assertIsNone(fetch_video_metrics("abc123", channel_id="tapin"))

    @patch.dict(os.environ, {"YOUTUBE_ANALYTICS_SYNC": "true"}, clear=False)
    @patch("analytics.youtube_metrics.get_youtube_analytics_service")
    def test_fetch_parses_report(self, mock_service):
        api = MagicMock()
        mock_service.return_value = api
        api.reports().query().execute.return_value = {
            "columnHeaders": [
                {"name": "video"},
                {"name": "views"},
                {"name": "likes"},
                {"name": "comments"},
                {"name": "shares"},
                {"name": "subscribersGained"},
                {"name": "averageViewPercentage"},
                {"name": "estimatedMinutesWatched"},
            ],
            "rows": [["abc123", "1000", "50", "10", "2", "3", "42.5", "120"]],
        }

        metrics = fetch_video_metrics("abc123", channel_id="tapin")
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics["views"], 1000)
        self.assertEqual(metrics["likes"], 50)
        self.assertAlmostEqual(metrics["engaged_rate"], 0.425)

    @patch("analytics.youtube_metrics.fetch_video_metrics", return_value=None)
    def test_refresh_returns_false_when_no_metrics(self, _fetch):
        self.assertFalse(
            refresh_publish_metrics(
                content_run_id=1,
                youtube_video_id="x",
                channel_id="tapin",
            )
        )


if __name__ == "__main__":
    unittest.main()
