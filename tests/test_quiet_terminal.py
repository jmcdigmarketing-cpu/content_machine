"""#986: a quieter terminal - one header line at startup, the detail in a log file.

Operator, 2026-10-06: "cleaner ui?". `main.py` printed six separate lines before the menu
(sign-in, spend, "Using:", the goal, the upload quota, the reminder), and the INFO logs had
nowhere to go: the console is WARNING, so they were dropped. Now:

- `core.status.header_line` - one line: channel · sign-in · spent · uploads left · queue ·
  last video's organic views. Each part reads fail-open and is left out when unknown.
- `main._print_startup` prints the header, and a separate line only for something to act on
  (a dead sign-in, a renewal due, no uploads left).
- `core.logging` writes INFO and up to `data/logs/content_machine.log` (`CONTENT_LOG_FILE`;
  blank turns it off; the suite sets it blank). The console stays at its level.
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

PARTS = {
    "_hdr_name": "TapIn",
    "_hdr_sign_in": "sign-in ok",
    "_hdr_spent": "spent $81.00",
    "_hdr_uploads": "~5 uploads left",
    "_hdr_queue": "queue 2",
    "_hdr_last": "last video 480 views",
}


def _patched(**over):
    values = {**PARTS, **over}
    return [patch(f"core.status.{name}", **({"side_effect": v} if isinstance(v, Exception)
                                            else {"return_value": v}))
            for name, v in values.items()]  # fmt: skip


class HeaderTests(unittest.TestCase):
    def _header(self, **over):
        from core.status import header_line

        patches = _patched(**over)
        for p in patches:
            p.start()
        try:
            return header_line("tapin")
        finally:
            for p in patches:
                p.stop()

    def test_one_line(self):
        self.assertEqual(
            self._header(),
            "TapIn · sign-in ok · spent $81.00 · ~5 uploads left · queue 2 · last video 480 views",
        )

    def test_an_unknown_or_failing_part_is_left_out(self):
        got = self._header(_hdr_last="", _hdr_queue=RuntimeError("no db"))
        self.assertEqual(got, "TapIn · sign-in ok · spent $81.00 · ~5 uploads left")

    def test_sign_in_words(self):
        from core import status

        with patch("youtube.oauth.sign_in_status", return_value="No YouTube sign-in"):
            self.assertEqual(status._hdr_sign_in("tapin"), "signed out")
        with (
            patch("youtube.oauth.sign_in_status", return_value=""),
            patch("youtube.oauth.sign_in_reminder", return_value="6 days old - renew"),
        ):
            self.assertEqual(status._hdr_sign_in("tapin"), "sign-in due")
        with (
            patch("youtube.oauth.sign_in_status", return_value=""),
            patch("youtube.oauth.sign_in_reminder", return_value=""),
        ):
            self.assertEqual(status._hdr_sign_in("tapin"), "sign-in ok")

    def test_spent_reads_the_ledger(self):
        from core import status

        with patch("core.money.ledger.total_spent", return_value={"total": 81.0, "count": 3}):
            self.assertEqual(status._hdr_spent(), "spent $81.00")
        with patch("core.money.ledger.total_spent", return_value={"total": 0.0, "count": 0}):
            self.assertEqual(status._hdr_spent(), "spent: not entered")


class StartupTests(unittest.TestCase):
    def _startup(self, *, sign_in="", reminder="", uploads=5):
        import main

        buf = io.StringIO()
        with (
            patch("core.status.header_line", return_value="TapIn · sign-in ok"),
            patch("youtube.oauth.sign_in_status", return_value=sign_in),
            patch("youtube.oauth.sign_in_reminder", return_value=reminder),
            patch("apis.youtube_quota.uploads_remaining", return_value=uploads),
            patch("apis.youtube_quota.format_uploads_left", return_value="~0 upload(s) left"),
            redirect_stdout(buf),
        ):
            main._print_startup("tapin")
        return [line for line in buf.getvalue().splitlines() if line.strip()]

    def test_a_healthy_start_is_one_line(self):
        self.assertEqual(self._startup(), ["  TapIn · sign-in ok"])

    def test_problems_keep_their_own_line(self):
        lines = self._startup(sign_in="No YouTube sign-in - py -m youtube.oauth_setup", uploads=0)
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[1].startswith("  ! No YouTube sign-in"))
        self.assertIn("~0 upload(s) left", lines[2])

    def test_a_due_renewal_is_said(self):
        lines = self._startup(reminder="6 days old - renew")
        self.assertEqual(lines[1], "  ~ 6 days old - renew")


class LogFileTests(unittest.TestCase):
    def test_default_path_and_off_switch(self):
        from config.paths import DATA_DIR
        from core.logging import log_file_path

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CONTENT_LOG_FILE", None)
            self.assertEqual(log_file_path(), os.path.join(DATA_DIR, "logs", "content_machine.log"))
        with patch.dict(os.environ, {"CONTENT_LOG_FILE": ""}):
            self.assertIsNone(log_file_path())
        with patch.dict(os.environ, {"CONTENT_LOG_FILE": "x.log"}):
            self.assertEqual(log_file_path(), "x.log")

    def test_the_suite_writes_no_log_file(self):
        self.assertEqual(os.environ.get("CONTENT_LOG_FILE"), "")

    def test_info_goes_to_the_file_not_the_console(self):
        # The real setup path, isolated: a fresh root handler list and a captured stdout.
        from core import logging as cm_logging

        root = logging.getLogger()
        app = logging.getLogger("content_machine")
        saved = (root.handlers[:], app.handlers[:], app.level, cm_logging._CONFIGURED)
        screen = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "logs", "cm.log")
            try:
                root.handlers[:] = []
                app.handlers[:] = []
                cm_logging._CONFIGURED = False
                with (
                    patch.dict(
                        os.environ, {"CONTENT_LOG_FILE": path, "CONTENT_LOG_LEVEL": "WARNING"}
                    ),
                    patch("sys.stdout", screen),
                ):
                    cm_logging.setup_logging()
                    log = cm_logging.get_logger("quiet_test")
                    log.info("routine detail 986")
                    log.warning("something to fix 986")
                for handler in app.handlers:
                    handler.flush()
                with open(path, encoding="utf-8") as f:
                    written = f.read()
            finally:
                for handler in app.handlers:
                    handler.close()
                root.handlers[:] = saved[0]
                app.handlers[:] = saved[1]
                app.setLevel(saved[2])
                cm_logging._CONFIGURED = saved[3]
        self.assertIn("routine detail 986", written)
        self.assertIn("something to fix 986", written)
        self.assertNotIn("routine detail 986", screen.getvalue())
        self.assertIn("something to fix 986", screen.getvalue())


class OpsTestTests(unittest.TestCase):
    # Found running the wave: `ops test --order reverse` runs the suite in its own process,
    # which had already attached the log file when scripts.ops was imported - the tests then
    # logged into data/logs/ and the #892 hygiene check failed (CI runs this order).
    def test_ops_test_detaches_the_log_file_first(self):
        from types import SimpleNamespace

        from scripts.ops import COMMANDS

        calls: list[str] = []
        with (
            patch("core.logging.detach_log_file", side_effect=lambda: calls.append("detach")),
            patch(
                "core.suite_order.run_ordered", side_effect=lambda *a, **k: calls.append("run") or 0
            ),
            patch("core.suite_hygiene.changed", return_value=[]),
        ):
            COMMANDS["test"][1](SimpleNamespace(order="reverse", seed=None))
        self.assertEqual(calls, ["detach", "run"])

    def test_detach_removes_the_file_handler(self):
        from core import logging as cm_logging

        with tempfile.TemporaryDirectory() as tmp:
            handler = cm_logging.attach_log_file(os.path.join(tmp, "cm.log"))
            app = logging.getLogger("content_machine")
            self.assertIn(handler, app.handlers)
            cm_logging.detach_log_file()
            self.assertNotIn(handler, app.handlers)
            self.assertFalse(os.path.exists(os.path.join(tmp, "cm.log")))  # nothing logged yet


if __name__ == "__main__":
    unittest.main()
