"""#930: the suite read the operator's real keys, so it failed only on the operator's PC.

On the PC, `config/settings._load_dotenv` loaded `.env`, so `APIFY_CONTENT_MACHINE_KEY`
and `BALLDONTLIE_API_KEY` were set and seven tests reached `api.apify.com` /
`api.balldontlie.io` - failures CI (no keys) can never show. The suite now skips the
project `.env` (`CONTENT_SKIP_DOTENV`) and blanks secret-shaped variables already in the
process environment, so a test sees what CI sees.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class DotenvTests(unittest.TestCase):
    def test_the_suite_does_not_load_the_project_env(self):
        from config import settings

        self.assertEqual(os.environ.get("CONTENT_SKIP_DOTENV"), "1")
        with patch("os.path.isfile", return_value=True), patch("dotenv.load_dotenv") as load:
            settings._load_dotenv()
        load.assert_not_called()

    def test_outside_the_suite_it_still_loads(self):
        from config import settings

        with (
            patch.dict(os.environ, {"CONTENT_SKIP_DOTENV": ""}),
            patch("os.path.isfile", return_value=True),
            patch("dotenv.load_dotenv") as load,
        ):
            settings._load_dotenv()
        load.assert_called_once()


class SecretBlankingTests(unittest.TestCase):
    def test_secret_shaped_names_are_blanked(self):
        from tests import blank_secrets

        env = {"APIFY_CONTENT_MACHINE_KEY": "k", "YOUTUBE_API_KEY": "k", "REDDIT_CLIENT_SECRET": "s",
               "GH_TOKEN": "t", "PATH": "/bin", "TTS_PROVIDER": "elevenlabs"}  # fmt: skip
        blank_secrets(env)
        self.assertEqual(
            env,
            {"APIFY_CONTENT_MACHINE_KEY": "", "YOUTUBE_API_KEY": "", "REDDIT_CLIENT_SECRET": "",
             "GH_TOKEN": "", "PATH": "/bin", "TTS_PROVIDER": "elevenlabs"},
        )  # fmt: skip

    def test_a_key_in_the_environment_reaches_no_network(self):
        """The operator's PC, reproduced: a real-looking Apify key in the environment."""
        env = dict(os.environ, APIFY_CONTENT_MACHINE_KEY="fake-key", BALLDONTLIE_API_KEY="fake")
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "tests.test_discovery_progress",
                "tests.test_stats_context",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=240,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-1500:])
        self.assertNotIn("#921", proc.stderr)


if __name__ == "__main__":
    unittest.main()
