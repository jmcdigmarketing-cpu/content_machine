"""#999 a failed intro prepend is not recorded as an intro.

The first caption stays where the subtitle file put it. It is not shifted by
the intro's length.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class TestFailedIntro(unittest.TestCase):
    def test_a_raised_prepend_does_not_count_as_landed(self):
        from video.render_video import render_vertical_video

        asset = MagicMock(path="C:/tmp/bg.mp4", provider="local", attribution="")
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
            patch("video.channel_intro.resolve_intro_path", return_value="C:/tmp/intro.mp4"),
            patch(
                "video.channel_intro.prepend_channel_intro",
                side_effect=RuntimeError("prepend failed"),
            ),
            patch("video.channel_outro.resolve_end_card", return_value=None),
            patch("video.render_video.subprocess.run", return_value=ok),
        ):
            _path, _asset, landed = render_vertical_video(
                "C:/tmp/a.mp3", "topic", "out.mp4", "script words", render_preset="publish"
            )
        self.assertFalse(landed)

    def test_the_first_caption_is_not_shifted_when_the_prepend_failed(self):
        from video.channel_intro import opening_after_render

        opening = opening_after_render("tapin", False, 0.2)
        self.assertFalse(opening["intro"])
        self.assertEqual(opening["first_caption_s"], 0.2)

    def test_the_pipeline_does_not_count_a_failed_prepend(self):
        from core import pipeline

        captured: dict = {}
        seen_offset: dict = {}

        def _keep(_run_id, patch):
            if isinstance(patch, dict) and "opening" in patch:
                captured.update(patch["opening"])

        def _frame(_path, intro_offset=0.0):
            seen_offset["intro_offset"] = intro_offset
            return None

        with (
            patch.dict(
                "os.environ",
                {"THUMBNAIL_MODE": "off", "CONTENT_RENDER_PROGRESS": "0"},
                clear=False,
            ),
            patch.object(
                pipeline, "media_paths_for_topic", return_value=("a.mp3", "v.mp4", "out/v.mp4")
            ),
            patch.object(pipeline, "generate_audio"),
            patch.object(pipeline, "update_content_run_media"),
            patch.object(pipeline, "record_render_assets"),
            patch("core.run_features.load_features", return_value={}),
            patch("core.run_features.merge_features"),
            patch("core.run_trace.update_trace"),
            patch("video.channel_intro.intro_for_run", return_value=True),
            patch.object(
                pipeline,
                "render_vertical_video",
                return_value=("out/v.mp4", None, False),
            ),
            patch("video.caption_timing.first_cue_seconds", return_value=0.2),
            patch("video.caption_timing.subtitle_beside", return_value="out/v.srt"),
            patch("core.run_quality.merge_quality", side_effect=_keep),
            patch("scripts.probe_sync.intro_offset_seconds", return_value=2.15),
            patch("core.first_frame.inspect_video", side_effect=_frame),
            patch("scripts.probe_sync.grab_frame", return_value=False),
        ):
            pipeline.run_media_only("topic", "x" * 40, channel_id="tapin", content_run_id=64)
        self.assertFalse(captured["intro"])
        self.assertEqual(captured["first_caption_s"], 0.2)
        self.assertEqual(seen_offset["intro_offset"], 0.0)


if __name__ == "__main__":
    unittest.main()
