"""Fail-first coverage for backlog UI items #233, #269, #300, #451, #529 and #532."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests.qt_support import requires_qt


class NotificationSoundTests(unittest.TestCase):
    def test_render_toast_uses_distinct_shipped_channel_sounds(self):
        from config.channels import get_channel_profile
        from core import win_notify

        with tempfile.TemporaryDirectory() as tmp:
            tapin_file = Path(tmp, "tapin.mp4")
            money_file = Path(tmp, "moneywise.mp4")
            tapin_file.write_bytes(b"x")
            money_file.write_bytes(b"x")
            win_notify._toasted.clear()
            with (
                patch.object(win_notify, "toast_enabled", return_value=True),
                patch.object(win_notify, "_toasts_muted", return_value=False),
                patch.object(subprocess, "Popen", return_value=MagicMock()) as popen,
            ):
                win_notify.notify_ffmpeg_done(str(tapin_file), channel_id="tapin")
                tapin_script = str(popen.call_args.args[0][-1])
                win_notify.notify_ffmpeg_done(str(money_file), channel_id="moneywise")
                money_script = str(popen.call_args.args[0][-1])

        tapin_sound = get_channel_profile("tapin").notification_sound
        money_sound = get_channel_profile("moneywise").notification_sound
        self.assertTrue(tapin_sound)
        self.assertTrue(money_sound)
        self.assertNotEqual(tapin_sound, money_sound)
        self.assertIn(f'<audio src="{tapin_sound}"', tapin_script)
        self.assertIn(f'<audio src="{money_sound}"', money_script)


class BoothCaptionToggleTests(unittest.TestCase):
    def test_booth_can_switch_between_retext_and_proportional_tracks(self):
        from core.review_booth import booth_html

        with tempfile.TemporaryDirectory() as tmp:
            mp4 = Path(tmp, "video.mp4")
            mp4.write_bytes(b"mp4")
            html = booth_html(
                mp4_path=str(mp4),
                captions_href="retext.vtt",
                proportional_captions_href="proportional.vtt",
            )

        self.assertIn("captions-retext", html)
        self.assertIn("captions-proportional", html)
        self.assertIn("setCaptionMode", html)
        self.assertIn("Burned", html)
        self.assertIn("Proportional", html)


class BoothTagTests(unittest.TestCase):
    def test_applying_tag_chips_updates_the_run_and_queued_package(self):
        from core.review_booth import apply_booth_tags

        run = SimpleNamespace(id=7, tags_json='["old"]')
        job = SimpleNamespace(
            id=12,
            content_run_id=7,
            payload_json=json.dumps({"title": "T", "tags": ["old"]}),
        )
        run_repo = MagicMock()
        run_repo.get.return_value = run
        job_repo = MagicMock()
        job_repo.list_active_jobs.return_value = [job]

        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository",
                return_value=run_repo,
            ),
            patch("storage.repositories.jobs.get_job_repository", return_value=job_repo),
        ):
            saved = apply_booth_tags(7, [" UFC ", "news", "ufc", ""])

        self.assertEqual(saved, ["UFC", "news"])
        run_tags = json.loads(run_repo.update.call_args.args[1]["tags_json"])
        self.assertEqual(run_tags, ["UFC", "news"])
        job_payload = json.loads(job_repo.update.call_args.args[1]["payload_json"])
        self.assertEqual(job_payload["tags"], ["UFC", "news"])


class PhoneBoothTests(unittest.TestCase):
    def test_booth_player_fits_a_phone_width_viewport(self):
        from core.review_booth import booth_html

        html = booth_html()
        self.assertIn("@media (max-width: 520px)", html)
        self.assertIn(".phone-bezel", html)
        self.assertIn("calc(100vw -", html)


@requires_qt
class DesktopScreenshotTests(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        self.app = QApplication.instance() or QApplication([])

    def test_active_panel_is_copied_to_the_qt_clipboard(self):
        from PySide6.QtWidgets import QApplication

        from desktop.shell import MainShell

        with patch("desktop.home.home_lines", return_value=[("Queue", "2 waiting")]):
            shell = MainShell(channel_id="tapin")
        shell.show()
        self.app.processEvents()
        self.assertTrue(shell.copy_active_panel_screenshot())
        self.assertFalse(QApplication.clipboard().pixmap().isNull())
        shell.close()


class DesktopChangelogTests(unittest.TestCase):
    @staticmethod
    def _git(root: str, *args: str, when: str | None = None) -> None:
        env = os.environ.copy()
        if when:
            env["GIT_AUTHOR_DATE"] = when
            env["GIT_COMMITTER_DATE"] = when
        subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )

    def test_changelog_reads_only_commits_since_the_previous_launch(self):
        from desktop.home import changelog_since_last_launch

        with tempfile.TemporaryDirectory() as tmp:
            self._git(tmp, "init")
            self._git(tmp, "config", "user.email", "test@example.com")
            self._git(tmp, "config", "user.name", "Test")
            Path(tmp, "note.txt").write_text("one", encoding="utf-8")
            self._git(tmp, "add", "note.txt")
            self._git(tmp, "commit", "-m", "first launch", when="2026-01-01T12:00:00+00:00")
            state = Path(tmp, "launch.json")
            state.write_text(
                json.dumps({"tapin": {"last_launch": "2026-01-01T18:00:00+00:00"}}),
                encoding="utf-8",
            )
            Path(tmp, "note.txt").write_text("two", encoding="utf-8")
            self._git(tmp, "add", "note.txt")
            self._git(tmp, "commit", "-m", "after launch", when="2026-01-02T12:00:00+00:00")

            lines = changelog_since_last_launch(
                "tapin",
                root=tmp,
                state_path=state,
                now=datetime(2026, 1, 3, tzinfo=timezone.utc),
            )

            self.assertTrue(any("after launch" in line for line in lines), lines)
            self.assertFalse(any("first launch" in line for line in lines), lines)
            saved = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(saved["tapin"]["last_launch"], "2026-01-03T00:00:00+00:00")

    def test_home_writes_isolated_launch_state_not_the_operator_store(self):
        from config.paths import DATA_DIR
        from desktop.home import home_lines

        operator = Path(DATA_DIR) / "launch_state.json"
        if operator.exists():
            operator.unlink()
        with tempfile.TemporaryDirectory() as tmp:
            isolated = Path(tmp, "launch_state.json")
            with (
                patch.dict(os.environ, {"CONTENT_LAUNCH_STATE": str(isolated)}),
                patch("core.money.ledger.spend_line", return_value="Spent so far: $1.00"),
                patch("youtube.oauth.sign_in_status", return_value=""),
                patch("youtube.oauth.sign_in_reminder", return_value=""),
                patch("desktop.home._queue_line", return_value=""),
                patch("desktop.home._recent_lines", return_value=[]),
                patch("analytics.auto_research_report.verdict_line", return_value=""),
                patch("desktop.home._ads", return_value=""),
            ):
                home_lines("tapin")
            self.assertTrue(isolated.is_file(), isolated)
            self.assertFalse(operator.exists(), operator)


if __name__ == "__main__":
    unittest.main()
