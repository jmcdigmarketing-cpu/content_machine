"""Tests for youtube/oauth.py — the last sequenced item on the render/publish
coverage wave.

token_has_scope gates the duplicate-upload check; a broken token is a silent
missed publish. Round-trip load/save against a TEMP file only — never
config/secrets/. run_interactive_oauth is skipped (needs a browser).
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from youtube import oauth
from youtube.constants import (
    OAUTH_SCOPES_FULL,
    OAUTH_SCOPES_UPLOAD,
    SCOPE_YOUTUBE_UPLOAD,
    SCOPE_YT_ANALYTICS_READONLY,
)


def _profile(token_path: str):
    return SimpleNamespace(youtube_oauth_token_file=token_path)


class TestOauthScopes(unittest.TestCase):
    def test_full_includes_upload_read_and_analytics(self):
        scopes = oauth.oauth_scopes(include_analytics=True)
        self.assertEqual(scopes, list(OAUTH_SCOPES_FULL))
        self.assertIn(SCOPE_YOUTUBE_UPLOAD, scopes)
        self.assertIn(SCOPE_YT_ANALYTICS_READONLY, scopes)

    def test_upload_only_drops_analytics(self):
        scopes = oauth.oauth_scopes(include_analytics=False)
        self.assertEqual(scopes, list(OAUTH_SCOPES_UPLOAD))
        self.assertNotIn(SCOPE_YT_ANALYTICS_READONLY, scopes)


class TestTokenPathForChannel(unittest.TestCase):
    def test_profile_path_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "token.json")
            with (
                patch("youtube.oauth.resolve_channel_id", return_value="tapin"),
                patch("youtube.oauth.get_channel_profile", return_value=_profile(path)),
            ):
                self.assertEqual(oauth.token_path_for_channel("tapin"), path)

    def test_env_used_when_profile_has_no_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "from-env.json")
            with (
                patch("youtube.oauth.resolve_channel_id", return_value="tapin"),
                patch("youtube.oauth.get_channel_profile", return_value=_profile("")),
                patch.dict(os.environ, {"YOUTUBE_OAUTH_TOKEN_FILE": path}, clear=False),
            ):
                self.assertEqual(oauth.token_path_for_channel("tapin"), path)

    def test_never_returns_a_secrets_path_when_profile_is_temp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "token.json")
            with (
                patch("youtube.oauth.resolve_channel_id", return_value="tapin"),
                patch("youtube.oauth.get_channel_profile", return_value=_profile(path)),
            ):
                got = oauth.token_path_for_channel("tapin")
        self.assertNotIn("config/secrets", got.replace("\\", "/"))
        self.assertEqual(got, path)


class TestTokenHasScope(unittest.TestCase):
    def test_missing_file_is_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "missing.json")
            with patch.object(oauth, "token_path_for_channel", return_value=path):
                self.assertFalse(oauth.token_has_scope("tapin", SCOPE_YOUTUBE_UPLOAD))

    def test_scope_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "token.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"scopes": [SCOPE_YOUTUBE_UPLOAD, SCOPE_YT_ANALYTICS_READONLY]}, f)
            with patch.object(oauth, "token_path_for_channel", return_value=path):
                self.assertTrue(oauth.token_has_scope("tapin", SCOPE_YOUTUBE_UPLOAD))
                self.assertTrue(oauth.token_has_scope("tapin", SCOPE_YT_ANALYTICS_READONLY))

    def test_scope_absent_is_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "token.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"scopes": [SCOPE_YOUTUBE_UPLOAD]}, f)
            with patch.object(oauth, "token_path_for_channel", return_value=path):
                self.assertFalse(oauth.token_has_scope("tapin", SCOPE_YT_ANALYTICS_READONLY))


class _FakeCreds:
    def __init__(self, **kw):
        self.token = kw.get("token", "ya29.test")
        self.refresh_token = kw.get("refresh_token", "1//test")
        self.token_uri = kw.get("token_uri", "https://oauth2.googleapis.com/token")
        self.client_id = kw.get("client_id", "cid")
        self.client_secret = kw.get("client_secret", "csecret")
        self.scopes = list(kw.get("scopes") or oauth.oauth_scopes())
        self.expired = False
        self.valid = True

    def refresh(self, _request):
        raise AssertionError("refresh must not hit the network in tests")


class TestLoadSaveRoundTrip(unittest.TestCase):
    def test_save_then_load_against_temp_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "token.json")
            creds = _FakeCreds(token="ya29.roundtrip", scopes=list(OAUTH_SCOPES_FULL))
            with patch.object(oauth, "token_path_for_channel", return_value=path):
                saved = oauth.save_credentials(creds, "tapin")
                self.assertEqual(saved, path)
                self.assertTrue(os.path.isfile(path))
                self.assertNotIn("config/secrets", path.replace("\\", "/"))

                with open(path, encoding="utf-8") as fh:
                    payload = json.loads(fh.read())
                self.assertEqual(payload["token"], "ya29.roundtrip")
                self.assertEqual(payload["scopes"], list(OAUTH_SCOPES_FULL))

                loaded = _FakeCreds(**payload)
                loaded.expired = False
                loaded.valid = True
                with patch.object(
                    oauth.Credentials, "from_authorized_user_file", return_value=loaded
                ):
                    got = oauth.load_credentials("tapin")
            self.assertIsNotNone(got)
            self.assertEqual(got.token, "ya29.roundtrip")
            self.assertEqual(list(got.scopes), list(OAUTH_SCOPES_FULL))

    def test_load_missing_file_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "nope.json")
            with patch.object(oauth, "token_path_for_channel", return_value=path):
                self.assertIsNone(oauth.load_credentials("tapin"))

    def test_expired_refresh_failure_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "token.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"token": "x", "scopes": list(OAUTH_SCOPES_FULL)}, f)
            expired = _FakeCreds()
            expired.expired = True
            expired.valid = False

            def _boom(_request):
                raise RuntimeError("network")

            expired.refresh = _boom
            with (
                patch.dict(os.environ, {"CONTENT_FORBID_LIVE_YOUTUBE": ""}, clear=False),
                patch.object(oauth, "token_path_for_channel", return_value=path),
                patch.object(oauth.Credentials, "from_authorized_user_file", return_value=expired),
            ):
                self.assertIsNone(oauth.load_credentials("tapin"))

    def test_forbid_live_skips_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "token.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"token": "x", "scopes": list(OAUTH_SCOPES_FULL)}, f)
            expired = _FakeCreds()
            expired.expired = True
            expired.valid = False

            def _must_not_refresh(_request):
                raise AssertionError("refresh must not hit the network")

            expired.refresh = _must_not_refresh
            with (
                patch.dict(os.environ, {"CONTENT_FORBID_LIVE_YOUTUBE": "1"}, clear=False),
                patch.object(oauth, "token_path_for_channel", return_value=path),
                patch.object(oauth.Credentials, "from_authorized_user_file", return_value=expired),
            ):
                self.assertIsNone(oauth.load_credentials("tapin"))


if __name__ == "__main__":
    unittest.main()
