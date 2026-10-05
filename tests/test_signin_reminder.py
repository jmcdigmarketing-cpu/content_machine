"""#974: a reminder before a Testing-mode YouTube sign-in expires.

While the Google consent screen is in Testing, a sign-in stops working 7 days after it was
made (#961) - the operator found out from a failed `ops all`. The token file cannot say when the
sign-in happened: every refresh rewrites it. So `save_credentials` now stamps `signed_in_at` on
a fresh sign-in (`run_interactive_oauth`) and carries the stamp through refreshes, and
`sign_in_reminder` says so from day `SIGN_IN_REMINDER_DAYS` (6) - in `ops all` (which still runs
every step), at `main.py` startup and in `ops status`. `SIGN_IN_REMINDER_DAYS=0` turns it off
once the consent screen is published (#956). A token from before the stamp says nothing.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)


def _creds(token="t1"):
    return SimpleNamespace(token=token, refresh_token="r", token_uri="u", client_id="c",
                           client_secret="s", scopes=["a"])  # fmt: skip


class _TokenCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "token.json")
        for p in (
            patch("youtube.oauth.token_path_for_channel", return_value=self.path),
            patch("youtube.oauth._now", return_value=NOW),
        ):
            p.start()
            self.addCleanup(p.stop)

    def _stored(self):
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def _write(self, **payload):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"token": "t", "scopes": ["a"], **payload}, f)


class StampTests(_TokenCase):
    def test_a_fresh_sign_in_is_stamped(self):
        from youtube.oauth import save_credentials

        save_credentials(_creds(), "tapin", signed_in=True)
        self.assertEqual(self._stored()["signed_in_at"], NOW.isoformat())

    def test_a_refresh_keeps_the_stamp(self):
        from youtube.oauth import save_credentials

        self._write(signed_in_at="2026-10-01T09:00:00+00:00")
        save_credentials(_creds("t2"), "tapin")
        stored = self._stored()
        self.assertEqual(stored["signed_in_at"], "2026-10-01T09:00:00+00:00")
        self.assertEqual(stored["token"], "t2")

    def test_the_setup_flow_stamps_it(self):
        from youtube import oauth

        flow = SimpleNamespace(run_local_server=lambda port=0: _creds())
        with (
            patch.object(oauth, "_client_secrets_path", return_value=self.path),
            patch("google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file",
                  return_value=flow),
            redirect_stdout(io.StringIO()),
        ):  # fmt: skip
            self._write()
            oauth.run_interactive_oauth("tapin")
        self.assertEqual(self._stored()["signed_in_at"], NOW.isoformat())


class ReminderTests(_TokenCase):
    def _reminder(self, days_old=None, env=None):
        from youtube.oauth import sign_in_reminder

        if days_old is None:
            self._write()
        else:
            self._write(signed_in_at=(NOW - timedelta(days=days_old)).isoformat())
        with patch.dict(os.environ, env or {"SIGN_IN_REMINDER_DAYS": "6"}):
            return sign_in_reminder("tapin")

    def test_day_six_says_renew(self):
        line = self._reminder(6.2)
        self.assertIn("6 days old", line)
        self.assertIn("py -m youtube.oauth_setup --channel tapin", line)

    def test_a_young_sign_in_says_nothing(self):
        self.assertEqual(self._reminder(2), "")

    def test_no_stamp_says_nothing(self):
        self.assertEqual(self._reminder(None), "")

    def test_it_can_be_turned_off(self):
        self.assertEqual(self._reminder(6.5, {"SIGN_IN_REMINDER_DAYS": "0"}), "")


class BatchTests(unittest.TestCase):
    def test_ops_all_prints_it_and_still_runs_the_youtube_steps(self):
        from scripts import ops

        ran: list[str] = []

        def fake(name):
            def step(_args):
                ran.append(name)
                return 0

            return step

        commands = {name: (help_, fake(name)) for name, (help_, _fn) in ops.COMMANDS.items()}
        note = "YouTube sign-in for tapin is 6 days old - renew: py -m youtube.oauth_setup"
        buf = io.StringIO()
        with (
            patch.dict(ops.COMMANDS, commands),
            patch("youtube.oauth.sign_in_status", return_value=""),
            patch("youtube.oauth.sign_in_reminder", return_value=note),
            redirect_stdout(buf),
        ):
            code = ops._run_batch("all", Namespace(channel="tapin"))
        self.assertIn(note, buf.getvalue())
        self.assertIn("sync-metrics", ran)
        self.assertIn("backfill", ran)
        self.assertEqual(code, 0)

    def test_status_shows_it(self):
        from core.status_summary import machine_lines

        with (
            patch("youtube.oauth.sign_in_status", return_value=""),
            patch("youtube.oauth.sign_in_reminder", return_value="6 days old - renew"),
        ):
            lines = machine_lines("tapin")
        self.assertTrue(any(line.startswith("Sign-in") and "6 days old" in line for line in lines))


if __name__ == "__main__":
    unittest.main()
