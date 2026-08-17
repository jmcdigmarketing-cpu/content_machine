"""The intro step mutates the finished render in place — it must never lose it.

`prepend_channel_intro` moves the rendered mp4 aside (`os.replace` to a `.body.tmp.mp4`)
and asks ffmpeg to write the concatenated result back to the original path. Everything
between those two points is a window where the only copy of a just-rendered video lives
under a temp name, so every exit from that window has to put it back.

`render_vertical_video` catches failures here and logs "Channel intro skipped (render
kept)" — these tests are what make that sentence true.

No ffmpeg: subprocess is mocked throughout (tests/CLAUDE.md).
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from video import channel_intro


def _fake_completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=["ffmpeg"], returncode=returncode, stdout=stdout, stderr=stderr
    )


class _IntroCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.body = os.path.join(self.tmp, "video.mp4")
        self.intro = os.path.join(self.tmp, "intro.mp4")
        with open(self.body, "w", encoding="utf-8") as f:
            f.write("RENDERED-BODY")
        with open(self.intro, "w", encoding="utf-8") as f:
            f.write("INTRO")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _body_text(self):
        with open(self.body, encoding="utf-8") as f:
            return f.read()

    def _strays(self):
        return [n for n in os.listdir(self.tmp) if ".tmp" in n]


class TestRenderSurvivesEveryFailure(_IntroCase):
    def test_body_survives_when_ffmpeg_is_missing(self):
        """The bug: subprocess.run raising skipped the restore entirely.

        ffmpeg not on PATH raises FileNotFoundError before any exit code exists, so the
        `returncode != 0` restore never ran and the render stayed parked at
        `<path>.body.tmp.mp4` — while the caller reported "render kept".
        """
        with (
            patch.object(channel_intro, "resolve_intro_path", return_value=self.intro),
            patch.object(channel_intro.subprocess, "run", side_effect=FileNotFoundError("ffmpeg")),
            self.assertRaises(FileNotFoundError),
        ):
            channel_intro.prepend_channel_intro(self.body)

        self.assertTrue(os.path.isfile(self.body), "rendered video vanished from its path")
        self.assertEqual(self._body_text(), "RENDERED-BODY")
        self.assertEqual(self._strays(), [], "left a stray temp copy behind")

    def test_body_survives_a_nonzero_exit(self):
        with (
            patch.object(channel_intro, "resolve_intro_path", return_value=self.intro),
            patch.object(
                channel_intro.subprocess, "run", return_value=_fake_completed(1, stderr="boom")
            ),
            self.assertRaises(RuntimeError),
        ):
            channel_intro.prepend_channel_intro(self.body)

        self.assertTrue(os.path.isfile(self.body))
        self.assertEqual(self._body_text(), "RENDERED-BODY")
        self.assertEqual(self._strays(), [])

    def test_body_survives_an_empty_output(self):
        """ffmpeg can exit 0 and still leave nothing usable; deleting the temp then
        destroys the only real copy."""

        def _exit_zero_but_write_nothing(cmd, **kwargs):
            open(self.body, "w").close()  # 0 bytes at the output path
            return _fake_completed(0)

        with (
            patch.object(channel_intro, "resolve_intro_path", return_value=self.intro),
            patch.object(channel_intro.subprocess, "run", side_effect=_exit_zero_but_write_nothing),
            self.assertRaises(RuntimeError),
        ):
            channel_intro.prepend_channel_intro(self.body)

        self.assertEqual(self._body_text(), "RENDERED-BODY", "restored the real render")
        self.assertEqual(self._strays(), [])


class TestSuccessPath(_IntroCase):
    def test_output_replaces_body_and_temp_is_removed(self):
        def _write_output(cmd, **kwargs):
            with open(cmd[-1], "w", encoding="utf-8") as f:
                f.write("INTRO+BODY-CONCATENATED")
            return _fake_completed(0)

        with (
            patch.object(channel_intro, "resolve_intro_path", return_value=self.intro),
            patch.object(channel_intro.subprocess, "run", side_effect=_write_output),
        ):
            out = channel_intro.prepend_channel_intro(self.body)

        self.assertEqual(out, os.path.abspath(self.body))
        self.assertEqual(self._body_text(), "INTRO+BODY-CONCATENATED")
        self.assertEqual(self._strays(), [])

    def test_no_intro_configured_is_a_no_op(self):
        with (
            patch.object(channel_intro, "resolve_intro_path", return_value=None),
            patch.object(channel_intro.subprocess, "run") as run,
        ):
            out = channel_intro.prepend_channel_intro(self.body)
        run.assert_not_called()
        self.assertEqual(out, self.body)
        self.assertEqual(self._body_text(), "RENDERED-BODY")

    def test_explicit_output_path_leaves_the_body_alone(self):
        dest = os.path.join(self.tmp, "with_intro.mp4")

        def _write_output(cmd, **kwargs):
            with open(cmd[-1], "w", encoding="utf-8") as f:
                f.write("COMBINED")
            return _fake_completed(0)

        with (
            patch.object(channel_intro, "resolve_intro_path", return_value=self.intro),
            patch.object(channel_intro.subprocess, "run", side_effect=_write_output),
        ):
            out = channel_intro.prepend_channel_intro(self.body, output_path=dest)

        self.assertEqual(out, os.path.abspath(dest))
        self.assertEqual(self._body_text(), "RENDERED-BODY", "body must not be consumed")
        self.assertEqual(self._strays(), [])

    def test_missing_body_raises_before_touching_anything(self):
        with patch.object(channel_intro, "resolve_intro_path", return_value=self.intro):
            with self.assertRaises(FileNotFoundError):
                channel_intro.prepend_channel_intro(os.path.join(self.tmp, "nope.mp4"))


class TestConcatCommand(unittest.TestCase):
    """A silent intro must still contribute an audio track, or concat drops audio and
    the voiceover slides earlier by the intro's length."""

    def _cmd(self, *, has_audio, duration=2.15):
        return channel_intro.build_intro_concat_command(
            intro_path="intro.mp4",
            body_path="body.mp4",
            output_path="out.mp4",
            intro_has_audio=has_audio,
            intro_duration=duration,
        )

    def test_silent_intro_gets_synthesized_audio_of_the_right_length(self):
        graph = self._cmd(has_audio=False)[self._cmd(has_audio=False).index("-filter_complex") + 1]
        self.assertIn("anullsrc", graph)
        self.assertIn("atrim=duration=2.150", graph)

    def test_intro_with_audio_uses_its_own_track(self):
        graph = self._cmd(has_audio=True)[self._cmd(has_audio=True).index("-filter_complex") + 1]
        self.assertNotIn("anullsrc", graph)
        self.assertIn("[0:a]aformat", graph)

    def test_both_streams_are_concatenated_with_audio(self):
        graph = self._cmd(has_audio=True)[self._cmd(has_audio=True).index("-filter_complex") + 1]
        self.assertIn("concat=n=2:v=1:a=1[vout][aout]", graph)

    def test_both_inputs_are_scaled_to_vertical(self):
        graph = self._cmd(has_audio=True)[self._cmd(has_audio=True).index("-filter_complex") + 1]
        self.assertEqual(graph.count(f"scale={channel_intro.TARGET_W}:{channel_intro.TARGET_H}"), 2)
        self.assertEqual(graph.count("setpts=PTS-STARTPTS"), 2)

    def test_intro_comes_first(self):
        cmd = self._cmd(has_audio=True)
        self.assertLess(cmd.index("intro.mp4"), cmd.index("body.mp4"))


class TestIntroResolution(_IntroCase):
    def test_profile_intro_wins_over_env(self):
        # tapin configures its own intro, so the env var must not override it.
        with patch.dict("os.environ", {"CHANNEL_INTRO_PATH": self.intro}, clear=False):
            resolved = channel_intro.resolve_intro_path("tapin")
        self.assertIsNotNone(resolved)
        self.assertNotEqual(resolved, os.path.abspath(self.intro))

    def test_env_path_is_used_when_the_profile_has_none(self):
        profile = channel_intro.get_channel_profile("tapin")
        with (
            patch.object(profile, "intro_video_file", ""),
            patch.object(channel_intro, "get_channel_profile", return_value=profile),
            patch.dict("os.environ", {"CHANNEL_INTRO_PATH": self.intro}, clear=False),
        ):
            self.assertEqual(channel_intro.resolve_intro_path("tapin"), os.path.abspath(self.intro))

    def test_disabled_returns_none(self):
        with patch.dict("os.environ", {"CHANNEL_INTRO_ENABLED": "false"}, clear=False):
            self.assertIsNone(channel_intro.resolve_intro_path("tapin"))


if __name__ == "__main__":
    unittest.main()
