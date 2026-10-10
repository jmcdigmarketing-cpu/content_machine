"""#1045: one file does not fill a video, and a clip from the last videos is not next."""

from __future__ import annotations

import os
import random
import unittest

from assets.clip_memory import reset


class TestClipVariety(unittest.TestCase):
    def tearDown(self):
        reset()

    def test_one_file_does_not_fill_the_video_while_another_is_free(self):
        from assets.fast_cut import cut_points, plan_windowed_shots

        keys = [f"a.mp4#{i}" for i in range(6)] + ["b.mp4"]
        windows = {f"a.mp4#{i}": ("a.mp4", float(i * 30), 30.0) for i in range(6)}
        windows["b.mp4"] = ("b.mp4", 0.0, 40.0)
        shots = plan_windowed_shots(cut_points(40.0), keys, windows, rng=random.Random(0))
        cap = 2
        counts: dict[str, int] = {}
        sources = {"a.mp4", "b.mp4"}
        early = False
        for path, _start, _length in shots:
            counts[path] = counts.get(path, 0) + 1
            if counts[path] > cap and any(counts.get(other, 0) < cap for other in sources):
                early = True
        self.assertFalse(early, counts)

    def test_a_recent_clip_is_left_out_when_another_exists(self):
        from assets.fast_cut import pool_without_recent

        a = os.path.abspath("a.mp4")
        b = os.path.abspath("b.mp4")
        remembered = {os.path.normcase(a)}
        self.assertEqual(pool_without_recent([a, b], remembered), [b])
        self.assertEqual(pool_without_recent([a], remembered), [a])
