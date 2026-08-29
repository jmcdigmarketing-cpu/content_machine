"""#389 serve stale cache on live failure, 48h ceiling, never equal to fresh.

Calls the real get_cached / _fetch_one. Cache file is the suite isolate; keys are
unique. Clock is frozen. No network.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from apis import cache_manager as cm
from apis import register_signals as rs
from apis.signal_contract import (
    STATUS_INACTIVE,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    make_signal,
)

NOW = 1_700_000_000.0


def _good(**extra):
    sig = make_signal(
        connected=True,
        active=True,
        score=0.8,
        data={"facts": ["Take-Two confirmed the leak investigation"]},
        status=STATUS_OK,
        status_detail="ok",
    )
    sig.update(extra)
    return sig


class TestStaleCacheServe(unittest.TestCase):
    def setUp(self):
        cm.reset_cache_stats()

    def _plant(self, key: str, payload: dict, *, age_hours: float, ttl: int = 3600) -> None:
        written_at = NOW - age_hours * 3600
        with patch("apis.cache_manager.time.time", return_value=written_at):
            cm.set_cache(key, payload, ttl_seconds=ttl)

    def _fetch(self, name: str, topic: str, live):
        with patch("apis.cache_manager.time.time", return_value=NOW):
            return rs._fetch_one(name, live, topic)

    def test_fresh_hit_does_not_call_live(self):
        topic = "stale-fresh-hit"
        key = cm.build_key("wikipedia", topic)
        self._plant(key, _good(), age_hours=0.5, ttl=3 * 3600)
        called = {"n": 0}

        def live(_topic):
            called["n"] += 1
            return make_signal(connected=False, active=False, status=STATUS_UNAVAILABLE)

        name, sig = self._fetch("wikipedia", topic, live)
        self.assertEqual(name, "wikipedia")
        self.assertEqual(sig.get("status"), STATUS_OK)
        self.assertEqual(called["n"], 0)
        self.assertFalse(sig.get("stale"))

    def test_live_unavailable_serves_10h_payload_flagged_stale_not_a_hit(self):
        topic = "stale-10h-serve"
        key = cm.build_key("tapology", topic)
        self._plant(key, _good(), age_hours=10, ttl=3600)
        hits_before = cm.get_cache_stats()["hits"]

        def live(_topic):
            return make_signal(
                connected=False,
                active=False,
                status=STATUS_UNAVAILABLE,
                status_detail="timeout",
            )

        _name, sig = self._fetch("tapology", topic, live)
        self.assertTrue(sig.get("stale"))
        self.assertIn("STALE cache", sig.get("status_detail") or "")
        self.assertIn("10", sig.get("status_detail") or "")
        self.assertEqual(sig.get("data"), {"facts": ["Take-Two confirmed the leak investigation"]})
        stats = cm.get_cache_stats()
        self.assertEqual(stats["hits"], hits_before)
        self.assertGreaterEqual(stats.get("stale_served", 0), 1)

    def test_live_unavailable_50h_old_is_refused(self):
        topic = "stale-50h-refuse"
        key = cm.build_key("tapology", topic)
        self._plant(key, _good(), age_hours=50, ttl=3600)

        def live(_topic):
            return make_signal(
                connected=False,
                active=False,
                status=STATUS_UNAVAILABLE,
                status_detail="timeout",
            )

        _name, sig = self._fetch("tapology", topic, live)
        self.assertFalse(sig.get("stale"))
        self.assertEqual(sig.get("status"), STATUS_UNAVAILABLE)
        self.assertIn("timeout", sig.get("status_detail") or "")

    def test_live_inactive_does_not_resurrect_stale_hit(self):
        topic = "stale-inactive-no-match"
        key = cm.build_key("wikipedia", topic)
        self._plant(key, _good(), age_hours=10, ttl=3600)

        def live(_topic):
            return make_signal(
                connected=True,
                active=False,
                status=STATUS_INACTIVE,
                status_detail="no page",
            )

        _name, sig = self._fetch("wikipedia", topic, live)
        self.assertFalse(sig.get("stale"))
        self.assertEqual(sig.get("status"), STATUS_INACTIVE)
        self.assertIn("no page", sig.get("status_detail") or "")

    def test_failed_live_fetch_does_not_clobber_eligible_stale_entry(self):
        topic = "stale-no-clobber"
        key = cm.build_key("tapology", topic)
        original = _good()
        self._plant(key, original, age_hours=10, ttl=3600)

        def live(_topic):
            return make_signal(
                connected=False,
                active=False,
                status=STATUS_UNAVAILABLE,
                status_detail="timeout",
            )

        self._fetch("tapology", topic, live)
        stored = cm.load_cache().get(key, {}).get("data")
        self.assertEqual(stored.get("data"), original["data"])
        self.assertEqual(stored.get("status"), STATUS_OK)
