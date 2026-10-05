"""#971: `ops all` checks the YouTube sign-in first (operator, 2026-10-05: "let's ensure the
script ops all is including that").

`ops all` (all-checks + all-analytics + all-review) never ran `check-youtube` - only
`all-setup` did - so when Google refused the tapin sign-in every YouTube-backed step failed
on its own, and the operator saw "most of those were failing". Now the batch asks once:
a missing, refused or analytics-less sign-in prints one line with the command that fixes it,
the steps that need it (sync-metrics, backfill) are skipped and named, and the rest still run.
`ops status` carries the same line.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from unittest.mock import patch

ANALYTICS = "https://www.googleapis.com/auth/yt-analytics.readonly"


class StatusTests(unittest.TestCase):
    def _status(self, scopes, *, exists=True, creds=object(), problem=""):
        from youtube.oauth import sign_in_status

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "token.json")
            if exists:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"scopes": scopes}, f)
            with (
                patch("youtube.oauth.token_path_for_channel", return_value=path),
                patch("youtube.oauth.load_credentials", return_value=creds),
                patch("youtube.oauth.sign_in_problem", return_value=problem),
            ):
                return sign_in_status("tapin")

    def test_a_good_sign_in_says_nothing(self):
        self.assertEqual(self._status([ANALYTICS]), "")

    def test_no_token_file(self):
        line = self._status([], exists=False)
        self.assertIn("py -m youtube.oauth_setup --channel tapin", line)

    def test_no_analytics_permission(self):
        line = self._status(["https://www.googleapis.com/auth/youtube.upload"])
        self.assertIn("analytics", line)
        self.assertIn("py -m youtube.oauth_setup --channel tapin", line)

    def test_a_refused_sign_in_says_why(self):
        line = self._status(
            [ANALYTICS], creds=None, problem="YouTube sign-in for tapin has expired"
        )
        self.assertIn("expired", line)


class AllBatchTests(unittest.TestCase):
    def _run(self, problem):
        from scripts import ops

        ran: list[str] = []

        def fake(name):
            def step(_args):
                ran.append(name)
                return 0

            return step

        commands = {name: (help_, fake(name)) for name, (help_, _fn) in ops.COMMANDS.items()}
        buf = io.StringIO()
        with (
            patch.dict(ops.COMMANDS, commands),
            patch("youtube.oauth.sign_in_status", return_value=problem),
            redirect_stdout(buf),
        ):
            code = ops._run_batch("all", Namespace(channel="tapin"))
        return code, ran, buf.getvalue()

    def test_a_dead_sign_in_skips_the_youtube_steps_and_says_how_to_fix_it(self):
        fix = (
            "YouTube sign-in for tapin has expired - run: py -m youtube.oauth_setup --channel tapin"
        )
        code, ran, out = self._run(fix)
        self.assertNotIn("sync-metrics", ran)
        self.assertNotIn("backfill", ran)
        self.assertIn("scoreboard", ran)
        self.assertIn("test", ran)
        self.assertEqual(out.count("py -m youtube.oauth_setup --channel tapin"), 2)  # top + end
        self.assertIn("skipped", out)
        self.assertNotEqual(code, 0)

    def test_a_good_sign_in_runs_everything(self):
        code, ran, _out = self._run("")
        self.assertIn("sync-metrics", ran)
        self.assertIn("backfill", ran)
        self.assertEqual(code, 0)


class MachineStatusTests(unittest.TestCase):
    def test_status_has_a_sign_in_line(self):
        from core.status_summary import machine_lines

        with patch("youtube.oauth.sign_in_status", return_value=""):
            lines = machine_lines("tapin")
        self.assertTrue(any(line.startswith("Sign-in") for line in lines))


if __name__ == "__main__":
    unittest.main()
