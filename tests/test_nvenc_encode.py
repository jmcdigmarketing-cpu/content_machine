"""#38 NVENC encode with libx264 fallback.

Patch ffmpeg_has_nvenc, never video_encoder_args. NVENC=off (suite default)
must keep the CPU argv byte-identical to today's libx264 block.
"""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from assets.composite import build_hybrid_concat_command
from video.channel_intro import build_intro_concat_command
from video.channel_outro import build_outro_concat_command
from video.encoder import (
    executed_cmd,
    fallback_libx264_cmd,
    run_ffmpeg_with_nvenc_fallback,
    video_encoder_args,
)
from video.render_video import build_render_ffmpeg_command


def _cpu_block(*, preset: str = "fast", crf: str = "23") -> list[str]:
    return ["-c:v", "libx264", "-preset", preset, "-crf", crf]


class TestNvencEncoderArgs(unittest.TestCase):
    def test_off_or_probe_false_is_libx264_byte_identical(self):
        with patch.dict(os.environ, {"NVENC": "off"}):
            self.assertEqual(video_encoder_args(), _cpu_block())
        with patch.dict(os.environ, {"NVENC": ""}):
            with patch("core.cuda_probe.ffmpeg_has_nvenc", return_value=False):
                self.assertEqual(
                    video_encoder_args(preset="veryfast", crf="28"),
                    _cpu_block(preset="veryfast", crf="28"),
                )

    def test_probe_true_emits_h264_nvenc_not_libx264_preset(self):
        with patch.dict(os.environ, {"NVENC": "1"}, clear=False):
            with patch("core.cuda_probe.ffmpeg_has_nvenc", return_value=True):
                args = video_encoder_args(preset="fast", crf="23")
        self.assertIn("h264_nvenc", args)
        self.assertNotIn("libx264", args)
        self.assertNotIn("-crf", args)

    def test_render_command_uses_helper(self):
        kwargs = {
            "background_path": "bg.mp4",
            "mp3_path": "vo.mp3",
            "output_path": "out.mp4",
            "subtitle_path": "s.srt",
            "duration": 6.0,
        }
        with patch.dict(os.environ, {"NVENC": "off"}):
            cpu = build_render_ffmpeg_command(**kwargs)
        self.assertIn("libx264", cpu)
        with patch.dict(os.environ, {"NVENC": "1"}):
            with patch("core.cuda_probe.ffmpeg_has_nvenc", return_value=True):
                gpu = build_render_ffmpeg_command(**kwargs)
        self.assertIn("h264_nvenc", gpu)
        self.assertNotIn("libx264", gpu)

    def test_intro_and_outro_use_helper(self):
        with patch.dict(os.environ, {"NVENC": "1"}):
            with patch("core.cuda_probe.ffmpeg_has_nvenc", return_value=True):
                intro = build_intro_concat_command(
                    intro_path="i.mp4",
                    body_path="b.mp4",
                    output_path="o.mp4",
                    intro_has_audio=True,
                    intro_duration=1.0,
                )
                outro = build_outro_concat_command(
                    body_path="b.mp4",
                    output_path="o.mp4",
                    card={"bg": "#000000", "fg": "#FFFFFF", "duration": 1.5, "text": "Tap In"},
                )
                hybrid = build_hybrid_concat_command(
                    local_path="l.mp4",
                    stock_path="s.mp4",
                    output_path="o.mp4",
                    duration=6.0,
                )
        self.assertIn("h264_nvenc", intro)
        self.assertIn("h264_nvenc", outro)
        self.assertIn("h264_nvenc", hybrid)

    def test_encode_fail_retries_libx264(self):
        nvenc_cmd = ["ffmpeg", "-c:v", "h264_nvenc", "-preset", "p4", "out.mp4"]
        calls: list[list[str]] = []

        def runner(cmd):
            calls.append(list(cmd))
            ok = "libx264" in cmd
            return SimpleNamespace(returncode=0 if ok else 1, stderr="nvenc fail")

        with patch.dict(os.environ, {"NVENC": "off"}):
            proc = run_ffmpeg_with_nvenc_fallback(nvenc_cmd, runner=runner)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(len(calls), 2)
        self.assertIn("h264_nvenc", calls[0])
        self.assertIn("libx264", calls[1])
        self.assertNotIn("h264_nvenc", calls[1])
        fallback = fallback_libx264_cmd(nvenc_cmd)
        self.assertEqual(calls[1], fallback)


class TestExecutedArgvFidelity(unittest.TestCase):
    """#309 persists the argv that SUCCEEDED. An NVENC fallback must not let the
    booth show (and the operator copy) the h264_nvenc command that failed."""

    def test_executed_cmd_reports_the_libx264_retry_not_the_failed_nvenc(self):
        nvenc_cmd = ["ffmpeg", "-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23", "out.mp4"]

        def runner(cmd):
            return SimpleNamespace(returncode=0 if "libx264" in cmd else 1, stderr="nvenc fail")

        proc = run_ffmpeg_with_nvenc_fallback(nvenc_cmd, runner=runner)
        ran = executed_cmd(proc, nvenc_cmd)
        self.assertIn("libx264", ran)
        self.assertNotIn("h264_nvenc", ran)
        self.assertEqual(ran, fallback_libx264_cmd(nvenc_cmd))

    def test_executed_cmd_is_the_original_when_no_fallback_happened(self):
        cpu_cmd = ["ffmpeg", "-c:v", "libx264", "-preset", "fast", "-crf", "23", "out.mp4"]
        proc = run_ffmpeg_with_nvenc_fallback(
            cpu_cmd, runner=lambda _cmd: SimpleNamespace(returncode=0, stderr="")
        )
        self.assertEqual(executed_cmd(proc, cpu_cmd), cpu_cmd)

    def test_outro_success_callback_carries_the_command_that_ran(self):
        import tempfile
        from pathlib import Path

        from video.channel_outro import append_channel_outro

        captured: dict[str, list[str]] = {}
        with tempfile.TemporaryDirectory() as td:
            body = Path(td, "body.mp4")
            body.write_bytes(b"real-body")

            def fake_run(cmd, **_kwargs):
                if "h264_nvenc" in cmd:
                    return SimpleNamespace(returncode=1, stderr="nvenc unavailable")
                Path(cmd[-1]).write_bytes(b"concatenated")
                return SimpleNamespace(returncode=0, stderr="")

            with (
                patch.dict(os.environ, {"NVENC": "1"}),
                patch("core.cuda_probe.ffmpeg_has_nvenc", return_value=True),
                patch(
                    "video.channel_outro.resolve_end_card",
                    return_value={
                        "enabled": True,
                        "duration": 1.0,
                        "text": "Tap in",
                        "bg": "#000000",
                        "fg": "#ffffff",
                    },
                ),
                patch("video.encoder.subprocess.run", side_effect=fake_run),
            ):
                append_channel_outro(
                    str(body),
                    channel_id="tapin",
                    command_callback=lambda kind, argv: captured.__setitem__(kind, argv),
                )

        self.assertIn("h264_nvenc", captured["outro_attempt"])
        self.assertIn("libx264", captured["outro_success"])
        self.assertNotIn("h264_nvenc", captured["outro_success"])

    def test_render_ffmpeg_run_stamps_the_libx264_retry(self):
        from video.render_video import _ffmpeg_run

        nvenc_cmd = ["ffmpeg", "-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23", "out.mp4"]
        seen: list[list[str]] = []

        def fake_run(cmd, **_kwargs):
            seen.append(list(cmd))
            return SimpleNamespace(returncode=0 if "libx264" in cmd else 1, stderr="nvenc fail")

        with patch("video.render_video.subprocess.run", side_effect=fake_run):
            proc = _ffmpeg_run(nvenc_cmd)

        self.assertEqual(len(seen), 2)
        self.assertEqual(proc.returncode, 0)
        ran = executed_cmd(proc, nvenc_cmd)
        self.assertIn("libx264", ran)
        self.assertNotIn("h264_nvenc", ran)


if __name__ == "__main__":
    unittest.main()
