"""Credit-efficiency wave 1: Apify breaker persistence (O2/O3) + preflight skip (O1)."""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from apis import apify_client, register_signals
from core import quota_state


class TestApifyPersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "quota_state.json")
        self._patch = patch.object(quota_state, "QUOTA_STATE_FILE", self.path)
        self._patch.start()
        quota_state.reset_all()
        apify_client.reset_apify_state()

    def tearDown(self):
        apify_client.reset_apify_state()
        quota_state.reset_all()
        self._patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_hard_failure_persists_and_disables_next_run(self):
        # Simulate a prior run hitting a hard 402.
        apify_client._persist_exhausted("main", "402 out of credits")
        # New "process": clear in-memory breaker, then sync from persisted state.
        apify_client.reset_apify_state()
        self.assertFalse(apify_client.apify_disabled())  # not synced yet
        apify_client._sync_persistent("main")
        self.assertTrue(apify_client.apify_disabled())
        self.assertIn("persisted", apify_client.apify_status())

    def test_run_actor_short_circuits_on_persisted_state(self):
        apify_client._persist_exhausted("main", "402")
        apify_client.reset_apify_state()
        # No network: run_actor returns None immediately via the persisted breaker.
        with patch.object(apify_client.requests, "post") as mock_post:
            result = apify_client.run_actor("user~actor", {"q": "x"})
        self.assertIsNone(result)
        mock_post.assert_not_called()

    def test_usage_cache_skips_network_preflight(self):
        # A fresh, non-exhausted usage reading lets preflight skip the network.
        quota_state.set_value("apify_usage:main", {"usage": 1.0, "limit": 10.0}, 1200)
        with patch.dict("os.environ", {"APIFY_CONTENT_MACHINE_KEY": "key"}, clear=False):
            with patch.object(apify_client.requests, "get") as mock_get:
                ok, status = apify_client.apify_preflight()
        self.assertTrue(ok)
        self.assertIn("cached", status)
        mock_get.assert_not_called()


class TestWillUseApify(unittest.TestCase):
    def test_false_when_no_paid_social_signal_active(self):
        active = (("youtube", None), ("trends", None), ("news", None))
        with patch.object(register_signals, "_active_signal_sources", return_value=active):
            self.assertFalse(register_signals.will_use_apify("some gaming topic"))

    def test_true_when_a_paid_apify_signal_is_active(self):
        active = (("youtube", None), ("reddit", None))
        with patch.object(register_signals, "_active_signal_sources", return_value=active):
            self.assertTrue(register_signals.will_use_apify("some topic"))

    def test_fail_safe_true_on_error(self):
        with patch.object(register_signals, "_active_signal_sources", side_effect=RuntimeError):
            self.assertTrue(register_signals.will_use_apify("x"))


if __name__ == "__main__":
    unittest.main()
