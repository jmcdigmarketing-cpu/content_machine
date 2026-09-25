"""#455 shared quota-state isolation fixture.

A test that forgets to isolate data/quota_state.json poisons the operator breaker.
This mixin is the shared seam; GovernorCase must use it.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from tests.isolation import IsolatedQuotaStore


class TestSharedQuotaIsolation(IsolatedQuotaStore, unittest.TestCase):
    def test_writes_land_in_the_temp_store_not_repo_data(self):
        from core import quota_state

        quota_state.set_value("stage2-isolation", "ok", 3600)
        self.assertTrue(Path(self.quota_state_file).is_file())
        repo_data = Path(__file__).resolve().parents[1] / "data" / "quota_state.json"
        self.assertNotEqual(Path(quota_state.QUOTA_STATE_FILE).resolve(), repo_data.resolve())
        self.assertEqual(quota_state.get_value("stage2-isolation"), "ok")

    def test_governor_case_is_the_shared_mixin(self):
        from tests.test_quota_governor import GovernorCase

        self.assertTrue(issubclass(GovernorCase, IsolatedQuotaStore))
