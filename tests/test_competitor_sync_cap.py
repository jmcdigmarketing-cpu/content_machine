"""Competitor-sync YouTube-unit cap — no record_usage, no real quota file."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from analytics.competitor_sync import youtube_api_fallback_block_reason


class TestCompetitorSyncCap(unittest.TestCase):
    def test_unlimited_when_caps_off(self):
        env = {"COMPETITOR_SYNC_MAX_UNITS": "0", "COMPETITOR_SYNC_RESERVE_UNITS": "0"}
        with patch.dict(os.environ, env, clear=False):
            self.assertIsNone(youtube_api_fallback_block_reason(remaining=10, used_this_sync=0))

    def test_max_units_blocks_over_cap(self):
        env = {"COMPETITOR_SYNC_MAX_UNITS": "3", "COMPETITOR_SYNC_RESERVE_UNITS": "0"}
        with patch.dict(os.environ, env, clear=False):
            self.assertIsNone(youtube_api_fallback_block_reason(remaining=10000, used_this_sync=0))
            reason = youtube_api_fallback_block_reason(remaining=10000, used_this_sync=3)
        self.assertIsNotNone(reason)
        self.assertIn("unit cap", reason or "")

    def test_reserve_keeps_an_upload(self):
        env = {"COMPETITOR_SYNC_MAX_UNITS": "0", "COMPETITOR_SYNC_RESERVE_UNITS": "1600"}
        with patch.dict(os.environ, env, clear=False):
            reason = youtube_api_fallback_block_reason(remaining=100, used_this_sync=0)
        self.assertIsNotNone(reason)
        self.assertIn("reserve", reason or "")

    def test_blocked_api_does_not_record_usage(self):
        from analytics import competitor_sync as cs

        env = {"COMPETITOR_SYNC_MAX_UNITS": "3", "COMPETITOR_SYNC_RESERVE_UNITS": "0"}
        with (
            patch.dict(os.environ, env, clear=False),
            patch.object(cs, "_rss_enabled", return_value=True),
            patch(
                "analytics.youtube_rss.fetch_channel_uploads_rss",
                return_value=[],
            ),
            patch.object(cs, "_sync_api_units", 3),
            patch("apis.youtube_quota.record_usage") as rec,
            patch.object(cs, "_get_youtube_service") as svc,
        ):
            videos = cs.fetch_channel_recent_videos("tapin", "UCBJycsmduvYEL83R_U4JriQ")
        self.assertEqual(videos, [])
        rec.assert_not_called()
        svc.assert_not_called()

    def test_plenty_of_quota_passes_reserve(self):
        env = {"COMPETITOR_SYNC_MAX_UNITS": "30", "COMPETITOR_SYNC_RESERVE_UNITS": "1600"}
        with patch.dict(os.environ, env, clear=False):
            self.assertIsNone(youtube_api_fallback_block_reason(remaining=8000, used_this_sync=0))

    def test_forbid_live_skips_api_key_build(self):
        from analytics import competitor_sync as cs

        env = {
            "CONTENT_FORBID_LIVE_YOUTUBE": "1",
            "YOUTUBE_API_KEY": "not-a-real-key",
        }
        with (
            patch.dict(os.environ, env, clear=False),
            patch("googleapiclient.discovery.build") as build,
        ):
            self.assertIsNone(cs._get_youtube_service("tapin"))
        build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
