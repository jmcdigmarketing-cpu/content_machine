"""Dependency wave: Pillow 11.3, requests 2.32.4, moviepy gone from render_video."""

from __future__ import annotations

import inspect
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent


class TestDependencyPins(unittest.TestCase):
    def test_requirements_pins(self):
        text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("Pillow==11.3.0", text)
        self.assertIn("requests==2.32.4", text)
        self.assertNotIn("moviepy", text)

    def test_pyproject_pins(self):
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("Pillow==11.3.0", text)
        self.assertIn("requests==2.32.4", text)
        self.assertNotIn("moviepy", text)


class TestRenderVideoDropsMoviepy(unittest.TestCase):
    def test_render_video_source_has_no_moviepy(self):
        import video.render_video as rv

        source = inspect.getsource(rv)
        self.assertNotIn("moviepy", source)
        self.assertNotIn("AudioFileClip", source)

    def test_audio_duration_comes_from_probe_helper(self):
        from video.render_video import render_vertical_video

        asset = MagicMock(path="C:/tmp/bg.mp4", provider="local", attribution="")
        ok = MagicMock(returncode=0, stderr="")

        def probe(path):
            lowered = str(path).replace("\\", "/").lower()
            if lowered.endswith(".mp3") or "voice" in lowered:
                return 12.5
            return 60.0

        with (
            patch("video.render_video.get_background_asset", return_value=asset),
            patch("video.render_video.generate_subtitle_file", return_value="C:/tmp/s.srt"),
            patch("video.render_video._resolve_music_bed", return_value=None),
            patch("video.render_video._probe_video_duration", side_effect=probe) as probed,
            patch("video.render_video._render_extra_formats", return_value=[]),
            patch("video.render_video.os.makedirs"),
            patch("video.render_video.is_render_progress_enabled", return_value=False),
            patch("assets.manager.get_scene_matched_background", return_value=None),
            patch("video.channel_intro.resolve_intro_path", return_value=None),
            patch("video.render_video.subprocess.run", return_value=ok) as run,
        ):
            render_vertical_video("C:/tmp/voice.mp3", "topic", "out.mp4", "script words")
        self.assertTrue(probed.called)
        argv = run.call_args_list[0][0][0]
        self.assertEqual(argv[argv.index("-t") + 1], "12.500")


if __name__ == "__main__":
    unittest.main()
