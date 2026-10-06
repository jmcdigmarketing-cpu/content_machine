"""#981 one desktop window, #982 a launcher that opens it.

Operator, 2026-10-06: "it kinda opens another terminal when i run from the folder, but it
actually doesn't do anything for me atm ... I wanted more typical desktop application". The
file in the folder and the Start Menu shortcut (`content_os.pyw`) ran `core.win_notify.run_tray`
- a quota chip and a toast. The real Qt app (`desktop/`, Stages 0-4) was seven separate windows
behind seven flags. Now `py -m desktop` and `content_os.pyw` open one window: a sidebar
(Home, New video, Review, Queue, Costs, Studio, Brand) over the existing windows as pages, with a
Home page of what matters at a glance. The chip stays behind `--chip`; the old flags still open
single windows.
"""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tests.qt_support import requires_qt


class HomeLinesTests(unittest.TestCase):
    def test_home_lists_what_matters(self):
        from desktop.home import home_lines

        with (
            patch("core.money.ledger.spend_line", return_value="Spent so far: $54.00"),
            patch("youtube.oauth.sign_in_status", return_value=""),
            patch("youtube.oauth.sign_in_reminder", return_value="6 days old - renew"),
            patch("desktop.home._queue_line", return_value="Queue: 2 waiting"),
            patch("desktop.home._recent_lines", return_value=["Heat preseason - 480 views (low)"]),
            patch("analytics.auto_research_report.verdict_line", return_value=""),
        ):
            lines = dict(home_lines("tapin"))
        self.assertEqual(lines["Money"], "Spent so far: $54.00")
        self.assertIn("6 days old", lines["Sign-in"])
        self.assertEqual(lines["Queue"], "Queue: 2 waiting")
        self.assertIn("480 views", lines["Last videos"])

    def test_a_broken_reader_does_not_break_home(self):
        from desktop.home import home_lines

        with (
            patch("core.money.ledger.spend_line", side_effect=RuntimeError("db gone")),
            patch("youtube.oauth.sign_in_status", return_value="No YouTube sign-in"),
            patch("desktop.home._queue_line", return_value=""),
            patch("desktop.home._recent_lines", return_value=[]),
            patch("analytics.auto_research_report.verdict_line", return_value=""),
        ):
            lines = dict(home_lines("tapin"))
        self.assertIn("unavailable", lines["Money"])
        self.assertIn("No YouTube sign-in", lines["Sign-in"])


class ModeTests(unittest.TestCase):
    def test_no_flag_opens_the_app(self):
        from desktop.launch import desktop_mode

        self.assertEqual(desktop_mode([]), "shell")
        self.assertEqual(desktop_mode(["--run"]), "run")
        self.assertEqual(desktop_mode(["--queue"]), "queue")
        self.assertEqual(desktop_mode(["--chip"]), "chip")


class PywTests(unittest.TestCase):
    def _main(self, argv):
        import runpy

        with (
            patch("sys.argv", ["content_os.pyw", *argv]),
            patch("desktop.launch.launch", return_value=0) as launch,
            patch("core.win_notify.run_tray", return_value=0) as tray,
        ):
            with self.assertRaises(SystemExit):
                runpy.run_path("content_os.pyw", run_name="__main__")
        return launch, tray

    def test_the_folder_launcher_opens_the_app(self):
        launch, tray = self._main([])
        launch.assert_called_once()
        tray.assert_not_called()

    def test_the_chip_is_still_there(self):
        launch, tray = self._main(["--chip"])
        tray.assert_called_once()
        launch.assert_not_called()

    def test_no_qt_under_pythonw_shows_a_box_not_a_console_line(self):
        from desktop import launch as launcher

        shown: list[str] = []
        with (
            patch.object(launcher, "_qt_available", return_value=False),
            patch.object(launcher, "_no_console", return_value=True),
            patch.object(launcher, "_message_box", side_effect=shown.append),
        ):
            self.assertEqual(launcher.launch(), 2)
        self.assertTrue(shown and 'pip install -e ".[app]"' in shown[0])


class ShortcutTests(unittest.TestCase):
    def test_shortcut_installs_start_menu_and_desktop(self):
        from scripts.ops import COMMANDS

        with (
            patch("core.win_shell.install_start_menu_shortcut", return_value="S.lnk") as start,
            patch("core.win_shell.install_app_desktop_shortcut", return_value="D.lnk") as desk,
        ):
            COMMANDS["shortcut"][1](SimpleNamespace())
        start.assert_called_once()
        desk.assert_called_once()


@requires_qt
class ShellTests(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        if QApplication.instance() is None:
            QApplication([])

    def test_one_window_with_a_sidebar_of_pages(self):
        from desktop.shell import PAGES, MainShell

        with patch("desktop.home.home_lines", return_value=[("Money", "Spent so far: $54.00")]):
            shell = MainShell(channel_id="tapin")
        names = [shell.sidebar.item(i).text() for i in range(shell.sidebar.count())]
        self.assertEqual(names, [name for name, _key in PAGES])
        self.assertEqual(names[0], "Home")
        self.assertIn("New video", names)
        self.assertEqual(shell.stack.currentIndex(), 0)
        self.assertIn("Spent so far: $54.00", shell.home_text())
        shell.close()

    def test_new_video_opens_on_the_apps_channel(self):
        # Live check, 2026-10-06: the run window opened on "Default" and titled itself
        # MoneyWise (its brand line knew only TapIn).
        from desktop.shell import build_page

        page = build_page("run", "tapin")
        self.assertEqual(page.channel.currentData(), "tapin")
        self.assertEqual(page.brand.text(), "TapIn")
        page.channel.setCurrentIndex(page.channel.findData("default"))
        self.assertNotEqual(page.brand.text(), "MoneyWise")
        page.close()

    def test_a_page_is_built_when_first_opened(self):
        from PySide6.QtWidgets import QLabel, QWidget

        from desktop.shell import MainShell

        built: list[str] = []

        def factory(key):
            built.append(key)
            return QLabel(f"page {key}")

        with patch("desktop.home.home_lines", return_value=[]):
            shell = MainShell(channel_id="tapin", factory=factory)
        self.assertEqual(built, [])
        shell.sidebar.setCurrentRow(2)
        self.assertEqual(len(built), 1)
        self.assertIsInstance(shell.stack.currentWidget(), QWidget)
        shell.sidebar.setCurrentRow(2)
        self.assertEqual(len(built), 1)  # not rebuilt
        shell.close()

    def test_a_page_that_fails_shows_why(self):
        from desktop.shell import MainShell

        def factory(_key):
            raise RuntimeError("no review context")

        with patch("desktop.home.home_lines", return_value=[]):
            shell = MainShell(channel_id="tapin", factory=factory)
        shell.sidebar.setCurrentRow(3)
        self.assertIn("no review context", shell.stack.currentWidget().findChild(
            __import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel).text())  # fmt: skip
        shell.close()


if __name__ == "__main__":
    unittest.main()
