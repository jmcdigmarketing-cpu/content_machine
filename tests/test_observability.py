"""Tests for cache-hit instrumentation (O8) and the reliability dashboard (O9)."""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

import config.paths
from apis import cache_manager
from core import reliability


class TestCacheStats(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._patch = patch.object(
            config.paths, "CACHE_STATS_FILE", os.path.join(self.tmp, "c.json")
        )
        self._patch.start()
        cache_manager.reset_cache_stats()

    def tearDown(self):
        cache_manager.reset_cache_stats()
        self._patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_prefix_extraction(self):
        self.assertEqual(cache_manager._prefix_of("reddit::some topic"), "reddit")
        self.assertEqual(cache_manager._prefix_of("apify:user~actor::{json}"), "apify")
        self.assertEqual(cache_manager._prefix_of("weird"), "weird")

    def test_hits_and_misses_recorded(self):
        cache_manager._record_cache_access("reddit::t", True)
        cache_manager._record_cache_access("reddit::t", False)
        cache_manager._record_cache_access("youtube::t", True)
        stats = cache_manager.get_cache_stats()
        self.assertEqual(stats["hits"], 2)
        self.assertEqual(stats["misses"], 1)
        self.assertAlmostEqual(stats["hit_rate"], 2 / 3, places=3)
        self.assertEqual(stats["by_prefix"]["reddit"], {"hits": 1, "misses": 1})

    def test_flush_persists_and_clears_in_process(self):
        cache_manager._record_cache_access("reddit::t", True)
        cache_manager.flush_cache_stats()
        # In-process counters cleared, but persisted file retains them.
        self.assertEqual(cache_manager._stats, {})
        self.assertEqual(cache_manager.get_cache_stats()["hits"], 1)
        # A second flush accumulates on top of the persisted total.
        cache_manager._record_cache_access("reddit::t", True)
        cache_manager.flush_cache_stats()
        self.assertEqual(cache_manager.get_cache_stats()["hits"], 2)

    def test_get_cached_records_miss(self):
        with patch.object(cache_manager, "load_cache", return_value={}):
            result = cache_manager.get_cached("reddit::nothing")
        self.assertIsNone(result)
        self.assertEqual(cache_manager.get_cache_stats()["misses"], 1)

    def test_reset_clears_everything(self):
        cache_manager._record_cache_access("x::y", True)
        cache_manager.flush_cache_stats()
        cache_manager.reset_cache_stats()
        self.assertEqual(cache_manager.get_cache_stats()["total"], 0)


class TestReliability(unittest.TestCase):
    def test_gather_has_all_sections(self):
        data = reliability.gather()
        for key in ("apify", "llm", "signals", "cache", "youtube"):
            self.assertIn(key, data)

    def test_budget_line(self):
        self.assertEqual(reliability._budget_line(None, None), "no budget set")
        self.assertIn("50%", reliability._budget_line(1.0, 2.0))
        self.assertIn("⚠", reliability._budget_line(6.0, 5.0))

    def test_render_smoke(self):
        out = reliability.render(
            {
                "apify": {"status": "ON", "budget": 5.0},
                "llm": {"disabled_providers": {}, "daily_budget": None, "spend_today": 0.0},
                "signals": {"disabled": []},
                "cache": {
                    "hits": 3,
                    "misses": 1,
                    "total": 4,
                    "hit_rate": 0.75,
                    "by_prefix": {"reddit": {"hits": 3, "misses": 1}},
                },
                "youtube": {"used": 100, "limit": 10000, "remaining": 9900},
            }
        )
        self.assertIn("Reliability", out)
        self.assertIn("Apify", out)
        self.assertIn("75% hit rate", out)
        self.assertIn("YouTube units", out)


if __name__ == "__main__":
    unittest.main()
