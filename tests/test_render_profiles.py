"""Dual-format render (Pillar 6) — aspect profiles + the extra-format loop.

No real ffmpeg run: the command builder is asserted on its scale/crop dims, and the
extra-format loop is driven with a mocked subprocess. Default (RENDER_FORMATS unset) must
keep the primary vertical output byte-identical.
"""

from __future__ import annotations

import unittest
from unittest import mock

from video import render_profiles as rp
from video.render_video import build_render_ffmpeg_command


class TestProfilesFor(unittest.TestCase):
    def test_empty_is_vertical_only(self):
        self.assertEqual([p.name for p in rp.profiles_for("")], ["vertical"])
        self.assertEqual([p.name for p in rp.profiles_for(None or "")], ["vertical"])

    def test_all_three(self):
        names = [p.name for p in rp.profiles_for("vertical,landscape,square")]
        self.assertEqual(names, ["vertical", "landscape", "square"])

    def test_vertical_always_first_even_if_omitted(self):
        # Asking only for landscape still renders the primary vertical first.
        self.assertEqual([p.name for p in rp.profiles_for("landscape")], ["vertical", "landscape"])

    def test_unknown_ignored_and_deduped(self):
        self.assertEqual(
            [p.name for p in rp.profiles_for("square,bogus,square")],
            ["vertical", "square"],
        )

    def test_extra_profiles_excludes_vertical(self):
        self.assertEqual([p.name for p in rp.extra_profiles("vertical,landscape")], ["landscape"])
        self.assertEqual(rp.extra_profiles(""), [])


class TestCommandDims(unittest.TestCase):
    def _dims(self, cmd: list[str]) -> str:
        i = cmd.index("-filter_complex")
        return cmd[i + 1]

    def test_default_is_vertical_1080x1920(self):
        cmd = build_render_ffmpeg_command(
            background_path="bg.mp4",
            mp3_path="a.mp3",
            output_path="o.mp4",
            subtitle_path="s.srt",
            duration=10.0,
        )
        fc = self._dims(cmd)
        self.assertIn("scale=1080:1920", fc)
        self.assertIn("crop=1080:1920", fc)

    def test_landscape_profile_is_1920x1080(self):
        cmd = build_render_ffmpeg_command(
            background_path="bg.mp4",
            mp3_path="a.mp3",
            output_path="o.mp4",
            subtitle_path="s.srt",
            duration=10.0,
            profile=rp._PROFILES["landscape"],
        )
        fc = self._dims(cmd)
        self.assertIn("scale=1920:1080", fc)
        self.assertIn("crop=1920:1080", fc)

    def test_square_profile_is_1080x1080(self):
        cmd = build_render_ffmpeg_command(
            background_path="bg.mp4",
            mp3_path="a.mp3",
            output_path="o.mp4",
            subtitle_path="s.srt",
            duration=10.0,
            profile=rp._PROFILES["square"],
        )
        self.assertIn("scale=1080:1080", self._dims(cmd))


class TestExtraFormatLoop(unittest.TestCase):
    def test_no_extras_by_default(self):
        from video.render_video import _render_extra_formats

        with mock.patch("subprocess.run") as run:
            out = _render_extra_formats(
                background_path="bg.mp4",
                mp3_path="a.mp3",
                primary_output="o.mp4",
                subtitle_path="s.srt",
                duration=10.0,
                stage=lambda *_: None,
            )
        self.assertEqual(out, [])
        run.assert_not_called()  # RENDER_FORMATS unset → no extra ffmpeg calls

    def test_renders_suffixed_siblings(self):
        from video.render_video import _render_extra_formats

        with (
            mock.patch(
                "video.render_profiles.extra_profiles",
                return_value=[
                    rp._PROFILES["landscape"],
                    rp._PROFILES["square"],
                ],
            ),
            mock.patch("subprocess.run", return_value=mock.MagicMock(returncode=0, stderr="")),
            mock.patch("os.path.isfile", return_value=True),
        ):
            out = _render_extra_formats(
                background_path="bg.mp4",
                mp3_path="a.mp3",
                primary_output="C:/out/vid.mp4",
                subtitle_path="s.srt",
                duration=10.0,
                stage=lambda *_: None,
            )
        self.assertEqual(out, ["C:/out/vid_16x9.mp4", "C:/out/vid_1x1.mp4"])

    def test_extra_failure_is_fail_open(self):
        from video.render_video import _render_extra_formats

        with (
            mock.patch(
                "video.render_profiles.extra_profiles", return_value=[rp._PROFILES["square"]]
            ),
            mock.patch("subprocess.run", side_effect=RuntimeError("ffmpeg missing")),
        ):
            out = _render_extra_formats(
                background_path="bg.mp4",
                mp3_path="a.mp3",
                primary_output="o.mp4",
                subtitle_path="s.srt",
                duration=10.0,
                stage=lambda *_: None,
            )
        self.assertEqual(out, [])  # skipped, never raised


if __name__ == "__main__":
    unittest.main()
