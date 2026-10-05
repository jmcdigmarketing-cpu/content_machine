import os
import unittest
from unittest.mock import patch

from youtube.check_setup import check_channel_setup


class TestCheckSetup(unittest.TestCase):
    def setUp(self):
        # The isfile patch is os.path.isfile itself: channel profiles first loaded under it
        # cache "default" only, and later tests resolve every channel to it (#961).
        from config.channels import get_channel_profiles

        get_channel_profiles.cache_clear()
        self.addCleanup(get_channel_profiles.cache_clear)

    @patch.dict(os.environ, {"YOUTUBE_UPLOAD_ENABLED": "true"}, clear=False)
    @patch("youtube.check_setup.os.path.isfile", return_value=False)
    def test_missing_secrets_and_token(self, _isfile):
        report = check_channel_setup("tapin")
        self.assertFalse(report.ok)
        self.assertTrue(any("secrets" in i.lower() or "token" in i.lower() for i in report.issues))


if __name__ == "__main__":
    unittest.main()
