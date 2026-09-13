"""TTS character cap — refuse Extended-scale scripts before paying."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core.tts_char_cap import max_chars, tts_char_cap_reason


class TestTtsCharCap(unittest.TestCase):
    def test_short_script_passes(self):
        self.assertIsNone(tts_char_cap_reason("word " * 50))

    def test_over_default_ceiling_refuses(self):
        # 15% grace: 5,001 is warn-only; hard stop is 5,751 at the default 5,000.
        reason = tts_char_cap_reason("x" * 5751)
        self.assertIsNotNone(reason)
        self.assertIn("5751", reason.replace(",", ""))

    def test_off_disables(self):
        with patch.dict(os.environ, {"TTS_MAX_CHARS": "off"}, clear=False):
            self.assertIsNone(max_chars())
            self.assertIsNone(tts_char_cap_reason("x" * 20000))

    def test_zero_disables(self):
        with patch.dict(os.environ, {"TTS_MAX_CHARS": "0"}, clear=False):
            self.assertIsNone(max_chars())

    def test_custom_ceiling(self):
        with patch.dict(os.environ, {"TTS_MAX_CHARS": "100"}, clear=False):
            self.assertIsNone(tts_char_cap_reason("a" * 100))
            self.assertIsNone(tts_char_cap_reason("a" * 101))  # inside 15% grace
            self.assertIsNotNone(tts_char_cap_reason("a" * 116))


if __name__ == "__main__":
    unittest.main()
