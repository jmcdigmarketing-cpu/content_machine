import unittest
from unittest.mock import MagicMock, patch

from video.render_video import MUSIC_BED_VOLUME, build_render_ffmpeg_command, render_vertical_video


class TestRenderFfmpegCommand(unittest.TestCase):
    def _vo_only(self, **kwargs):
        defaults = {
            "background_path": "C:/tmp/bg.mp4",
            "mp3_path": "C:/tmp/voice.mp3",
            "output_path": "C:/tmp/out.mp4",
            "subtitle_path": "C:/tmp/subs.srt",
            "duration": 90.5,
        }
        defaults.update(kwargs)
        return build_render_ffmpeg_command(**defaults)

    def test_mutes_stock_audio_via_filter_complex(self):
        cmd = self._vo_only()
        joined = " ".join(cmd)
        self.assertIn("-filter_complex", cmd)
        self.assertIn("[0:v]", joined)
        self.assertIn("[vout]", joined)
        self.assertIn("-map", cmd)
        vout_idx = cmd.index("[vout]")
        self.assertEqual(cmd[vout_idx - 1], "-map")
        self.assertIn("1:a:0", cmd)
        self.assertNotIn("0:a", joined)
        self.assertIn("-stream_loop", cmd)
        self.assertIn("90.500", cmd)

    def test_no_shortest_flag(self):
        cmd = build_render_ffmpeg_command(
            background_path="bg.mp4",
            mp3_path="a.mp3",
            output_path="out.mp4",
            subtitle_path="s.srt",
            duration=60.0,
        )
        self.assertNotIn("-shortest", cmd)

    def test_music_bed_mixed_under_vo(self):
        cmd = self._vo_only(music_path="C:/tmp/bed.mp3")
        joined = " ".join(cmd)
        self.assertIn(f"volume={MUSIC_BED_VOLUME}", joined)
        self.assertIn("amix=inputs=2:duration=first:normalize=0", joined)
        self.assertIn("[aout]", cmd)
        self.assertIn("C:/tmp/bed.mp3", cmd)

    def test_no_music_byte_identical_to_vo_only(self):
        a = self._vo_only()
        b = self._vo_only(music_path=None)
        self.assertEqual(a, b)

    def test_loudnorm_off_by_default(self):
        joined = " ".join(self._vo_only())
        self.assertNotIn("loudnorm", joined)

    def test_loudnorm_opt_in(self):
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {"LUFS_NORMALIZE": "true"}):
            joined = " ".join(self._vo_only())
        self.assertIn("loudnorm=I=-14", joined)
        self.assertIn("[aout]", joined)

    def test_t_bounds_output(self):
        cmd = self._vo_only(duration=12.25)
        self.assertEqual(cmd[cmd.index("-t") + 1], "12.250")

    def test_subtitles_burned_from_escaped_path(self):
        cmd = self._vo_only(subtitle_path="C:/tmp/subs.srt")
        joined = " ".join(cmd)
        self.assertIn("subtitles='C\\:/tmp/subs.srt'", joined)


class TestMusicBedFailureRetriesVoOnly(unittest.TestCase):
    def test_render_retries_vo_only_when_bed_mix_fails(self):
        asset = MagicMock(path="C:/tmp/bg.mp4", provider="local", attribution="")
        fail = MagicMock(returncode=1, stderr="amix failed")
        ok = MagicMock(returncode=0, stderr="")
        with (
            patch("video.render_video.get_background_asset", return_value=asset),
            patch("video.render_video.generate_subtitle_file", return_value="C:/tmp/s.srt"),
            patch("video.render_video._resolve_music_bed", return_value="C:/tmp/bed.mp3"),
            patch("video.render_video._probe_video_duration", return_value=60.0),
            patch("video.render_video._render_extra_formats", return_value=[]),
            patch("video.render_video.os.makedirs"),
            patch("video.render_video.is_render_progress_enabled", return_value=False),
            patch("assets.manager.get_scene_matched_background", return_value=None),
            patch("video.channel_intro.resolve_intro_path", return_value=None),
            patch("video.channel_intro.prepend_channel_intro"),
            patch("video.render_video.subprocess.run", side_effect=[fail, ok]) as run,
        ):
            render_vertical_video("C:/tmp/a.mp3", "topic", "out.mp4", "script words")
        self.assertEqual(run.call_count, 2)
        first = " ".join(run.call_args_list[0][0][0])
        second = " ".join(run.call_args_list[1][0][0])
        self.assertIn("amix", first)
        self.assertNotIn("amix", second)


class TestFfmpegFileLockRetry(unittest.TestCase):
    def test_retries_sharing_violation_then_succeeds(self):
        asset = MagicMock(path="C:/tmp/bg.mp4", provider="local", attribution="")
        locked = MagicMock(
            returncode=1,
            stderr="Permission denied: being used by another process",
        )
        ok = MagicMock(returncode=0, stderr="")
        with (
            patch("video.render_video.get_background_asset", return_value=asset),
            patch("video.render_video.generate_subtitle_file", return_value="C:/tmp/s.srt"),
            patch("video.render_video._resolve_music_bed", return_value=None),
            patch("video.render_video._probe_video_duration", return_value=60.0),
            patch("video.render_video._render_extra_formats", return_value=[]),
            patch("video.render_video.os.makedirs"),
            patch("video.render_video.is_render_progress_enabled", return_value=False),
            patch("assets.manager.get_scene_matched_background", return_value=None),
            patch("video.channel_intro.resolve_intro_path", return_value=None),
            patch("video.render_video.subprocess.run", side_effect=[locked, ok]) as run,
            patch.dict(
                "os.environ",
                {"FFMPEG_LOCK_RETRIES": "3", "FFMPEG_LOCK_DELAY_SEC": "0"},
                clear=False,
            ),
        ):
            from video.render_video import render_vertical_video

            render_vertical_video("C:/tmp/a.mp3", "topic", "out.mp4", "script words")
        self.assertEqual(run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
