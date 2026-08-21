"""Quiet hours (#116) + UFC PPV window (#115). Isolated clocks; no live YouTube."""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from core.publish_windows import (
    adjust_publish_at,
    is_ufc_topic,
    quiet_hours_reason,
    ufc_ppv_reason,
)
from publishing.youtube_publisher import build_video_status
from youtube.upload import UploadRequest

try:
    from zoneinfo import ZoneInfo

    ET = ZoneInfo("America/New_York")
except Exception:
    ET = timezone(timedelta(hours=-4))


class TestUfcPpvWindow(unittest.TestCase):
    def test_ufc_topic_detects_card_language(self):
        self.assertTrue(is_ufc_topic("UFC 319 main card", "gaming"))
        self.assertTrue(is_ufc_topic("fight night", "ufc"))
        self.assertFalse(is_ufc_topic("GTA 6 leaks", "gaming"))
        self.assertFalse(is_ufc_topic("UFC 5 career mode", "gaming"))
        self.assertFalse(is_ufc_topic("EA Sports UFC 5", "ufc"))

    def test_saturday_late_blocks_ufc_only(self):
        sat = datetime(2026, 8, 22, 22, 0, tzinfo=ET)
        with patch.dict(os.environ, {"UFC_PPV_BLACKOUT": "true"}):
            why = ufc_ppv_reason(topic="UFC 319", domain="ufc", when=sat)
            gta = ufc_ppv_reason(topic="GTA 6 leaks", domain="gaming", when=sat)
        self.assertIsNotNone(why)
        self.assertIn("PPV", why)
        self.assertIsNone(gta)

    def test_sunday_afternoon_is_clear(self):
        sun = datetime(2026, 8, 23, 15, 0, tzinfo=ET)
        with patch.dict(os.environ, {"UFC_PPV_BLACKOUT": "true"}):
            self.assertIsNone(ufc_ppv_reason(topic="UFC 319", domain="ufc", when=sun))

    def test_env_off(self):
        sat = datetime(2026, 8, 22, 22, 0, tzinfo=ET)
        with patch.dict(os.environ, {"UFC_PPV_BLACKOUT": "false"}):
            self.assertIsNone(ufc_ppv_reason(topic="UFC 319", domain="ufc", when=sat))


class TestQuietHours(unittest.TestCase):
    def test_three_am_is_quiet(self):
        cfg = {"start_hour": 1, "end_hour": 8, "timezone": "America/New_York"}
        when = datetime(2026, 8, 21, 3, 0, tzinfo=ET)
        with patch.dict(os.environ, {"QUIET_HOURS": "true"}):
            why = quiet_hours_reason(when=when, config=cfg)
        self.assertIsNotNone(why)
        self.assertIn("quiet hours", why)

    def test_noon_is_clear(self):
        cfg = {"start_hour": 1, "end_hour": 8, "timezone": "America/New_York"}
        when = datetime(2026, 8, 21, 12, 0, tzinfo=ET)
        with patch.dict(os.environ, {"QUIET_HOURS": "true"}):
            self.assertIsNone(quiet_hours_reason(when=when, config=cfg))


class TestAdjustPublishAt(unittest.TestCase):
    def test_scheduled_ufc_ppv_is_bumped(self):
        sat = datetime(2026, 8, 22, 22, 0, tzinfo=ET)
        with patch.dict(os.environ, {"UFC_PPV_BLACKOUT": "true", "QUIET_HOURS": "false"}):
            bumped, why = adjust_publish_at(
                sat,
                topic="UFC 319 Topuria",
                domain="ufc",
                privacy="public",
            )
        self.assertIsNotNone(why)
        self.assertIsNotNone(bumped)
        self.assertGreater(bumped, sat)

    def test_ppv_clear_does_not_land_in_quiet_hours(self):
        sat = datetime(2026, 8, 22, 22, 0, tzinfo=ET)
        ppv = {"weekday": 5, "start_hour": 21, "end_hour": 2, "timezone": "America/New_York"}
        quiet = {"start_hour": 1, "end_hour": 8, "timezone": "America/New_York"}
        with patch.dict(os.environ, {"UFC_PPV_BLACKOUT": "true", "QUIET_HOURS": "true"}):
            with (
                patch("core.publish_windows.ppv_config", return_value=ppv),
                patch("core.publish_windows.quiet_hours_config", return_value=quiet),
            ):
                bumped, why = adjust_publish_at(
                    sat,
                    topic="UFC 319 Topuria",
                    domain="ufc",
                    privacy="public",
                    channel_id="tapin",
                )
        self.assertIsNotNone(why)
        self.assertIsNotNone(bumped)
        local = bumped.astimezone(ET)
        self.assertGreaterEqual(local.hour, 8)
        self.assertNotEqual(local.hour, 2)

    def test_unlisted_review_skips_immediate_public(self):
        sat = datetime(2026, 8, 22, 22, 0, tzinfo=ET)
        with patch.dict(
            os.environ,
            {
                "UFC_PPV_BLACKOUT": "true",
                "YOUTUBE_UNLISTED_REVIEW": "true",
                "QUIET_HOURS": "false",
            },
        ):
            bumped, why = adjust_publish_at(
                None,
                topic="UFC 319",
                domain="ufc",
                privacy="public",
                now=sat,
            )
        self.assertIsNone(why)
        self.assertIsNone(bumped)

    def test_build_video_status_schedules_out_of_window(self):
        sat = datetime(2026, 8, 22, 22, 0, tzinfo=ET)
        with patch.dict(os.environ, {"UFC_PPV_BLACKOUT": "true", "QUIET_HOURS": "false"}):
            with patch("apis.topic_scorer.infer_domain", return_value="ufc"):
                status = build_video_status(
                    UploadRequest(
                        file_path="x.mp4",
                        title="UFC 319",
                        description="D",
                        privacy_status="public",
                        publish_at=sat,
                    ),
                    channel_id="tapin",
                )
        self.assertEqual(status["privacyStatus"], "private")
        self.assertIn("publishAt", status)
        self.assertIn("_window_reason", status)
        status.pop("_window_reason")
        self.assertLessEqual(
            set(status),
            {"privacyStatus", "publishAt", "selfDeclaredMadeForKids"},
        )


if __name__ == "__main__":
    unittest.main()
