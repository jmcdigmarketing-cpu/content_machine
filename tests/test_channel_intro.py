import os
import unittest
from unittest.mock import patch

from config.paths import ROOT_DIR
from video.channel_intro import (
    build_intro_concat_command,
    resolve_intro_path,
)


class TestChannelIntro(unittest.TestCase):
    def test_resolve_default_intro_when_enabled(self):
        default = os.path.join(ROOT_DIR, "video", "intro", "channel_intro.mp4")
        if not os.path.isfile(default):
            self.skipTest("channel_intro.mp4 not present")

        with patch.dict(os.environ, {"CHANNEL_INTRO_ENABLED": "true"}, clear=False):
            path = resolve_intro_path("tapin")
        self.assertEqual(path, os.path.abspath(default))

    def test_resolve_none_when_disabled(self):
        with patch.dict(os.environ, {"CHANNEL_INTRO_ENABLED": "false"}, clear=False):
            self.assertIsNone(resolve_intro_path("tapin"))

    def test_concat_command_includes_intro_and_body(self):
        cmd = build_intro_concat_command(
            intro_path="C:/intro.mp4",
            body_path="C:/body.mp4",
            output_path="C:/out.mp4",
            intro_has_audio=True,
            intro_duration=2.5,
        )
        joined = " ".join(cmd)
        self.assertIn("concat=n=2", joined)
        self.assertIn("C:/intro.mp4", cmd)
        self.assertIn("C:/body.mp4", cmd)

    def test_concat_command_silent_intro_when_no_audio(self):
        cmd = build_intro_concat_command(
            intro_path="intro.mp4",
            body_path="body.mp4",
            output_path="out.mp4",
            intro_has_audio=False,
            intro_duration=3.0,
        )
        joined = " ".join(cmd)
        self.assertIn("anullsrc", joined)


if __name__ == "__main__":
    unittest.main()
