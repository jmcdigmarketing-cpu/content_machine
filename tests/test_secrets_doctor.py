"""secrets-doctor — present/missing/placeholder, never echoes values."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from core.secrets_doctor import classify_secret, gather, render


class TestSecretsDoctor(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(classify_secret(""), "missing")
        self.assertEqual(classify_secret("changeme"), "placeholder")
        self.assertEqual(classify_secret("sk-live-abcdefghijklmnopqrstuvwxyz"), "present")

    def test_render_never_includes_values(self):
        secret = "sk-live-DO-NOT-PRINT-THIS-VALUE-123456"

        def fake_getenv(name, default=None):
            if name == "ELEVEN_API_KEY":
                return secret
            return "" if default is None else default

        with (
            patch("core.secrets_doctor.os.getenv", side_effect=fake_getenv),
            patch("core.secrets_doctor._oauth_files", return_value=[]),
        ):
            blob = render(gather("tapin"), channel_id="tapin")
        self.assertNotIn(secret, blob)
        self.assertIn("values never printed", blob)
        self.assertIn("ELEVEN_API_KEY", blob)

    def test_gather_counts_required_missing_separately(self):
        env = {
            "DEEPSEEK_API_KEY": "sk-deepseek-dummy-xx",
            "OPENROUTER_API_KEY": "sk-or-dummy-xxxxxx",
            "ELEVEN_API_KEY": "sk-eleven-dummy-xx",
            "APIFY_CONTENT_MACHINE_KEY": "apify-dummy-xxxx",
            "YOUTUBE_API_KEY": "yt-dummy-key-xxxx",
            "OPENAI_API_KEY": "",
            "ANTHROPIC_API_KEY": "",
            "BRAVE_SEARCH_API_KEY": "",
            "BFL_API_KEY": "",
            "NEWS_API_KEY": "",
        }
        with (
            patch.dict("os.environ", env, clear=False),
            patch("core.secrets_doctor._oauth_files", return_value=[]),
        ):
            data = gather("tapin")
        self.assertEqual(data["required_missing"], 0)
        self.assertGreaterEqual(data["missing"], 1)
        self.assertGreaterEqual(data["optional_missing"], 1)

    def test_brave_and_bfl_are_not_secrets_doctor_slots(self):
        """Unused Brave/BFL slots were optional-missing noise. APIs still exist; doctor must not list them."""
        env = {
            "DEEPSEEK_API_KEY": "sk-deepseek-dummy-xx",
            "OPENROUTER_API_KEY": "sk-or-dummy-xxxxxx",
            "ELEVEN_API_KEY": "sk-eleven-dummy-xx",
            "APIFY_CONTENT_MACHINE_KEY": "apify-dummy-xxxx",
            "YOUTUBE_API_KEY": "yt-dummy-key-xxxx",
            "OPENAI_API_KEY": "sk-openai-dummy-xx",
            "ANTHROPIC_API_KEY": "sk-ant-dummy-xxxxx",
            "NEWS_API_KEY": "news-dummy-key-xx",
            "BRAVE_SEARCH_API_KEY": "",
            "BFL_API_KEY": "",
        }
        with (
            patch.dict("os.environ", env, clear=False),
            patch("core.secrets_doctor._oauth_files", return_value=[]),
        ):
            data = gather("tapin")
            blob = render(data, channel_id="tapin")
        names = {row["name"] for row in data["keys"]}
        self.assertNotIn("BRAVE_SEARCH_API_KEY", names)
        self.assertNotIn("BFL_API_KEY", names)
        self.assertEqual(data["optional_missing"], 0)
        self.assertNotIn("BRAVE_SEARCH_API_KEY", blob)
        self.assertNotIn("BFL_API_KEY", blob)


if __name__ == "__main__":
    unittest.main()
