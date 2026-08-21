"""channel-go-live checklist — never reads config/secrets/ token contents."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.channel_go_live import inspect_channel, render_report


class TestChannelGoLive(unittest.TestCase):
    def _oauth(self, ok=True):
        return SimpleNamespace(ok=ok, issues=[] if ok else ["missing token"])

    def test_moneywise_has_seo_feeds_brand_kit_fails_persona(self):
        with patch("youtube.check_setup.check_channel_setup", return_value=self._oauth(True)):
            report = inspect_channel("moneywise")
        names = {c.name: c for c in report.checks}
        self.assertTrue(names["seo"].ok)
        self.assertTrue(names["feeds"].ok)
        self.assertTrue(names["brand_kit"].ok)
        self.assertFalse(names["persona"].ok)
        self.assertFalse(report.ok)
        blob = render_report(report)
        self.assertIn("NOT READY", blob)
        self.assertIn("persona", blob)

    def test_tapin_has_persona_and_seo(self):
        with patch("youtube.check_setup.check_channel_setup", return_value=self._oauth(True)):
            report = inspect_channel("tapin")
        names = {c.name: c for c in report.checks}
        self.assertTrue(names["persona"].ok)
        self.assertTrue(names["seo"].ok)
        self.assertTrue(names["feeds"].ok)
        self.assertIn("handle", names)
        self.assertIn("trailer", names)
        self.assertIn("banner", names)

    def test_moneywise_banner_present_handle_trailer_fail(self):
        with patch("youtube.check_setup.check_channel_setup", return_value=self._oauth(True)):
            report = inspect_channel("moneywise")
        names = {c.name: c for c in report.checks}
        self.assertTrue(names["banner"].ok)
        self.assertFalse(names["handle"].ok)
        self.assertFalse(names["trailer"].ok)

    def test_oauth_failure_is_a_fail_line(self):
        with patch("youtube.check_setup.check_channel_setup", return_value=self._oauth(False)):
            report = inspect_channel("tapin")
        oauth = next(c for c in report.checks if c.name == "oauth")
        self.assertFalse(oauth.ok)

    def test_ops_command_registered(self):
        from scripts import ops

        self.assertIn("channel-go-live", ops.COMMANDS)


if __name__ == "__main__":
    unittest.main()
