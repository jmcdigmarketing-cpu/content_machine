"""Discovery worker cap (candidate 41)."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from apis.register_signals import _discovery_worker_cap


class TestDiscoveryWorkerCap(unittest.TestCase):
    def test_default_caps_at_eight(self):
        with patch.dict(os.environ, {"DISCOVERY_MAX_WORKERS": "8"}):
            self.assertEqual(_discovery_worker_cap(20), 8)
            self.assertEqual(_discovery_worker_cap(3), 3)

    def test_off_is_one_per_source(self):
        with patch.dict(os.environ, {"DISCOVERY_MAX_WORKERS": "0"}):
            self.assertEqual(_discovery_worker_cap(20), 20)

    def test_empty_sources_at_least_one(self):
        self.assertEqual(_discovery_worker_cap(0), 1)


if __name__ == "__main__":
    unittest.main()
