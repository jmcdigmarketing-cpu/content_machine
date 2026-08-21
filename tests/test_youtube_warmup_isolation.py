"""C9 — suite must not open a live Google HTTPS socket (warmup / discovery doc)."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from apis.youtube_api import start_youtube_warmup_background, warmup_youtube_client


class TestYoutubeWarmupIsolation(unittest.TestCase):
    def test_warmup_is_noop_when_skip_env_set(self):
        env = {
            "CONTENT_SKIP_YOUTUBE_WARMUP": "1",
            "CONTENT_FORBID_LIVE_YOUTUBE": "1",
            "YOUTUBE_API_KEY": "not-a-real-key",
        }
        with (
            patch.dict(os.environ, env, clear=False),
            patch("apis.youtube_api._get_youtube_client") as build,
            patch("apis.youtube_api.threading.Thread") as thread,
        ):
            start_youtube_warmup_background()
            warmup_youtube_client()
        build.assert_not_called()
        thread.assert_not_called()

    def test_live_client_raises_in_suite(self):
        from apis import youtube_api as ya

        ya._youtube_client = None
        env = {"CONTENT_FORBID_LIVE_YOUTUBE": "1", "YOUTUBE_API_KEY": "k"}
        with patch.dict(os.environ, env, clear=False):
            with self.assertRaises(RuntimeError):
                ya._get_youtube_client()
        ya._youtube_client = None

    def test_oauth_builders_do_not_load_credentials(self):
        from youtube import oauth

        env = {"CONTENT_FORBID_LIVE_YOUTUBE": "1"}
        with (
            patch.dict(os.environ, env, clear=False),
            patch.object(oauth, "load_credentials") as load,
        ):
            self.assertIsNone(oauth.get_youtube_service("tapin"))
            self.assertIsNone(oauth.get_youtube_analytics_service("tapin"))
        load.assert_not_called()


if __name__ == "__main__":
    unittest.main()
