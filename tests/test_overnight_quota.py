"""Overnight quota-aware count — opt-in, isolated from real youtube_quota.json."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core.overnight_quota import adjust_count, gate_enabled


class TestOvernightQuota(unittest.TestCase):
    def test_disabled_leaves_count(self):
        with patch.dict(os.environ, {"OVERNIGHT_QUOTA_GATE": "false"}):
            n, reason = adjust_count(3)
        self.assertFalse(gate_enabled())
        self.assertEqual(n, 3)
        self.assertEqual(reason, "")

    def test_skip_when_youtube_below_upload_reserve(self):
        env = {"OVERNIGHT_QUOTA_GATE": "true"}
        with (
            patch.dict(os.environ, env),
            patch("apis.apify_client.apify_disabled", return_value=False),
            patch("core.quota_governor.apify_is_exhausted", return_value=(False, "")),
            patch(
                "apis.youtube_quota.get_usage_summary",
                return_value={"remaining": 100},
            ),
        ):
            n, reason = adjust_count(3)
        self.assertEqual(n, 0)
        self.assertIn("skip overnight", reason)

    def test_shrink_when_apify_breaker(self):
        env = {"OVERNIGHT_QUOTA_GATE": "1"}
        with (
            patch.dict(os.environ, env),
            patch("apis.apify_client.apify_disabled", return_value=True),
            patch(
                "apis.youtube_quota.get_usage_summary",
                return_value={"remaining": 9000},
            ),
        ):
            n, reason = adjust_count(5)
        self.assertEqual(n, 1)
        self.assertIn("Apify", reason)

    def test_store_error_fail_opens(self):
        with (
            patch.dict(os.environ, {"OVERNIGHT_QUOTA_GATE": "true"}),
            patch("apis.apify_client.apify_disabled", side_effect=RuntimeError("x")),
            patch("apis.youtube_quota.get_usage_summary", side_effect=RuntimeError("y")),
        ):
            n, reason = adjust_count(4)
        self.assertEqual(n, 4)
        self.assertEqual(reason, "")


if __name__ == "__main__":
    unittest.main()
