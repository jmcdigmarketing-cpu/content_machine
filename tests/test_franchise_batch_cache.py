"""#42 share discovery cache across franchise-anchor topics inside one run_batch."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from apis.register_signals import _fetch_one, franchise_batch_cache
from apis.signal_contract import make_signal


class TestFranchiseBatchCache(unittest.TestCase):
    def test_second_gta_topic_does_not_hit_the_network(self):
        calls: list[str] = []

        def fake(topic: str):
            calls.append(topic)
            return make_signal(connected=True, active=True, score=1.0, data={"t": topic})

        with (
            franchise_batch_cache(["GTA 6 leak week 1", "GTA 6 trailer rumours"]),
            patch("apis.register_signals._record_signal_health"),
        ):
            _fetch_one("tiktok_trends", fake, "GTA 6 leak week 1")
            _fetch_one("tiktok_trends", fake, "GTA 6 trailer rumours")
        self.assertEqual(len(calls), 1)

    def test_without_batch_scope_topics_are_fetched_separately(self):
        calls: list[str] = []

        def fake(topic: str):
            calls.append(topic)
            return make_signal(connected=True, active=True, score=1.0, data={"t": topic})

        with patch("apis.register_signals._record_signal_health"):
            _fetch_one("youtube_competitors", fake, "GTA 6 leak unique-a")
            _fetch_one("youtube_competitors", fake, "GTA 6 trailer unique-b")
        self.assertEqual(len(calls), 2)
