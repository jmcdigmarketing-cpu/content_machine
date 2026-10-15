"""#388: cooldown jitter and a per-host cap on the discovery pool.

#41 caps how many signals run at once. It does not stop two YouTube signals
starting together, and a 429 cooldown of exactly 900s wakes them together.
"""

from __future__ import annotations

import os
import random
import threading
import time
import unittest
from unittest.mock import patch


class CooldownJitterTests(unittest.TestCase):
    def test_two_cooldowns_do_not_share_a_wake_time(self):
        from apis.register_signals import jittered_cooldown

        rng = random.Random(0)
        first = jittered_cooldown(900, now=1_000.0, rng=rng)
        second = jittered_cooldown(900, now=1_000.0, rng=rng)
        self.assertNotEqual(first, second)
        self.assertGreaterEqual(min(first, second), 1_000.0 + 450)
        self.assertLessEqual(max(first, second), 1_000.0 + 1_350)


class HostCapTests(unittest.TestCase):
    def _spans(self, names: list[str]) -> list[tuple[float, float]]:
        from apis.register_signals import in_host_slot

        spans: list[tuple[float, float]] = []
        lock = threading.Lock()

        def slow():
            start = time.perf_counter()
            time.sleep(0.08)
            with lock:
                spans.append((start, time.perf_counter()))

        threads = [
            threading.Thread(target=lambda name=name: in_host_slot(name, slow)) for name in names
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(2)
        return spans

    def test_two_youtube_signals_do_not_overlap_when_the_cap_is_one(self):
        with patch.dict(os.environ, {"DISCOVERY_HOST_CONCURRENCY": "1"}):
            spans = self._spans(["youtube", "youtube_comments"])
        self.assertEqual(len(spans), 2)
        spans.sort()
        self.assertGreaterEqual(spans[1][0], spans[0][1] - 0.01)

    def test_two_unmapped_signals_may_overlap(self):
        with patch.dict(os.environ, {"DISCOVERY_HOST_CONCURRENCY": "1"}):
            spans = self._spans(["blog_rss", "blog_rss"])
        self.assertEqual(len(spans), 2)
        spans.sort()
        self.assertLess(spans[1][0], spans[0][1])
