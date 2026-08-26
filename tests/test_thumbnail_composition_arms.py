"""A2: thumbnail_style named-slot arms stay selectable and do not leak into scripts."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from core import experiments as ex
from core.experiment_levers import arms, directive, kind


class ExperimentCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        import config.paths as paths

        self._patch = patch.object(
            paths, "EXPERIMENTS_FILE", os.path.join(self._tmp.name, "experiments.json")
        )
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()


class TestCompositionArms(ExperimentCase):
    def test_new_arms_are_selectable_thumbnail_kind(self):
        names = arms("thumbnail_style")
        self.assertIn("close_up", names)
        self.assertIn("wide_drama", names)
        self.assertIn("subject_scale", names)
        self.assertIn("text_negative_space", names)
        self.assertIn("hard_light", names)
        self.assertEqual(kind("thumbnail_style"), "thumbnail")
        for arm in ("subject_scale", "text_negative_space", "hard_light"):
            text = directive("thumbnail_style", arm).lower()
            self.assertTrue(text, arm)
            self.assertNotIn("hook experiment", text)

    def test_composition_arms_do_not_leak_into_script_prompts(self):
        ex.start_experiment("tapin", "thumbnail_style")
        self.assertIsNone(ex.next_arm("tapin", kind="script"))
        picked = ex.next_arm("tapin", kind="thumbnail")
        self.assertIsNotNone(picked)
        self.assertEqual(picked[0], "thumbnail_style")
        self.assertIn(picked[1], arms("thumbnail_style"))
        self.assertEqual(kind(picked[0]), "thumbnail")


if __name__ == "__main__":
    unittest.main()
