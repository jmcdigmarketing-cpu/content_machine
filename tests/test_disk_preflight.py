"""Disk-space preflight — opt-in, fail-open when disabled."""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.disk_preflight import block_reason, min_free_gb


class TestDiskPreflight(unittest.TestCase):
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {"DISK_MIN_FREE_GB": "0"}):
            self.assertIsNone(min_free_gb())
            self.assertIsNone(block_reason(".", min_gb=None))

    def test_blocks_when_below_floor(self):
        fake = SimpleNamespace(free=100 * 1024**2, total=10 * 1024**3, used=0)
        with (
            patch.dict(os.environ, {"DISK_MIN_FREE_GB": "1"}),
            patch("core.disk_preflight.shutil.disk_usage", return_value=fake),
        ):
            why = block_reason(".")
        self.assertIsNotNone(why)
        self.assertIn("GB free", why)
        self.assertIn(">=", why)  # ASCII, not >= unicode

    def test_missing_disk_usage_fail_opens(self):
        with (
            patch.dict(os.environ, {"DISK_MIN_FREE_GB": "1"}),
            patch("core.disk_preflight.shutil.disk_usage", side_effect=OSError("nope")),
        ):
            self.assertIsNone(block_reason("."))


if __name__ == "__main__":
    unittest.main()
