"""ops --html / tray / blocking / shortcut commands (no browser, no Start Menu COM)."""

from __future__ import annotations

import argparse
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts import ops


class TestOpsHtmlAndHelpers(unittest.TestCase):
    def test_emit_text_writes_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(html=True)
            with patch.dict(os.environ, {"CONTENT_HTML_DIR": tmp, "CONTENT_HTML_OPEN": "false"}):
                ops._emit_text("Reliability", "Apify ON", args)
            files = os.listdir(tmp)
            self.assertTrue(any(name.endswith(".html") for name in files))

    def test_emit_text_passes_channel_into_the_html_dump(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(html=True, channel="moneywise")
            with patch.dict(os.environ, {"CONTENT_HTML_DIR": tmp, "CONTENT_HTML_OPEN": "false"}):
                ops._emit_text("Reliability", "Apify ON", args)
            text = Path(os.path.join(tmp, os.listdir(tmp)[0])).read_text(encoding="utf-8")
        self.assertIn("channel-moneywise", text)
        self.assertIn("Georgia", text)

    def test_blocking_command_prints_sentence(self):
        args = argparse.Namespace(channel="tapin", html=False)
        with patch(
            "core.publish_blockers.publish_status_sentence",
            return_value="Nothing is blocking publish: ok.",
        ) as status:
            self.assertEqual(ops.cmd_blocking(args), 0)
        status.assert_called_once_with("tapin")

    def test_shortcut_writes_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "Content OS.lnk")
            with (
                patch("core.win_shell.start_menu_shortcut_path", return_value=dest),
                patch("core.win_shell.start_menu_dir", return_value=tmp),
                patch("core.win_shell.os.name", "posix"),
            ):
                from core.win_shell import install_start_menu_shortcut

                written = install_start_menu_shortcut()
            self.assertTrue(os.path.isfile(written))

    def test_registry_includes_new_commands(self):
        for name in (
            "tray",
            "booth",
            "lightbox",
            "reveal",
            "shortcut",
            "booth-shortcut",
            "blocking",
            "secrets-doctor",
            "vault-decay",
            "next",
        ):
            self.assertIn(name, ops.COMMANDS)

    def test_grade_html_flag_dumps(self):
        args = argparse.Namespace(run_id=1, html=True, channel="tapin")
        fake_grade = type("G", (), {"letter": "B", "score": 80, "components": []})()
        record = MagicMock(script_preview="x", channel_id="tapin")
        repo = MagicMock()
        repo.get.return_value = record
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.dict(os.environ, {"CONTENT_HTML_DIR": tmp, "CONTENT_HTML_OPEN": "false"}),
                patch(
                    "storage.repositories.content_runs.get_content_run_repository",
                    return_value=repo,
                ),
                patch("core.video_grade.grade_from_record", return_value=fake_grade),
                patch("core.video_grade.render_grade", return_value="Report card: B (80/100)"),
                patch("core.video_grade.render_expert_panel", return_value=""),
            ):
                self.assertEqual(ops.cmd_grade(args), 0)
            self.assertTrue(any(name.endswith(".html") for name in os.listdir(tmp)))

    def test_intelligence_report_requires_topic(self):
        args = argparse.Namespace(topic="", channel="tapin", sku=False, no_brief=False)
        self.assertEqual(ops.cmd_intelligence_report(args), 1)

    def test_tray_passes_channel_to_run_tray(self):
        args = argparse.Namespace(
            channel="moneywise", stay=False, open_output=False, doctor_html=False
        )
        with patch("core.win_notify.run_tray", return_value=0) as tray:
            self.assertEqual(ops.cmd_tray(args), 0)
        tray.assert_called_once()
        self.assertEqual(tray.call_args.kwargs.get("channel_id"), "moneywise")


if __name__ == "__main__":
    unittest.main()
