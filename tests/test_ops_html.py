"""ops --html / tray / blocking / shortcut commands (no browser, no Start Menu COM)."""

from __future__ import annotations

import argparse
import os
import tempfile
import unittest
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

    def test_blocking_command_prints_sentence(self):
        args = argparse.Namespace(channel="tapin", html=False)
        with patch(
            "core.publish_blockers.blocking_publish_sentence",
            return_value="Nothing is blocking publish: ok.",
        ):
            self.assertEqual(ops.cmd_blocking(args), 0)

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
            "blocking",
            "secrets-doctor",
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


if __name__ == "__main__":
    unittest.main()
