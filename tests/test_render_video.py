import unittest

from video.render_video import build_render_ffmpeg_command


class TestRenderFfmpegCommand(unittest.TestCase):
    def test_mutes_stock_audio_via_filter_complex(self):
        cmd = build_render_ffmpeg_command(
            background_path="C:/tmp/bg.mp4",
            mp3_path="C:/tmp/voice.mp3",
            output_path="C:/tmp/out.mp4",
            subtitle_path="C:/tmp/subs.srt",
            duration=90.5,
        )
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


if __name__ == "__main__":
    unittest.main()
