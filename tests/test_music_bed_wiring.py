"""Music bed wiring (Pillar 6) — ffmpeg mix command + render fail-open.

No real ffmpeg / audiocraft: the command builder is asserted directly, and the render
path is driven with the bed generator, moviepy, assets, subtitles, and subprocess all
mocked. Locks two invariants: (1) `music_path=None` emits a command byte-identical to
today's VO-only command, and (2) a bed miss or a broken mix can never break a render.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

from core.providers import ProviderResult
from video.render_video import (
    MUSIC_BED_VOLUME,
    _resolve_music_bed,
    build_render_ffmpeg_command,
)


def _build(**overrides):
    kwargs = {
        "background_path": "C:/tmp/bg.mp4",
        "mp3_path": "C:/tmp/voice.mp3",
        "output_path": "C:/tmp/out.mp4",
        "subtitle_path": "C:/tmp/subs.srt",
        "duration": 90.5,
    }
    kwargs.update(overrides)
    return build_render_ffmpeg_command(**kwargs)


class TestCommandWithoutMusic(unittest.TestCase):
    def test_none_music_is_byte_identical_to_legacy_command(self):
        expected = [
            "ffmpeg",
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            "C:/tmp/bg.mp4",
            "-i",
            "C:/tmp/voice.mp3",
            "-t",
            "90.500",
            "-filter_complex",
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,setpts=PTS-STARTPTS,"
            "subtitles='C\\:/tmp/subs.srt'[vout]",
            "-map",
            "[vout]",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "C:/tmp/out.mp4",
        ]
        self.assertEqual(_build(), expected)
        self.assertEqual(_build(music_path=None), expected)


class TestCommandWithMusic(unittest.TestCase):
    def test_music_adds_looped_input_and_ducked_amix(self):
        cmd = _build(music_path="C:/tmp/bed.wav")
        self.assertIn("C:/tmp/bed.wav", cmd)
        # Both the background and the bed loop (VO does not).
        self.assertEqual(cmd.count("-stream_loop"), 2)
        fc = cmd[cmd.index("-filter_complex") + 1]
        # Bed ducked; VO left at unit gain by normalize=0 — voice stays dominant.
        self.assertIn(f"[2:a]volume={MUSIC_BED_VOLUME}[bed]", fc)
        self.assertIn("[1:a][bed]amix=inputs=2:duration=first:normalize=0[aout]", fc)
        # Mixed audio mapped instead of the raw VO stream; video graph unchanged.
        self.assertIn("[aout]", cmd)
        self.assertNotIn("1:a:0", cmd)
        self.assertIn("[vout]", cmd)

    def test_music_is_input_index_two(self):
        cmd = _build(music_path="C:/tmp/bed.wav")
        inputs = [cmd[i + 1] for i, tok in enumerate(cmd) if tok == "-i"]
        self.assertEqual(inputs, ["C:/tmp/bg.mp4", "C:/tmp/voice.mp3", "C:/tmp/bed.wav"])


class TestResolveMusicBed(unittest.TestCase):
    def test_gate_unset_returns_none_without_calling_backend(self):
        with (
            mock.patch.dict(os.environ, {}, clear=False),
            mock.patch("core.music.generate_bed") as gen,
        ):
            os.environ.pop("MUSIC_PROVIDER", None)
            self.assertIsNone(_resolve_music_bed(10.0, lambda *_: None))
        gen.assert_not_called()

    def test_not_ok_result_fails_open_to_none(self):
        with (
            mock.patch.dict(os.environ, {"MUSIC_PROVIDER": "musicgen"}, clear=False),
            mock.patch(
                "core.music.generate_bed",
                return_value=ProviderResult.fail_open("music", "audiocraft not installed"),
            ) as gen,
        ):
            os.environ.pop("MUSIC_MOOD", None)
            self.assertIsNone(_resolve_music_bed(12.0, lambda *_: None))
        gen.assert_called_once_with("upbeat", 12.0)

    def test_mood_env_override(self):
        with (
            mock.patch.dict(
                os.environ, {"MUSIC_PROVIDER": "musicgen", "MUSIC_MOOD": "calm"}, clear=False
            ),
            mock.patch(
                "core.music.generate_bed",
                return_value=ProviderResult.fail_open("music", "x"),
            ) as gen,
        ):
            _resolve_music_bed(5.0, lambda *_: None)
        gen.assert_called_once_with("calm", 5.0)

    def test_ok_result_returns_normalized_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            bed = os.path.join(tmp, "bed.wav")
            with open(bed, "wb") as f:
                f.write(b"\x00")
            with (
                mock.patch.dict(os.environ, {"MUSIC_PROVIDER": "musicgen"}, clear=False),
                mock.patch(
                    "core.music.generate_bed",
                    return_value=ProviderResult.success("music", "musicgen", data=bed),
                ),
            ):
                out = _resolve_music_bed(12.0, lambda *_: None)
            self.assertEqual(out, os.path.abspath(bed).replace("\\", "/"))

    def test_ok_result_with_missing_file_fails_open(self):
        with (
            mock.patch.dict(os.environ, {"MUSIC_PROVIDER": "musicgen"}, clear=False),
            mock.patch(
                "core.music.generate_bed",
                return_value=ProviderResult.success("music", "musicgen", data="C:/nope/bed.wav"),
            ),
        ):
            self.assertIsNone(_resolve_music_bed(12.0, lambda *_: None))

    def test_backend_exception_fails_open(self):
        with (
            mock.patch.dict(os.environ, {"MUSIC_PROVIDER": "musicgen"}, clear=False),
            mock.patch("core.music.generate_bed", side_effect=RuntimeError("torch OOM")),
        ):
            self.assertIsNone(_resolve_music_bed(12.0, lambda *_: None))


class _RenderHarness(unittest.TestCase):
    """Drive render_vertical_video with every heavy dependency mocked (no ffmpeg run)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        audio_dir = os.path.join(self.tmp.name, "audio")
        os.makedirs(audio_dir)
        self.mp3_path = os.path.join(audio_dir, "voice.mp3")
        with open(self.mp3_path, "wb") as f:
            f.write(b"\x00")
        self.duration = 12.5

        env = mock.patch.dict(os.environ, {"MUSIC_PROVIDER": "musicgen"}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("MUSIC_MOOD", None)
        os.environ.pop("RENDER_FORMATS", None)  # no extra-format renders

        def _patch(target, **kw):
            p = mock.patch(target, **kw)
            m = p.start()
            self.addCleanup(p.stop)
            return m

        clip = mock.MagicMock()
        clip.duration = self.duration
        _patch("video.render_video.AudioFileClip", return_value=clip)
        asset = mock.MagicMock()
        asset.path = os.path.join(self.tmp.name, "bg.mp4")
        asset.provider = "local"
        asset.attribution = None
        _patch("video.render_video.get_background_asset", return_value=asset)
        _patch("assets.manager.get_scene_matched_background", return_value=None)
        _patch("video.render_video._probe_video_duration", return_value=None)
        _patch(
            "video.render_video.generate_subtitle_file",
            return_value=os.path.join(self.tmp.name, "subs.srt"),
        )
        _patch("video.render_video.is_render_progress_enabled", return_value=False)
        _patch("video.channel_intro.resolve_intro_path", return_value=None)
        self.run_mock = _patch(
            "video.render_video.subprocess.run",
            return_value=mock.MagicMock(returncode=0, stderr=""),
        )

    def _render(self, *, command_callback=None):
        from video.render_video import render_vertical_video

        return render_vertical_video(
            self.mp3_path,
            "topic",
            "out.mp4",
            "script text",
            command_callback=command_callback,
        )

    def _write_bed(self) -> str:
        bed = os.path.join(self.tmp.name, "bed.wav")
        with open(bed, "wb") as f:
            f.write(b"\x00")
        return bed


class TestRenderWithBed(_RenderHarness):
    def test_bed_mixed_under_vo(self):
        bed = self._write_bed()
        with mock.patch(
            "core.music.generate_bed",
            return_value=ProviderResult.success("music", "musicgen", data=bed),
        ) as gen:
            output_path, _asset = self._render()
        gen.assert_called_once_with("upbeat", self.duration)
        self.assertEqual(self.run_mock.call_count, 1)
        cmd = self.run_mock.call_args[0][0]
        self.assertIn(os.path.abspath(bed).replace("\\", "/"), cmd)
        self.assertIn("amix=inputs=2", " ".join(cmd))
        self.assertIn("[aout]", cmd)
        self.assertNotIn("1:a:0", cmd)
        self.assertTrue(output_path.endswith("out.mp4"))


class TestRenderFailsOpenToVoOnly(_RenderHarness):
    def test_not_ok_bed_renders_vo_only(self):
        with mock.patch(
            "core.music.generate_bed",
            return_value=ProviderResult.fail_open("music", "audiocraft not installed"),
        ) as gen:
            self._render()  # must not raise
        gen.assert_called_once()
        self.assertEqual(self.run_mock.call_count, 1)
        cmd = self.run_mock.call_args[0][0]
        self.assertNotIn("amix", " ".join(cmd))
        self.assertIn("1:a:0", cmd)
        self.assertEqual(cmd.count("-stream_loop"), 1)

    def test_failed_mix_retries_vo_only(self):
        bed = self._write_bed()
        self.run_mock.side_effect = [
            mock.MagicMock(returncode=1, stderr="Unrecognized option 'normalize'"),
            mock.MagicMock(returncode=0, stderr=""),
        ]
        with mock.patch(
            "core.music.generate_bed",
            return_value=ProviderResult.success("music", "musicgen", data=bed),
        ):
            self._render()  # must not raise
        self.assertEqual(self.run_mock.call_count, 2)
        first = self.run_mock.call_args_list[0][0][0]
        second = self.run_mock.call_args_list[1][0][0]
        self.assertIn("amix=inputs=2", " ".join(first))
        self.assertNotIn("amix", " ".join(second))
        self.assertIn("1:a:0", second)

    def test_command_callback_reports_the_command_that_succeeds(self):
        bed = self._write_bed()
        self.run_mock.side_effect = [
            mock.MagicMock(returncode=1, stderr="mix failed"),
            mock.MagicMock(returncode=0, stderr=""),
        ]
        seen = []
        with mock.patch(
            "core.music.generate_bed",
            return_value=ProviderResult.success("music", "musicgen", data=bed),
        ):
            self._render(command_callback=lambda kind, argv: seen.append((kind, argv)))
        self.assertEqual([kind for kind, _ in seen], ["primary", "primary"])
        self.assertIn("amix", " ".join(seen[0][1]))
        self.assertNotIn("amix", " ".join(seen[-1][1]))


if __name__ == "__main__":
    unittest.main()
