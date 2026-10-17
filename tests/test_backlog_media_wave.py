"""Fail-first coverage for media backlog items #454, #497, #508, #509 and #511."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image


class RenderLutTests(unittest.TestCase):
    def test_shipped_channels_use_real_distinct_lut_files(self):
        from video.render_video import _resolve_color_lut, build_render_ffmpeg_command

        tapin = _resolve_color_lut("tapin")
        moneywise = _resolve_color_lut("moneywise")
        self.assertTrue(tapin and os.path.isfile(tapin), tapin)
        self.assertTrue(moneywise and os.path.isfile(moneywise), moneywise)
        self.assertNotEqual(Path(tapin).read_bytes(), Path(moneywise).read_bytes())

        cmd = build_render_ffmpeg_command(
            background_path="bg.mp4",
            mp3_path="voice.mp3",
            output_path="out.mp4",
            subtitle_path="captions.srt",
            duration=12.5,
            color_lut=tapin,
        )
        graph = cmd[cmd.index("-filter_complex") + 1]
        self.assertIn("lut3d=", graph)
        self.assertNotIn("eq=", graph)


class RenderArgvGoldenTests(unittest.TestCase):
    def test_every_render_path_matches_the_reviewed_argv(self):
        from video.render_profiles import _PROFILES
        from video.render_video import build_render_ffmpeg_command

        base = {
            "background_path": "bg.mp4",
            "mp3_path": "voice.mp3",
            "output_path": "out.mp4",
            "subtitle_path": "captions.srt",
            "duration": 12.5,
            "channel_id": None,
        }
        with patch("video.encoder.nvenc_wanted", return_value=False):
            actual = {
                "publish_srt": build_render_ffmpeg_command(**base),
                "draft_srt": build_render_ffmpeg_command(**base, render_preset="draft"),
                "landscape_ass": build_render_ffmpeg_command(
                    **{**base, "subtitle_path": "captions.ass"},
                    profile=_PROFILES["landscape"],
                ),
                "music_overlay": build_render_ffmpeg_command(
                    **base,
                    music_path="music.mp3",
                    lower_thirds_path="lower.ass",
                    policy_overlays_path="policy.ass",
                ),
                "publish_lut": build_render_ffmpeg_command(**base, color_lut="grade.cube"),
            }
        golden = Path(__file__).with_name("golden").joinpath("render_argv.json")
        self.assertEqual(actual, json.loads(golden.read_text(encoding="utf-8")))


class FaceCropTests(unittest.TestCase):
    def test_portrait_subject_biases_toward_the_upper_focal_area(self):
        from assets.thumbnail_compose import compose_thumbnail

        base = Image.new("RGB", (640, 360), (0, 0, 0))
        subject = Image.new("RGB", (100, 300), (0, 0, 255))
        for y in range(100):
            for x in range(100):
                subject.putpixel((x, y), (255, 0, 0))

        with tempfile.TemporaryDirectory() as tmp:
            dest = str(Path(tmp, "thumb.jpg"))
            plate = compose_thumbnail(base, "A Real Headline", dest, subject=subject)
            self.assertEqual(plate.path, dest)
            result = Image.open(dest).convert("RGB")
            pixels = list(result.crop((420, 40, 640, 320)).get_flattened_data())

        red = sum(1 for r, g, b in pixels if r > 150 and b < 100)
        blue = sum(1 for r, g, b in pixels if b > 150 and r < 100)
        self.assertGreater(red, blue)


class ThumbnailTextExperimentTests(unittest.TestCase):
    def test_dual_generation_can_isolate_short_vs_full_thumbnail_copy(self):
        from assets.flux_thumbnail import generate_dual_thumbnails

        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(
                os.environ,
                {
                    "IDEOGRAM_API_KEY": "",
                    "RECRAFT_API_KEY": "",
                    "FLUX_API_KEY": "",
                },
                clear=False,
            ):
                rows = generate_dual_thumbnails(
                    "Los Angeles Chargers playoff outlook",
                    "Why The Los Angeles Chargers Can Still Recover",
                    tmp,
                    content_run_id=71,
                    channel_id="tapin",
                    text_variants=True,
                )
            self.assertEqual([row["arm"] for row in rows], ["text_short", "text_full"])
            self.assertEqual({row["features"]["layout"] for row in rows}, {"text_on"})
            copy = [row["features"]["headline_text"] for row in rows]
            self.assertNotEqual(copy[0], copy[1])
            self.assertTrue(all(row["path"] and os.path.isfile(row["path"]) for row in rows))


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required for the teaser behavior test")
class TeaserTests(unittest.TestCase):
    def test_five_second_teaser_leaves_the_finished_video_unchanged(self):
        from video.render_video import _probe_video_duration
        from video.teaser import create_teaser

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp, "finished.mp4")
            dest = Path(tmp, "finished_teaser.mp4")
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=red:s=108x192:d=6",
                    "-pix_fmt",
                    "yuv420p",
                    str(source),
                ],
                check=True,
                capture_output=True,
            )
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            made = create_teaser(str(source), str(dest))
            after = hashlib.sha256(source.read_bytes()).hexdigest()
            duration = _probe_video_duration(made)

        self.assertEqual(before, after)
        self.assertTrue(4.8 <= float(duration or 0) <= 5.2, duration)


if __name__ == "__main__":
    unittest.main()
