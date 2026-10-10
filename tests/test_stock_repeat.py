"""#1041 stock is the last resort: not twice in one video, not in the last N videos,
and the run card says so.
"""

from __future__ import annotations

import unittest

from assets.clip_memory import begin_video, choose_stock_path, note_used, record, reset
from assets.manager import footage_quality
from assets.types import AssetResult
from core.run_ledger import footage_card_line


class TestStockAntiRepeat(unittest.TestCase):
    def setUp(self):
        reset()

    def tearDown(self):
        reset()

    def test_a_clip_used_in_this_video_is_not_picked_again(self):
        first = choose_stock_path(["a.mp4", "b.mp4"])
        note_used(first or "")
        second = choose_stock_path(["a.mp4", "b.mp4"])
        self.assertEqual(first, "a.mp4")
        self.assertEqual(second, "b.mp4")

    def test_the_last_n_videos_are_skipped_when_another_clip_exists(self):
        for i in range(8):
            record(f"old{i}.mp4")
        begin_video()
        choice = choose_stock_path([f"old{i}.mp4" for i in range(8)] + ["new.mp4"])
        self.assertEqual(choice, "new.mp4")

    def test_repeats_only_when_every_candidate_was_used(self):
        record("only.mp4")
        begin_video()
        self.assertEqual(choose_stock_path(["only.mp4"]), "only.mp4")
        note_used("a.mp4")
        note_used("b.mp4")
        again = choose_stock_path(["a.mp4", "b.mp4"])
        self.assertIn(again, ("a.mp4", "b.mp4"))


class TestFootageOnTheRunCard(unittest.TestCase):
    def test_stock_label_is_what_the_card_prints(self):
        quality = footage_quality(AssetResult(path="clip.mp4", provider="pexels"))
        line = footage_card_line(quality)
        self.assertIn("STOCK", quality["footage"])
        self.assertIn("last resort", quality["footage"])
        self.assertIn(quality["footage"], line)


if __name__ == "__main__":
    unittest.main()
