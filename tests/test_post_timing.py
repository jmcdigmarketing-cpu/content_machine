import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from analytics.post_timing import (
    next_optimal_post_time,
    slots_for_topic,
)


class TestPostTiming(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(os.environ, {"USE_LEARNED_POST_SLOTS": "false"})
        self._env.start()

    def tearDown(self):
        self._env.stop()

    def test_tapin_ufc_uses_domain_slots(self):
        gaming = {s.weekday for s in slots_for_topic("tapin", "GTA 6 release")}
        ufc = {s.weekday for s in slots_for_topic("tapin", "UFC 250 predictions")}
        self.assertIn(5, gaming)
        self.assertIn(3, ufc)

    def test_next_slot_is_in_future(self):
        after = datetime(2026, 6, 4, 14, 0, tzinfo=timezone.utc)
        nxt = next_optimal_post_time("tapin", "gaming news", after=after)
        self.assertGreater(nxt, after)

    def test_next_slot_respects_weekday(self):
        after = datetime(2026, 6, 4, 10, 0, tzinfo=timezone.utc)
        nxt = next_optimal_post_time("tapin", "Marvel Rivals", after=after)
        self.assertIsNotNone(nxt.tzinfo)


if __name__ == "__main__":
    unittest.main()
