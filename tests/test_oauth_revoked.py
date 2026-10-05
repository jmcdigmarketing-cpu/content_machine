"""#961: a revoked YouTube sign-in fails once, says how to fix it, and stops the backfill
(operator, 2026-10-05).

`py -m scripts.ops backfill view-curve --apply --channel tapin` printed
`[ERROR] OAuth refresh failed: ('invalid_grant: Token has been expired or revoked.' ...)` once per
video - 36 times - until the operator pressed Ctrl+C. `load_credentials` asked Google to refresh
the dead token on every call, logged the raw error with no remedy, and the backfill went on to
the next video. Google answers `invalid_grant` for good (a token in a consent screen's Testing
status expires after 7 days; a revoked one never comes back), so one answer is enough until the
token file changes.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from google.auth.exceptions import RefreshError, TransportError

REVOKED = RefreshError(
    "invalid_grant: Token has been expired or revoked.",
    {"error": "invalid_grant", "error_description": "Token has been expired or revoked."},
)


def _expired_creds(refresh_error: Exception) -> MagicMock:
    creds = MagicMock()
    creds.expired = True
    creds.valid = False
    creds.refresh_token = "refresh"
    creds.refresh.side_effect = refresh_error
    return creds


class _SignInCase(unittest.TestCase):
    def setUp(self):
        from youtube import oauth

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.token = os.path.join(self.tmp.name, "token_tapin.json")
        with open(self.token, "w", encoding="utf-8") as f:
            json.dump({"scopes": ["s"]}, f)
        getattr(oauth, "_SIGN_IN_PROBLEMS", {}).clear()
        env = {k: v for k, v in os.environ.items() if k != "CONTENT_FORBID_LIVE_YOUTUBE"}
        env["YOUTUBE_ANALYTICS_SYNC"] = "true"
        for p in (
            patch.dict(os.environ, env, clear=True),
            patch("youtube.oauth.token_path_for_channel", return_value=self.token),
            patch("youtube.oauth.resolve_channel_id", side_effect=lambda c=None: c or "tapin"),
        ):
            p.start()
            self.addCleanup(p.stop)

    def _creds(self, error: Exception) -> MagicMock:
        creds = _expired_creds(error)
        p = patch("youtube.oauth.Credentials.from_authorized_user_file", return_value=creds)
        p.start()
        self.addCleanup(p.stop)
        return creds


class LoadCredentialsTests(_SignInCase):
    def test_a_revoked_token_is_refreshed_once_and_logged_once(self):
        from youtube import oauth

        creds = self._creds(REVOKED)
        with self.assertLogs("content_machine.youtube.oauth", level="ERROR") as logs:
            for _ in range(5):
                self.assertIsNone(oauth.load_credentials("tapin"))
        self.assertEqual(creds.refresh.call_count, 1)
        self.assertEqual(len(logs.output), 1)
        self.assertIn("py -m youtube.oauth_setup --channel tapin", logs.output[0])

    def test_the_problem_names_the_fix_and_the_weekly_expiry(self):
        from youtube import oauth

        self._creds(REVOKED)
        with self.assertLogs("content_machine.youtube.oauth", level="ERROR"):
            oauth.load_credentials("tapin")
        problem = oauth.sign_in_problem("tapin")
        self.assertIn("py -m youtube.oauth_setup --channel tapin", problem)
        self.assertIn("Testing", problem)

    def test_a_new_token_file_is_tried_again(self):
        from youtube import oauth

        creds = self._creds(REVOKED)
        with self.assertLogs("content_machine.youtube.oauth", level="ERROR"):
            oauth.load_credentials("tapin")
        st = os.stat(self.token)
        os.utime(self.token, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
        with self.assertLogs("content_machine.youtube.oauth", level="ERROR"):
            oauth.load_credentials("tapin")
        self.assertEqual(creds.refresh.call_count, 2)

    def test_a_network_failure_is_not_remembered(self):
        from youtube import oauth

        creds = self._creds(TransportError("connection reset"))
        with self.assertLogs("content_machine.youtube.oauth", level="ERROR"):
            oauth.load_credentials("tapin")
            oauth.load_credentials("tapin")
        self.assertEqual(creds.refresh.call_count, 2)
        self.assertEqual(oauth.sign_in_problem("tapin"), "")


def _rows(n: int):
    published = datetime(2026, 9, 1, 18, tzinfo=timezone.utc)
    return [
        SimpleNamespace(id=i, youtube_video_id=f"v{i}", published_at=published, metrics_json="{}")
        for i in range(n)
    ]


class BackfillTests(_SignInCase):
    def _repo(self):
        repo = MagicMock()
        repo.list_timed_outcomes.return_value = _rows(36)
        p = patch("storage.repositories.publish_log.get_publish_log_repository", return_value=repo)
        p.start()
        self.addCleanup(p.stop)
        return repo

    def test_the_backfill_stops_at_the_first_sign_in_failure(self):
        from analytics.view_curve import backfill

        creds = self._creds(REVOKED)
        repo = self._repo()
        with self.assertLogs("content_machine.youtube.oauth", level="ERROR") as logs:
            tally = backfill("tapin", apply=True, force=True)
        self.assertEqual(creds.refresh.call_count, 1)
        self.assertEqual(len(logs.output), 1)
        self.assertEqual(tally["updated"], 0)
        repo.update.assert_not_called()

    def test_ops_backfill_prints_the_fix_and_fails(self):
        from scripts.ops import cmd_backfill

        self._creds(REVOKED)
        self._repo()
        buf = io.StringIO()
        with self.assertLogs("content_machine.youtube.oauth", level="ERROR"), redirect_stdout(buf):
            code = cmd_backfill(
                Namespace(channel="tapin", target="view-curve", apply=True, force=True)
            )
        self.assertNotEqual(code, 0)
        self.assertIn("py -m youtube.oauth_setup --channel tapin", buf.getvalue())


class CheckSetupTests(_SignInCase):
    def test_check_setup_says_the_sign_in_expired(self):
        from youtube.check_setup import check_channel_setup

        self._creds(REVOKED)
        with (
            patch("youtube.check_setup.token_path_for_channel", return_value=self.token),
            self.assertLogs("content_machine.youtube.oauth", level="ERROR"),
        ):
            report = check_channel_setup("tapin")
        text = " ".join(report.issues + report.hints)
        self.assertIn("expired or been revoked", text)


if __name__ == "__main__":
    unittest.main()
