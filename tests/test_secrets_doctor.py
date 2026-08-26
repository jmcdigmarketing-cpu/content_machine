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


if __name__ == "__main__":
    unittest.main()
