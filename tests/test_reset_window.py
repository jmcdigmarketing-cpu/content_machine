"""Tests for the reset-window auto-re-enable layer (O10, core/reset_window.py)."""

import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from core.reset_window import next_reset, reset_window_enabled, seconds_until_reset


class TestYouTubeReset(unittest.TestCase):
    def test_next_reset_is_midnight_pacific(self):
        now = datetime(2026, 7, 2, 12, 0, tzinfo=timezone.utc)
        nxt = next_reset("youtube", now=now)
        self.assertIsNotNone(nxt)
        local = nxt.astimezone(ZoneInfo("America/Los_Angeles"))
        self.assertEqual((local.hour, local.minute, local.second), (0, 0, 0))
        self.assertGreater(nxt, now)

    def test_reset_within_a_day(self):
        now = datetime(2026, 7, 2, 12, 0, tzinfo=timezone.utc)
        secs = seconds_until_reset("youtube", now=now)
        self.assertIsNotNone(secs)
        self.assertLessEqual(secs, 24 * 3600)


class TestMonthlyReset(unittest.TestCase):
    def test_apify_defaults_to_first_of_next_month(self):
        now = datetime(2026, 7, 15, tzinfo=timezone.utc)
        nxt = next_reset("apify", now=now)
        self.assertEqual((nxt.year, nxt.month, nxt.day), (2026, 8, 1))

    def test_apify_custom_billing_day(self):
        now = datetime(2026, 7, 2, tzinfo=timezone.utc)
        with patch.dict("os.environ", {"APIFY_RESET_DAY": "10"}):
            nxt = next_reset("apify", now=now)
        self.assertEqual((nxt.month, nxt.day), (7, 10))

    def test_apify_billing_day_already_passed_rolls_over(self):
        now = datetime(2026, 7, 20, tzinfo=timezone.utc)
        with patch.dict("os.environ", {"APIFY_RESET_DAY": "10"}):
            nxt = next_reset("apify", now=now)
        self.assertEqual((nxt.month, nxt.day), (8, 10))

    def test_day_31_clamps_to_month_length(self):
        now = datetime(2026, 2, 5, tzinfo=timezone.utc)
        with patch.dict("os.environ", {"APIFY_RESET_DAY": "31"}):
            nxt = next_reset("apify", now=now)
        self.assertEqual((nxt.month, nxt.day), (2, 28))

    def test_odds_resets_on_the_first(self):
        now = datetime(2026, 12, 25, tzinfo=timezone.utc)
        nxt = next_reset("odds", now=now)
        self.assertEqual((nxt.year, nxt.month, nxt.day), (2027, 1, 1))

    def test_year_rollover(self):
        now = datetime(2026, 12, 31, 23, 0, tzinfo=timezone.utc)
        nxt = next_reset("apify", now=now)
        self.assertEqual((nxt.year, nxt.month, nxt.day), (2027, 1, 1))


class TestUnknownProvider(unittest.TestCase):
    def test_unknown_returns_none(self):
        self.assertIsNone(next_reset("nope"))
        self.assertIsNone(seconds_until_reset("nope"))

    def test_seconds_has_minimum_floor(self):
        # Just before the reset boundary, still returns >= 60s.
        now = datetime(2026, 7, 31, 23, 59, 59, tzinfo=timezone.utc)
        secs = seconds_until_reset("apify", now=now)
        self.assertGreaterEqual(secs, 60)


class TestMasterSwitch(unittest.TestCase):
    def test_enabled_by_default(self):
        self.assertTrue(reset_window_enabled())

    def test_disable_via_env(self):
        with patch.dict("os.environ", {"RESET_WINDOW_AUTO_ENABLE": "false"}):
            self.assertFalse(reset_window_enabled())


class TestApifyClientIntegration(unittest.TestCase):
    """402 exhaustion persists until the cycle reset; auth failures keep the short TTL."""

    def test_402_ttl_uses_reset_window(self):
        from apis import apify_client as ac

        with patch("core.reset_window.seconds_until_reset", return_value=123456) as mock_secs:
            ttl = ac._persist_ttl_for_status(402)
        mock_secs.assert_called_once_with("apify")
        self.assertEqual(ttl, 123456)

    def test_402_ttl_falls_back_when_disabled(self):
        from apis import apify_client as ac

        with patch.dict("os.environ", {"RESET_WINDOW_AUTO_ENABLE": "false"}):
            self.assertEqual(ac._persist_ttl_for_status(402), ac._persist_ttl())

    def test_auth_ttl_unchanged(self):
        from apis import apify_client as ac

        self.assertEqual(ac._persist_ttl_for_status(403), ac._auth_failure_ttl())


class TestYouTubeQuotaIntegration(unittest.TestCase):
    def test_blocked_upload_retries_after_real_reset(self):
        from apis import youtube_quota as yq

        fixed = datetime(2026, 7, 3, 8, 0, tzinfo=timezone.utc)
        with (
            patch.object(yq, "has_quota_for_upload", return_value=False),
            patch("core.reset_window.next_reset", return_value=fixed) as mock_next,
        ):
            retry = yq.next_quota_retry_at()
        mock_next.assert_called_once()
        # 5-minute buffer past the reset boundary.
        self.assertEqual((retry - fixed).total_seconds(), 300)


if __name__ == "__main__":
    unittest.main()
