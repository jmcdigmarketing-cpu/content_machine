"""#994: the first caption on screen by 0.5 s.

#988 records what opens each video (the 2.15 s channel intro or the first word). It did not say
when the first words appear: a Short whose first caption comes 0.9 s after the intro shows no
text for the moment the viewer decides to swipe. Now:

- `video.caption_timing.first_cue_seconds` reads the first cue of the subtitle file the render
  burned (written beside the mp4: .ass, else .srt);
- `video.channel_intro.opening_record` keeps `first_caption_s` (in the final video, after any
  intro) and `late_first_caption` (the cue starts later than `FIRST_CAPTION_MAX_S`, 0.5 s, after
  the intro or the start);
- the pipeline passes the cue, and the run card prints it.
"""

from __future__ import annotations

import inspect
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

WORDS = [
    {"word": "The", "start": 0.32, "end": 0.5},
    {"word": "Heat", "start": 0.5, "end": 0.8},
    {"word": "won", "start": 0.8, "end": 1.1},
    {"word": "again.", "start": 1.1, "end": 1.5},
]


class ParseTests(unittest.TestCase):
    def test_the_first_cue_of_a_karaoke_file(self):
        from video.caption_timing import build_ass_karaoke, first_cue_seconds

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "v.ass")
            with open(path, "w", encoding="utf-8") as f:
                f.write(build_ass_karaoke(WORDS))
            self.assertAlmostEqual(first_cue_seconds(path), 0.32, places=2)

    def test_the_first_cue_of_an_srt(self):
        from video.caption_timing import build_srt_from_words, first_cue_seconds

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "v.srt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(build_srt_from_words(WORDS))
            self.assertAlmostEqual(first_cue_seconds(path), 0.32, places=2)

    def test_no_file_or_no_cue_is_none(self):
        from video.caption_timing import first_cue_seconds

        self.assertIsNone(first_cue_seconds(""))
        self.assertIsNone(first_cue_seconds("/nonexistent/v.ass"))

    def test_the_file_beside_the_video(self):
        from video.caption_timing import subtitle_beside

        with tempfile.TemporaryDirectory() as tmp:
            mp4 = os.path.join(tmp, "final.mp4")
            self.assertIsNone(subtitle_beside(mp4))
            open(os.path.join(tmp, "final.srt"), "w").close()
            self.assertTrue(subtitle_beside(mp4).endswith("final.srt"))
            open(os.path.join(tmp, "final.ass"), "w").close()
            self.assertTrue(subtitle_beside(mp4).endswith("final.ass"))  # the burned one


class RecordTests(unittest.TestCase):
    def test_on_time_and_late(self):
        from video.channel_intro import opening_record

        with patch("video.channel_intro._probe_duration", return_value=2.15):
            on_time = opening_record("tapin", True, "/x/intro.mp4", first_cue=0.32)
            late = opening_record("tapin", False, "/x/intro.mp4", first_cue=0.9)
        self.assertEqual(on_time["first_caption_s"], 2.47)
        self.assertFalse(on_time["late_first_caption"])
        self.assertEqual(late["first_caption_s"], 0.9)
        self.assertTrue(late["late_first_caption"])
        unknown = opening_record("tapin", False, None)
        self.assertNotIn("first_caption_s", unknown)

    def test_the_limit_is_configurable(self):
        from video.channel_intro import opening_record

        with patch.dict("os.environ", {"FIRST_CAPTION_MAX_S": "1.0"}):
            self.assertFalse(opening_record("tapin", False, None, first_cue=0.9)
                             ["late_first_caption"])  # fmt: skip

    def test_the_pipeline_passes_the_cue(self):
        from core import pipeline

        source = inspect.getsource(pipeline)
        self.assertIn("first_cue_seconds(", source)
        self.assertIn("first_cue=", source)


class CardTests(unittest.TestCase):
    def _card(self, opening):
        from core.run_ledger import render_dossier

        record = SimpleNamespace(
            id=7, channel_id="tapin", status="done", selected_topic="t", input_topic="t",
            title="T", composite_score=50.0, abort_reason="", features_json="{}",
            quality_json=json.dumps({"opening": opening}), timings_json="{}")  # fmt: skip
        with patch("storage.repositories.content_runs.get_content_run_repository",
                   return_value=type("Repo", (), {"get": lambda self, i: record})()):  # fmt: skip
            return render_dossier(7)

    def test_the_card_says_when_the_first_words_appear(self):
        text = self._card({"intro": True, "intro_seconds": 2.15, "first_caption_s": 2.47,
                           "late_first_caption": False})  # fmt: skip
        self.assertIn("first caption 0.32 s after the intro", text)
        late = self._card({"intro": False, "intro_seconds": 0.0, "first_caption_s": 0.9,
                           "late_first_caption": True})  # fmt: skip
        self.assertIn("LATE", late)
        self.assertIn("0.90 s", late)


if __name__ == "__main__":
    unittest.main()
