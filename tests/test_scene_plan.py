"""Tests for scene-matched B-roll: planning + concat builder + fallback."""

import unittest
from unittest.mock import patch

from assets import composite
from video.scene_plan import Scene, plan_scenes


class TestPlanScenes(unittest.TestCase):
    def test_empty_inputs(self):
        self.assertEqual(plan_scenes("", "topic", 10.0), [])
        self.assertEqual(plan_scenes("words here", "topic", 0.0), [])

    def test_single_scene_for_short_script(self):
        scenes = plan_scenes("Kape wins big tonight", "MMA rankings", 5.0)
        self.assertEqual(len(scenes), 1)
        self.assertEqual(scenes[0].start, 0.0)
        self.assertEqual(scenes[0].end, 5.0)

    def test_multiple_scenes_cover_duration(self):
        script = " ".join(f"word{i}" for i in range(40)) + "."
        scenes = plan_scenes(script, "NBA trades", 20.0, max_scenes=4)
        self.assertGreaterEqual(len(scenes), 2)
        self.assertEqual(scenes[0].start, 0.0)
        self.assertAlmostEqual(scenes[-1].end, 20.0, places=2)
        # Windows are contiguous and increasing.
        import itertools

        for a, b in itertools.pairwise(scenes):
            self.assertLessEqual(a.end, b.start + 0.001)

    def test_query_includes_topic_and_beat_keyword(self):
        script = "Giannis Antetokounmpo joined the Heat. " + " ".join(f"x{i}" for i in range(20))
        scenes = plan_scenes(script, "NBA trades", 12.0, max_scenes=2)
        self.assertTrue(any("NBA trades" in s.query for s in scenes))
        self.assertTrue(any("Giannis" in s.query for s in scenes))

    def test_uses_word_timings_when_present(self):
        tokens = [f"w{i}" for i in range(20)]
        script = " ".join(tokens)
        words = [{"word": t, "start": i * 0.5, "end": i * 0.5 + 0.5} for i, t in enumerate(tokens)]
        scenes = plan_scenes(script, "topic", 10.0, words=words, max_scenes=2)
        # First scene starts at the first word's real start time.
        self.assertAlmostEqual(scenes[0].start, 0.0, places=2)


class TestMultiConcatCommand(unittest.TestCase):
    def test_builds_n_inputs(self):
        cmd = composite.build_multi_concat_command(
            [("a.mp4", 2.0), ("b.mp4", 3.0), ("c.mp4", 2.0)], "out.mp4", duration=7.0
        )
        self.assertEqual(cmd.count("-i"), 3)
        joined = " ".join(cmd)
        self.assertIn("concat=n=3", joined)
        self.assertIn("a.mp4", joined)
        self.assertIn("out.mp4", joined)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            composite.build_multi_concat_command([], "out.mp4", duration=5.0)


class TestSceneMatchedFallback(unittest.TestCase):
    def test_disabled_returns_none(self):
        from assets import manager

        with patch.dict("os.environ", {"SCENE_MATCHED_BROLL": "false"}, clear=False):
            self.assertIsNone(
                manager.get_scene_matched_background("t", "script words", duration=10.0)
            )

    def test_missing_clip_falls_back_to_none(self):
        from assets import manager

        long_script = " ".join(f"word{i}" for i in range(40)) + "."
        with patch.dict("os.environ", {"SCENE_MATCHED_BROLL": "true"}, clear=False):
            with patch.object(manager, "get_stock_background_asset", return_value=None):
                result = manager.get_scene_matched_background("topic", long_script, duration=20.0)
        self.assertIsNone(result)  # any missing clip → fall back, never break

    def test_scene_dataclass(self):
        s = Scene(query="q", start=0.0, end=1.0, text="t")
        self.assertEqual(s.query, "q")


if __name__ == "__main__":
    unittest.main()
