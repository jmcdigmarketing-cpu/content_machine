"""Behavioral coverage for the five post-wave-4 roadmap pickups."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from assets.local_provider import LocalAssetProvider
from core import human_presence, overnight, pipeline, review_booth, win_notify


class TestOvernightPause(unittest.TestCase):
    def test_flag_short_circuits_before_topic_collection(self):
        from core.overnight_pause import set_paused

        with tempfile.TemporaryDirectory() as tmp:
            flag = os.path.join(tmp, "overnight.paused")
            with patch.dict(os.environ, {"OVERNIGHT_PAUSE_FILE": flag}, clear=False):
                self.assertTrue(set_paused(True))
                with patch("core.batch_generation.collect_topics") as collect:
                    result = overnight.run_overnight("tapin", count=3)
        collect.assert_not_called()
        self.assertEqual(result.requested, 0)
        self.assertIn("paused", overnight.render_overnight(result).lower())

    def test_tray_pause_and_resume_use_the_real_flag(self):
        from core.overnight_pause import is_paused

        with tempfile.TemporaryDirectory() as tmp:
            flag = os.path.join(tmp, "overnight.paused")
            with (
                patch.dict(os.environ, {"OVERNIGHT_PAUSE_FILE": flag}, clear=False),
                patch.object(win_notify, "show_quota_chip", return_value="chip"),
            ):
                self.assertEqual(win_notify.run_tray(pause_overnight=True), 0)
                self.assertTrue(is_paused())
                self.assertEqual(win_notify.run_tray(resume_overnight=True), 0)
                self.assertFalse(is_paused())


class TestHumanLastSeen(unittest.TestCase):
    def test_relative_label_reads_the_real_heartbeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            heartbeat = os.path.join(tmp, "heartbeat.json")
            with patch.dict(os.environ, {"HUMAN_PRESENCE_HOURS": "24"}, clear=False):
                human_presence.touch(at=1_000.0, path=heartbeat)
                label = human_presence.last_seen_label(now=8_200.0, path=heartbeat)
        self.assertEqual(label, "Human: 2h ago")

    def test_tray_chip_uses_heartbeat_without_mocking_formatter(self):
        snap = {
            "youtube": {"remaining": 10_000},
            "elevenlabs": {"chars_used": 0},
            "apify": {"exhausted": False},
        }
        with tempfile.TemporaryDirectory() as tmp:
            heartbeat = os.path.join(tmp, "heartbeat.json")
            with (
                patch.dict(
                    os.environ,
                    {
                        "HUMAN_PRESENCE_HOURS": "24",
                        "CONTENT_TRAY_PRESENCE": "true",
                    },
                    clear=False,
                ),
                patch.object(human_presence, "HEARTBEAT_FILE", heartbeat),
                patch.object(human_presence.time, "time", return_value=7_300.0),
                patch("apis.youtube_quota.uploads_remaining", return_value=6),
            ):
                human_presence.touch(at=100.0)
                lines = win_notify.quota_chip_lines(snap)
        self.assertIn("Human: 2h ago", lines)


class TestBoothDebugDetails(unittest.TestCase):
    def test_windows_copy_command_quotes_powershell_metacharacters(self):
        command = review_booth._command_line(
            [
                "ffmpeg",
                "-filter_complex",
                "[0:v]scale=1080:1920[v];[v]fps=30[out]",
                r"C:\Rendered Videos\out.mp4",
            ]
        )
        self.assertEqual(
            command,
            "& 'ffmpeg' '-filter_complex' "
            "'[0:v]scale=1080:1920[v];[v]fps=30[out]' "
            r"'C:\Rendered Videos\out.mp4'",
        )

    def test_pipeline_persists_commands_reported_by_real_callback_seam(self):
        captured_callback = {}

        def fake_render(*args, command_callback=None, **kwargs):
            captured_callback["value"] = command_callback
            command_callback("primary", ["ffmpeg", "-i", "voice.mp3", "out.mp4"])
            command_callback("intro", ["ffmpeg", "-i", "intro.mp4", "out.mp4"])
            return "out.mp4", None

        with (
            patch.dict(
                os.environ,
                {"THUMBNAIL_MODE": "off", "CONTENT_RENDER_PROGRESS": "0"},
                clear=False,
            ),
            patch.object(
                pipeline,
                "media_paths_for_topic",
                return_value=("voice.mp3", "out.mp4", "out.mp4"),
            ),
            patch.object(pipeline, "generate_audio"),
            patch.object(pipeline, "render_vertical_video", side_effect=fake_render),
            patch.object(pipeline, "update_content_run_media"),
            patch.object(pipeline, "record_render_assets"),
            patch("core.run_features.load_features", return_value={}),
            patch("core.run_features.merge_features"),
            patch("core.run_trace.update_trace") as update,
        ):
            pipeline.run_media_only("topic", "script", channel_id="tapin", content_run_id=71)

        self.assertIsNotNone(captured_callback.get("value"))
        trace_patch = update.call_args[0][1]
        self.assertEqual(trace_patch["ffmpeg_command"][0], "ffmpeg")
        self.assertIn("intro.mp4", trace_patch["ffmpeg_intro_command"])

    def test_booth_collapses_escaped_trace_and_copies_ffmpeg(self):
        html = review_booth.booth_html(
            trace_json=json.dumps({"token": "[redacted]", "title": "<unsafe>"}),
            ffmpeg_command='ffmpeg -i "voice file.mp3" out.mp4',
            ffmpeg_intro_command="ffmpeg -i intro.mp4 out.mp4",
        )
        self.assertIn("<summary>Raw trace JSON</summary>", html)
        self.assertIn("&lt;unsafe&gt;", html)
        self.assertNotIn("<unsafe>", html)
        self.assertIn("<summary>FFmpeg commands</summary>", html)
        self.assertIn("Copy ffmpeg command", html)
        self.assertIn("intro.mp4", html)


class TestBoothDesktopShortcut(unittest.TestCase):
    def test_installer_targets_persistent_booth_launcher(self):
        from core.win_shell import install_booth_desktop_shortcut

        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "Content OS Review Booth.lnk")
            with (
                patch("core.win_shell.desktop_booth_shortcut_path", return_value=dest),
                patch("core.win_shell.os.name", "posix"),
            ):
                written = install_booth_desktop_shortcut()
            with open(written, encoding="utf-8") as fh:
                text = fh.read()
        self.assertIn("booth_os.pyw", text)


class TestLocalClipLicense(unittest.TestCase):
    def test_root_license_flows_through_local_provider_attribution(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = os.path.join(tmp, "gaming", "gta")
            os.makedirs(folder)
            clip = os.path.join(folder, "clip.mp4")
            with open(clip, "wb") as fh:
                fh.write(b"clip")
            with open(os.path.join(tmp, "license.yaml"), "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "owner": "TapIn Media",
                        "license": "owned",
                        "commercial_use": True,
                    },
                    fh,
                )

            with (
                patch("assets.local_provider.BASE_VIDEO_DIR", tmp),
                patch("assets.local_provider._ai_choose_folder", return_value=folder),
            ):
                result = LocalAssetProvider().find_video("GTA 6", "gaming")

        self.assertIsNotNone(result)
        self.assertEqual(result.path, clip)
        self.assertIn("TapIn Media", result.attribution or "")
        self.assertIn("owned", result.attribution or "")


if __name__ == "__main__":
    unittest.main()
