"""Coverage remainder: actually call registry helpers and is_upload_configured."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from publishing.registry import (
    enabled_publish_platforms,
    listed_publish_platforms,
    publishers_for_channel,
)
from youtube.upload import is_upload_configured


class TestPublishRegistryBehaviour(unittest.TestCase):
    def test_shipped_tapin_is_youtube_only(self):
        enabled = enabled_publish_platforms("tapin")
        self.assertEqual(enabled, ("youtube",))
        listed = listed_publish_platforms("tapin")
        self.assertEqual(listed, ("youtube",))

    def test_listed_but_unregistered_platform_is_not_enabled(self):
        profile = type(
            "P",
            (),
            {"publishers_enabled": ("youtube", "tiktok", "instagram")},
        )()
        with patch("publishing.registry.get_channel_profile", return_value=profile):
            listed = listed_publish_platforms("tapin")
            enabled = enabled_publish_platforms("tapin")
        self.assertIn("tiktok", listed)
        self.assertIn("instagram", listed)
        self.assertEqual(enabled, ("youtube",))
        self.assertNotIn("tiktok", enabled)

    def test_publishers_for_channel_requires_configuration(self):
        with patch("publishing.youtube_publisher.is_youtube_configured", return_value=False):
            pubs = publishers_for_channel("tapin")
        self.assertEqual(pubs, [])

    def test_is_upload_configured_requires_env_and_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            secrets = os.path.join(tmp, "secrets.json")
            token = os.path.join(tmp, "token.json")
            with open(secrets, "w", encoding="utf-8") as fh:
                fh.write("{}")
            with open(token, "w", encoding="utf-8") as fh:
                fh.write("{}")
            with (
                patch.dict(
                    os.environ,
                    {"YOUTUBE_UPLOAD_ENABLED": "true"},
                    clear=False,
                ),
                patch("publishing.youtube_publisher._client_secrets_path", return_value=secrets),
                patch("publishing.youtube_publisher.token_path_for_channel", return_value=token),
            ):
                self.assertTrue(is_upload_configured("tapin"))
            with (
                patch.dict(os.environ, {"YOUTUBE_UPLOAD_ENABLED": ""}, clear=False),
                patch("publishing.youtube_publisher._client_secrets_path", return_value=secrets),
                patch("publishing.youtube_publisher.token_path_for_channel", return_value=token),
            ):
                os.environ.pop("YOUTUBE_UPLOAD_ENABLED", None)
                self.assertFalse(is_upload_configured("tapin"))


if __name__ == "__main__":
    unittest.main()
