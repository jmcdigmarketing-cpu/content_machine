"""Tests for the cross-run quota/credit state store (core/quota_state)."""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from core import quota_state


class TestQuotaState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "quota_state.json")
        self._patch = patch.object(quota_state, "QUOTA_STATE_FILE", self.path)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_mark_and_check(self):
        quota_state.mark_exhausted("apify", "main", "402 out of credits", ttl_seconds=3600)
        exhausted, reason = quota_state.is_exhausted("apify", "main")
        self.assertTrue(exhausted)
        self.assertEqual(reason, "402 out of credits")

    def test_persists_across_reload(self):
        quota_state.mark_exhausted("apify", "main", "r", ttl_seconds=3600)
        self.assertTrue(os.path.exists(self.path))
        # A fresh read (simulating a new process) still sees it.
        self.assertTrue(quota_state.is_exhausted("apify", "main")[0])

    def test_expired_record_reads_as_clear(self):
        quota_state.mark_exhausted("apify", "main", "r", ttl_seconds=-1)
        self.assertFalse(quota_state.is_exhausted("apify", "main")[0])

    def test_clear(self):
        quota_state.mark_exhausted("llm", "openrouter", "r", ttl_seconds=3600)
        quota_state.clear_exhausted("llm", "openrouter")
        self.assertFalse(quota_state.is_exhausted("llm", "openrouter")[0])

    def test_scopes_dont_collide(self):
        quota_state.mark_exhausted("apify", "main", "a", ttl_seconds=3600)
        self.assertFalse(quota_state.is_exhausted("llm", "main")[0])

    def test_kv_roundtrip(self):
        quota_state.set_value("apify_usage:main", {"usage": 1.5, "limit": 5.0}, 3600)
        self.assertEqual(quota_state.get_value("apify_usage:main"), {"usage": 1.5, "limit": 5.0})

    def test_kv_expiry(self):
        quota_state.set_value("k", "v", -1)
        self.assertIsNone(quota_state.get_value("k"))
        self.assertEqual(quota_state.get_value("k", "default"), "default")

    def test_reset_all(self):
        quota_state.mark_exhausted("apify", "main", "r", ttl_seconds=3600)
        quota_state.set_value("k", "v", 3600)
        quota_state.reset_all()
        self.assertFalse(quota_state.is_exhausted("apify", "main")[0])
        self.assertIsNone(quota_state.get_value("k"))

    def test_corrupt_file_fails_open(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{ not valid json")
        # Reads degrade to "not exhausted" instead of raising.
        self.assertFalse(quota_state.is_exhausted("apify", "main")[0])


if __name__ == "__main__":
    unittest.main()
