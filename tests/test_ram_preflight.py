"""RAM/VRAM preflight — opt-in, fail-open, ASCII >=."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core.ram_preflight import block_reason, min_ram_gb, snapshot


class TestRamPreflight(unittest.TestCase):
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {"RAM_MIN_GB": "0", "VRAM_MIN_GB": "0"}):
            self.assertIsNone(min_ram_gb())
            self.assertIsNone(block_reason(kind="whisper"))

    def test_blocks_when_below_floor(self):
        with (
            patch.dict(os.environ, {"RAM_MIN_GB": "32", "VRAM_MIN_GB": "0"}),
            patch("core.ram_preflight.available_ram_gb", return_value=4.0),
            patch("core.ram_preflight.available_vram_gb", return_value=None),
        ):
            why = block_reason(kind="whisper")
        self.assertIsNotNone(why)
        self.assertIn(">=", why)
        self.assertIn("whisper", why or "")

    def test_missing_probe_fail_opens(self):
        with (
            patch.dict(os.environ, {"RAM_MIN_GB": "8"}),
            patch("core.ram_preflight.available_ram_gb", return_value=None),
        ):
            self.assertIsNone(block_reason(kind="tts"))

    def test_snapshot_keys(self):
        data = snapshot()
        for key in ("ram_gb", "vram_gb", "ram_min_gb", "vram_min_gb"):
            self.assertIn(key, data)


if __name__ == "__main__":
    unittest.main()
