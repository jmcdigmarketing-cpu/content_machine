"""Dependency wave: Pillow >= 12.3, requests 2.32.4, moviepy gone from render_video.

Pillow's floor is 12.3.0, not 11.x. Measured with pip-audit: 11.3.0 still carried 25
advisories - font, PDF, JPEG2000 and TGA parsers, which is exactly the untrusted-bytes
surface the thumbnail path feeds - and every one of them is fixed only in 12.x.
Asserted as a floor rather than an exact pin so a future bump up passes and a
downgrade fails."""

from __future__ import annotations

import inspect
import os
import re
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent


class TestDependencyPins(unittest.TestCase):
    PILLOW_FLOOR = (12, 3, 0)

    def _pillow_pin(self, text: str) -> tuple[int, ...]:
        match = re.search(r"Pillow==(\d+)\.(\d+)\.(\d+)", text)
        self.assertIsNotNone(match, "Pillow must stay pinned to an exact version")
        return tuple(int(g) for g in match.groups())

    def test_requirements_pins(self):
        text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertGreaterEqual(self._pillow_pin(text), self.PILLOW_FLOOR)
        self.assertIn("requests==2.32.4", text)
        self.assertNotIn("moviepy", text)

    def test_pyproject_pins(self):
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertGreaterEqual(self._pillow_pin(text), self.PILLOW_FLOOR)
        self.assertIn("requests==2.32.4", text)
        self.assertNotIn("moviepy", text)

    def test_installed_pillow_matches_the_declared_pin(self):
        """A manifest edit is not an applied upgrade (rules 8).

        pyproject read 11.3.0 for a full wave while the environment ran 9.5.0, so the
        CVEs stayed live and CI diverged from the operator's machine on a major version.
        Assert the RUNTIME, not the file.
        """
        import PIL

        declared = self._pillow_pin((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        installed = tuple(int(p) for p in PIL.__version__.split(".")[:3])
        self.assertEqual(
            installed,
            declared,
            f"pyproject pins Pillow {declared} but the environment runs {installed} - "
            "run `pip install -e .`",
        )


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
