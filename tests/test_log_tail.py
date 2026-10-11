"""#990: the log file has no reader.

INFO goes to data/logs/content_machine.log. Nothing prints the last lines, and the
Costs page does not show the latest warning.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from argparse import Namespace
from io import StringIO
from unittest.mock import patch

from tests.qt_support import requires_qt

_WARNING = "2026-10-10 22:00:01 [WARNING] content_machine: fact conflict on Jones"
_LOG = f"2026-10-10 22:00:00 [INFO] content_machine: routine detail\n{_WARNING}\n"


class TailLogTests(unittest.TestCase):
    def _path(self, tmp: str) -> str:
        path = os.path.join(tmp, "cm.log")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(_LOG)
        return path

    def test_the_tail_returns_the_warning(self):
        from core.logging import log_link_text, tail_log

        with tempfile.TemporaryDirectory() as tmp:
            path = self._path(tmp)
            with patch.dict(os.environ, {"CONTENT_LOG_FILE": path}):
                got = tail_log(40)
                label = log_link_text(40)
        self.assertEqual(got["warnings"], [_WARNING])
        self.assertEqual(got["lines"][-1], _WARNING)
        self.assertIn(path, label)
        self.assertIn("fact conflict on Jones", label)

    def test_a_missing_file_is_empty_and_says_so(self):
        from core.logging import log_link_text, tail_log

        missing = os.path.join(tempfile.gettempdir(), "cm-no-such-log-990.log")
        with patch.dict(os.environ, {"CONTENT_LOG_FILE": missing}):
            got = tail_log(40)
            label = log_link_text(40)
        self.assertEqual(got["lines"], [])
        self.assertEqual(got["warnings"], [])
        self.assertIn("no warnings in the log", label)

    def test_ops_log_prints_the_warning(self):
        from scripts.ops import COMMANDS

        with tempfile.TemporaryDirectory() as tmp:
            path = self._path(tmp)
            buf = StringIO()
            with (
                patch.dict(os.environ, {"CONTENT_LOG_FILE": path}),
                patch("sys.stdout", buf),
            ):
                code = COMMANDS["log"][1](Namespace(limit=40))
        self.assertEqual(code, 0)
        self.assertIn("fact conflict on Jones", buf.getvalue())

    @requires_qt
    def test_the_costs_page_shows_the_same_warning(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        from core.logging import log_link_text
        from desktop.cost import CostWindow

        if QApplication.instance() is None:
            QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            path = self._path(tmp)
            with patch.dict(os.environ, {"CONTENT_LOG_FILE": path}):
                expected = log_link_text(40)
                window = CostWindow(rows=[])
                shown = window.log_label.text()
                window.close()
        self.assertEqual(shown, expected)
        self.assertIn("fact conflict on Jones", shown)


if __name__ == "__main__":
    unittest.main()
