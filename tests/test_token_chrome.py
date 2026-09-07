"""#303 booth chrome from tokens, #304 reduced chroma, #486 colour-blind palette."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core import html_report, themes
from core.design_tokens import header_border_hex


class TestBoothChannelChrome(unittest.TestCase):
    def test_moneywise_header_uses_token_green_not_tapin_red(self):
        tapin_border = header_border_hex("tapin").lower()
        money_border = header_border_hex("moneywise").lower()
        self.assertNotEqual(tapin_border, money_border)
        tapin = html_report.themed_page("Booth", "<p>x</p>", channel_id="tapin")
        money = html_report.themed_page("Booth", "<p>x</p>", channel_id="moneywise")
        self.assertIn(f"--header-border:{tapin_border}", tapin.lower())
        self.assertIn(f"--header-border:{money_border}", money.lower())
        self.assertNotIn(f"--header-border:{tapin_border}", money.lower())
        self.assertIn("swatch", money.lower())
        money_bg = "#1b2430"
        self.assertIn(money_bg, money.lower())


class TestReducedChroma(unittest.TestCase):
    def test_flag_adds_desaturated_body_class(self):
        with patch.dict(os.environ, {"CONTENT_UI_REDUCED_CHROMA": "1"}, clear=False):
            on = html_report.themed_page("T", "<p>x</p>")
        with patch.dict(os.environ, {"CONTENT_UI_REDUCED_CHROMA": "0"}, clear=False):
            off = html_report.themed_page("T", "<p>x</p>")
        self.assertRegex(on, r"<body[^>]*reduced-chroma")
        self.assertIn("filter: saturate", on)
        self.assertNotRegex(off, r"<body[^>]*reduced-chroma")


class TestColourBlindPalette(unittest.TestCase):
    def test_deuteranopia_keeps_success_and_error_distinct(self):
        from core.design_tokens import load_tokens

        tokens = load_tokens()
        cb = tokens["colorblind_roles"]
        default_ok = int(tokens["roles"]["success"]["ansi256"])
        cb_ok = int(cb["success"]["ansi256"])
        cb_err = int(cb["error"]["ansi256"])
        self.assertNotEqual(cb_ok, default_ok)
        env = {
            "CONTENT_UI_THEME": "default",
            "CONTENT_UI_COLOR_DEPTH": "256",
            "CONTENT_UI_COLORBLIND": "1",
        }
        with patch.dict("os.environ", env, clear=False):
            ok = themes.role_color("success")
            err = themes.role_color("error")
        self.assertIn(f"38;5;{cb_ok}m", ok)
        self.assertIn(f"38;5;{cb_err}m", err)
        self.assertNotEqual(ok, err)

    def test_plain_stays_uncolored_when_colourblind(self):
        with patch.dict(
            "os.environ",
            {"CONTENT_UI_THEME": "plain", "CONTENT_UI_COLORBLIND": "1"},
            clear=False,
        ):
            self.assertEqual(themes.role_color("success"), "")
            self.assertEqual(themes.role_color("error"), "")
