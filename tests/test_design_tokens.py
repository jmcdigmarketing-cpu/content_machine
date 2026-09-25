"""#170 design tokens: one JSON drives ANSI themes and at least one video consumer."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from config.paths import ROOT_DIR


class TestDesignTokens(unittest.TestCase):
    def test_shipped_json_has_roles_and_both_channel_accents(self):
        from core.design_tokens import TOKENS_PATH, load_tokens

        self.assertEqual(TOKENS_PATH, Path(ROOT_DIR) / "config" / "design_tokens.json")
        tokens = load_tokens()
        self.assertEqual(tokens["channels"]["tapin"]["caption_fill"], "#FFFFFF")
        self.assertEqual(tokens["channels"]["moneywise"]["caption_fill"], "#F7E7A9")
        self.assertIn("accent", tokens["roles"])
        self.assertIn("primary", tokens["roles"])

    def test_caption_fill_and_tokens_agree_on_shipped_channels(self):
        from core.caption_contrast import fill_hex_for_channel
        from core.design_tokens import caption_fill_hex, load_tokens

        tokens = load_tokens()
        for channel in ("tapin", "moneywise"):
            token_hex = caption_fill_hex(channel)
            overlay_hex = fill_hex_for_channel(channel)
            self.assertEqual(token_hex, overlay_hex)
            self.assertEqual(token_hex, tokens["channels"][channel]["caption_fill"])

    def test_themes_role_color_uses_token_ansi_for_default(self):
        from unittest.mock import patch

        from core import themes
        from core.design_tokens import load_tokens

        tokens = load_tokens()
        ansi256 = int(tokens["roles"]["accent"]["ansi256"])
        with patch.dict(
            "os.environ",
            {"CONTENT_UI_THEME": "default", "CONTENT_UI_COLOR_DEPTH": "256"},
        ):
            self.assertIn(f"38;5;{ansi256}m", themes.role_color("accent"))

    def test_json_is_valid_object(self):
        path = Path(ROOT_DIR) / "config" / "design_tokens.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsInstance(data, dict)
        self.assertIn("type", data)
        self.assertIn("spacing", data)
