"""Tests for core/quota_governor.py — persisted signal breaker records with
key-hash invalidation (the O11 seed). State file always isolated."""

import os
import tempfile
import unittest
from unittest.mock import patch

from core import quota_governor as qg
from core import quota_state


class GovernorCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._state_patch = patch.object(
            quota_state, "QUOTA_STATE_FILE", os.path.join(self._tmp.name, "q.json")
        )
        self._state_patch.start()

    def tearDown(self):
        self._state_patch.stop()
        self._tmp.cleanup()


class TestPersistRoundtrip(GovernorCase):
    def test_disable_then_read_back(self):
        qg.disable_signal("finnhub", "no_key: missing FINNHUB_API_KEY")
        out = qg.persisted_disabled_signals()
        self.assertEqual(out, {"finnhub": "no_key: missing FINNHUB_API_KEY"})

    def test_clear_signal(self):
        qg.disable_signal("finnhub", "no_key")
        qg.clear_signal("finnhub")
        self.assertEqual(qg.persisted_disabled_signals(), {})

    def test_clear_all_signals(self):
        qg.disable_signal("finnhub", "no_key")
        qg.disable_signal("rawg", "quota_exceeded")
        qg.clear_all_signals()
        self.assertEqual(qg.persisted_disabled_signals(), {})

    def test_ttl_expiry(self):
        qg.disable_signal("finnhub", "no_key", ttl_seconds=-1)
        self.assertEqual(qg.persisted_disabled_signals(), {})

    def test_persist_disabled_via_env(self):
        with patch.dict("os.environ", {"SIGNAL_BREAKER_PERSIST": "false"}):
            qg.disable_signal("finnhub", "no_key")
            self.assertEqual(qg.persisted_disabled_signals(), {})
        # Nothing was written while off.
        self.assertEqual(qg.persisted_disabled_signals(), {})

    def test_signal_scope_does_not_leak_into_apify_scope(self):
        qg.disable_signal("reddit", "quota_exceeded")
        exhausted, _ = quota_state.is_exhausted("apify", "main")
        self.assertFalse(exhausted)


class TestKeyHashInvalidation(GovernorCase):
    def test_stable_key_keeps_record(self):
        with patch.dict("os.environ", {"FINNHUB_API_KEY": "k1"}):
            qg.disable_signal("finnhub", "auth_error")
            self.assertIn("finnhub", qg.persisted_disabled_signals())
            self.assertIn("finnhub", qg.persisted_disabled_signals())  # still there

    def test_changed_key_clears_record(self):
        with patch.dict("os.environ", {"FINNHUB_API_KEY": "k1"}):
            qg.disable_signal("finnhub", "auth_error")
        with patch.dict("os.environ", {"FINNHUB_API_KEY": "k2"}):
            self.assertEqual(qg.persisted_disabled_signals(), {})
        # Cleared permanently, not just filtered.
        with patch.dict("os.environ", {"FINNHUB_API_KEY": "k1"}):
            self.assertEqual(qg.persisted_disabled_signals(), {})

    def test_any_env_in_the_tuple_invalidates(self):
        creds = {
            "APIFY_CONTENT_MACHINE_KEY": "a",
            "REDDIT_CLIENT_ID": "b",
            "REDDIT_CLIENT_SECRET": "c",
        }
        with patch.dict("os.environ", creds):
            qg.disable_signal("reddit", "auth_error")
        with patch.dict("os.environ", {**creds, "REDDIT_CLIENT_SECRET": "rotated"}):
            self.assertEqual(qg.persisted_disabled_signals(), {})

    def test_unlisted_signal_is_ttl_only(self):
        # No credential mapping -> record holds regardless of env churn.
        qg.disable_signal("wikipedia", "upstream_error")
        with patch.dict("os.environ", {"FINNHUB_API_KEY": "irrelevant-change"}):
            self.assertIn("wikipedia", qg.persisted_disabled_signals())


if __name__ == "__main__":
    unittest.main()
