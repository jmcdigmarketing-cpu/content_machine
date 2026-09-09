"""Defects found auditing Cursor's 96d6d1a (review 7).

Every test here was observed failing on unmodified 96d6d1a for the reason named
in its docstring.
"""

from __future__ import annotations

import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image


def _frame(dest: Path, *, plain_top: bool) -> Path:
    """A 1080x1920 frame. `plain_top` is the commonest b-roll composition: a flat
    sky over a detailed lower half. No HUD, no score bug, nothing overlaid."""
    random.seed(7)
    img = Image.new("RGB", (270, 480))
    px = img.load()
    for y in range(480):
        for x in range(270):
            if plain_top and y < 240:
                px[x, y] = (135, 180, 235)
            elif plain_top:
                px[x, y] = (
                    random.randint(20, 90),
                    random.randint(70, 140),
                    random.randint(20, 70),
                )
            else:
                px[x, y] = (28, 32, 40)
    img.save(dest)
    return dest


class TestAutoCaptionPlacementIsGated(unittest.TestCase):
    """#713 moves karaoke captions to ASS Alignment 8 when the bottom eighth has
    more unique chroma than the top. That runs on every karaoke render with no
    flag, and the detector measures *colour variety*, not whether a HUD is there.

    Measured on unmodified 96d6d1a: a flat sky over a textured lower half -- an
    ordinary outdoor shot -- scores top=1 / bottom=87 and relocates every caption
    to the top of the video. Cursor's own tests use a synthetic full-frame noise
    PNG, which is the detector's best case, so nothing caught it.

    #717 already concedes "chroma is not a face". A detector that admits it cannot
    tell a HUD from a landscape must not silently restyle finished video: this repo
    keeps uncertain visual features behind a default-off flag (SCENE_MATCHED_BROLL,
    LUFS_NORMALIZE). Same treatment here until #717 lands.
    """

    def test_an_ordinary_sky_over_ground_shot_keeps_captions_at_the_bottom(self):
        from video.caption_place import choose_caption_anchor

        with tempfile.TemporaryDirectory() as tmp:
            path = _frame(Path(tmp) / "broll.png", plain_top=True)
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("CAPTION_AUTO_PLACE", None)
                anchor = choose_caption_anchor(str(path))
        self.assertEqual(
            anchor,
            "bottom",
            "a plain sky over detailed ground moved captions to the top of the video",
        )

    def test_the_flag_is_what_turns_the_heuristic_on(self):
        """The work is kept, not deleted -- it just stops being the default."""
        from video.caption_place import choose_caption_anchor

        with tempfile.TemporaryDirectory() as tmp:
            path = _frame(Path(tmp) / "broll.png", plain_top=True)
            with patch.dict(os.environ, {"CAPTION_AUTO_PLACE": "true"}):
                anchor = choose_caption_anchor(str(path))
        self.assertEqual(anchor, "top")

    def test_a_quiet_frame_stays_bottom_with_the_flag_on(self):
        from video.caption_place import choose_caption_anchor

        with tempfile.TemporaryDirectory() as tmp:
            path = _frame(Path(tmp) / "flat.png", plain_top=False)
            with patch.dict(os.environ, {"CAPTION_AUTO_PLACE": "true"}):
                anchor = choose_caption_anchor(str(path))
        self.assertEqual(anchor, "bottom")

    def test_a_missing_background_is_still_bottom(self):
        from video.caption_place import choose_caption_anchor

        with patch.dict(os.environ, {"CAPTION_AUTO_PLACE": "true"}):
            self.assertEqual(choose_caption_anchor(None), "bottom")
            self.assertEqual(choose_caption_anchor(""), "bottom")

    def test_the_burned_ass_keeps_alignment_2_by_default(self):
        """The end-to-end guarantee: with the flag unset, a busy-bottom background
        produces the same bottom-anchored ASS it did before #713."""
        import json

        from video.subtitles import generate_subtitle_file

        words = [
            {"word": w, "start": i * 0.4, "end": i * 0.4 + 0.35}
            for i, w in enumerate("Jones beat Pereira at UFC three twenty".split())
        ]
        with tempfile.TemporaryDirectory() as tmp:
            mp3 = os.path.join(tmp, "vo.mp3")
            with open(mp3, "wb") as fh:
                fh.write(b"x")
            with open(mp3 + ".words.json", "w", encoding="utf-8") as fh:
                json.dump(words, fh)
            background = str(_frame(Path(tmp) / "broll.png", plain_top=True))
            os.environ.pop("CAPTION_AUTO_PLACE", None)
            out = generate_subtitle_file(
                "Jones beat Pereira at UFC three twenty",
                4.0,
                audio_path=mp3,
                channel_id="tapin",
                output_path=os.path.join(tmp, "vo.ass"),
                background_path=background,
            )
            with open(out, encoding="utf-8") as fh:
                text = fh.read()

        self.assertTrue(out.endswith(".ass"))
        self.assertIn(",2,80,80,260,1", text)
        self.assertNotIn(",8,80,80,260,1", text)


class TestFfmpegIsActuallyPresentInCI(unittest.TestCase):
    """#415 installed ffmpeg in CI and `render_smoke.require_ffmpeg` raises there
    if it is missing -- but nothing calls that un-patched, and every ffmpeg test
    is a bare `skipUnless(shutil.which("ffmpeg"))`. So if the apt-get step breaks,
    the three technical-QC classes and the 2s smoke all skip and the run still
    reports OK. Same shape as #711: the proof evaporates with nothing to say so.
    """

    def test_ci_must_not_silently_skip_every_ffmpeg_test(self):
        import shutil

        if os.getenv("CI", "").strip().lower() not in ("1", "true", "yes"):
            self.skipTest("not CI; ffmpeg is optional locally")
        self.assertIsNotNone(
            shutil.which("ffmpeg"),
            "ffmpeg is not on PATH in CI, so technical QC (#414/#420/#498) and the "
            "#415 render smoke skipped instead of running",
        )


if __name__ == "__main__":
    unittest.main()
