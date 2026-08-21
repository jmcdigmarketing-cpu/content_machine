"""Background clip anti-repeat — in-memory, no data/ writes."""

from __future__ import annotations

import random
import unittest

from assets.clip_memory import pick_unseen, recent, record, reset


class TestClipMemory(unittest.TestCase):
    def setUp(self):
        reset()

    def tearDown(self):
        reset()

    def test_skips_recent_when_alternatives_exist(self):
        rng = random.Random(0)
        first = pick_unseen(["a.mp4", "b.mp4"], rng=rng)
        second = pick_unseen(["a.mp4", "b.mp4"], rng=random.Random(1))
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        # With two clips, the second pick should prefer the unseen one.
        self.assertNotEqual(first, second)

    def test_fail_open_when_all_seen(self):
        record("only.mp4")
        choice = pick_unseen(["only.mp4"], rng=random.Random(0))
        self.assertTrue(choice.endswith("only.mp4") or "only.mp4" in choice)

    def test_empty_candidates(self):
        self.assertIsNone(pick_unseen([]))
        self.assertEqual(recent(), [])


if __name__ == "__main__":
    unittest.main()
