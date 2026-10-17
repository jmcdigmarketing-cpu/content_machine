"""Corrections to Cursor's waves of 2026-10-16, found reviewing them before the push.

- #1229: `overnight._draft_one` ran each draft with `capture_output=True` and never printed it -
  every warning of a draft, and the faulthandler traceback #1216 added for exactly this crash,
  stopped reaching `output/logs/overnight-last.log`.
- #1043: `clips_for_topic` dropped every untagged clip for a topic that names a team. The
  operator's files are untagged: "Tennessee Titans at Indianapolis Colts" kept 0 of 13 Madden
  clips and "Cleveland Cavaliers at Orlando Magic" 0 of 72 2K clips.
- #1228: `shot_timeout(6.8)` became 204 s, and the ultrafast retry the same - a stuck shot could
  hold a render about seven minutes where it used to hold two. `-nostdin` is the cure for a hang.
- #545: the "What I got wrong last time" sentence went after "Tap in for more." and onto every
  later script of the franchise; the item asks for the next script.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

TITANS = "Tennessee Titans at Indianapolis Colts"
CHARGERS = "Chargers Hopeium going into week 5"
MADDEN = [os.path.join("video", "backgrounds", "gaming", "sports", "Madden 26", f"GameClip_{i}.mp4")
          for i in range(3)]  # fmt: skip


class OvernightChildTests(unittest.TestCase):
    def test_the_childs_output_reaches_the_log(self):
        from core import overnight

        seen = {}

        def run(argv, **kwargs):
            seen.update(kwargs)
            return SimpleNamespace(returncode=0)

        with patch("subprocess.run", side_effect=run):
            overnight._draft_one("tapin", "Bo Nickal vs Joe Pyfer", key_facts=None, pick=None)
        self.assertFalse(seen.get("capture_output"))
        self.assertNotIn("stdout", seen)
        self.assertNotIn("stderr", seen)


class FootageTests(unittest.TestCase):
    def test_a_game_topic_keeps_the_untagged_madden_clips(self):
        from assets.clip_tags import clips_for_topic

        self.assertEqual(clips_for_topic(MADDEN, TITANS, {"clips": {}}), MADDEN)

    def test_a_clip_tagged_for_another_team_is_left_out(self):
        from assets.clip_tags import clips_for_topic

        chiefs = os.path.join("video", "backgrounds", "gaming", "sports", "Madden 26", "kc.mp4")
        index = {"clips": {chiefs: {"teams": ["Kansas City Chiefs"]}}}
        self.assertEqual(clips_for_topic([chiefs, *MADDEN], CHARGERS, index), MADDEN)

    def test_a_tagged_match_is_used_alone(self):
        from assets.clip_tags import clips_for_topic

        bolts = os.path.join("video", "backgrounds", "gaming", "sports", "Madden 26", "lac.mp4")
        index = {"clips": {bolts: {"teams": ["Los Angeles Chargers"]}}}
        self.assertEqual(clips_for_topic([*MADDEN, bolts], CHARGERS, index), [bolts])


class ShotTimeoutTests(unittest.TestCase):
    def test_a_try_is_held_to_the_old_two_minutes(self):
        from assets.fast_cut import shot_timeout

        self.assertLessEqual(shot_timeout(6.8), 120)
        self.assertLessEqual(shot_timeout(30.0), 120)
        self.assertGreaterEqual(shot_timeout(2.0), 45)


class CorrectionBeatTests(unittest.TestCase):
    def _store(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = patch("core.negative_facts.STORE_PATH", Path(tmp.name) / "negative_facts.json")
        store.start()
        self.addCleanup(store.stop)

    def test_the_beat_comes_before_the_closing_line(self):
        from core.negative_facts import record_negative, with_correction_beat

        self._store()
        record_negative("ufc", "Pereira retired in March 2024", reason="source retracted")
        script = with_correction_beat(
            "The division is still open this weekend. Tap in for more.",
            "UFC Contender Series prospects",
            "tapin",
        )
        self.assertTrue(script.endswith("Tap in for more."), script)
        self.assertIn("What I got wrong last time: Pereira retired in March 2024.", script)

    def test_it_is_said_once(self):
        from core.negative_facts import record_negative, with_correction_beat

        self._store()
        record_negative("ufc", "Pereira retired in March 2024", reason="source retracted")
        first = with_correction_beat("One. Tap in.", "UFC Contender Series prospects", "tapin")
        second = with_correction_beat("Two. Tap in.", "UFC Contender Series prospects", "tapin")
        self.assertIn("What I got wrong", first)
        self.assertEqual(second, "Two. Tap in.")


if __name__ == "__main__":
    unittest.main()
