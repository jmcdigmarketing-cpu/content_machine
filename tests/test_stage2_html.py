"""#295 contact sheet, #296 print CSS, #172 HTML tokens, #247 grain, #635 redaction.

Fail-then-fix: unmodified Stage 1 has no contact_sheet module and HTML CSS is a
hardcoded block, not generated from config/design_tokens.json.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from core.design_tokens import channel_tokens, load_tokens
from core.html_report import themed_page


class TestContactSheet(unittest.TestCase):
    def test_two_by_two_collage_of_the_newest_thumbs(self):
        from core.contact_sheet import render_contact_sheet

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "thumbs"
            folder.mkdir()
            colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
            for i, color in enumerate(colors):
                Image.new("RGB", (64, 64), color).save(folder / f"{i}.png")
            dest = Path(tmp) / "sheet.png"
            result = render_contact_sheet(str(dest), thumbs_dir=str(folder), channel_id="tapin")
            self.assertTrue(Path(result.path).is_file())
            with Image.open(result.path) as image:
                self.assertEqual(image.size[0], image.size[1])
                self.assertGreaterEqual(image.size[0], 128)
            self.assertEqual(len(result.paths), 4)

    def test_empty_folder_is_an_honest_empty_not_a_crash(self):
        from core.contact_sheet import render_contact_sheet

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "sheet.png"
            result = render_contact_sheet(
                str(dest), thumbs_dir=str(Path(tmp) / "missing"), channel_id="tapin"
            )
        self.assertFalse(result.ok)
        self.assertIn("no thumbnail", result.detail.lower())
        self.assertFalse(Path(dest).exists())

    def test_print_page_uses_token_type_and_hides_chrome(self):
        from core.contact_sheet import contact_sheet_html

        tokens = load_tokens()
        html = contact_sheet_html("sheet.png", channel_id="tapin")
        self.assertIn("@media print", html)
        self.assertIn(f"{int(tokens['type']['body'])}px", html)
        self.assertIn("sheet.png", html)
        self.assertIn("display: none", html.lower().replace("!important", ""))


class TestHtmlDesignSystem(unittest.TestCase):
    def test_themed_css_is_generated_from_shipped_tokens(self):
        from core.chrome import themed_css

        tokens = load_tokens()
        css = themed_css("tapin")
        self.assertIn(str(tokens["roles"]["error"]["hex"]), css)
        self.assertIn(str(channel_tokens("tapin")["header_border"]), css)
        self.assertIn(f"{int(tokens['type']['body'])}px", css)
        money = themed_css("moneywise")
        self.assertIn(str(channel_tokens("moneywise")["header_border"]), money)
        self.assertNotEqual(css, money)

    def test_html_dump_uses_generated_css_not_a_second_palette(self):
        page = themed_page("Booth", "<p>x</p>", channel_id="tapin")
        tokens = load_tokens()
        self.assertIn("design_tokens.json", page)
        self.assertIn(str(tokens["roles"]["success"]["hex"]).lower(), page.lower())
        self.assertIn(str(channel_tokens("tapin")["end_card_bg"]).lower(), page.lower())

    def test_grain_vignette_preview_class_is_token_driven(self):
        from core.chrome import themed_css

        css = themed_css("tapin", grain=True, vignette=True)
        self.assertIn("grain", css.lower())
        self.assertIn("vignette", css.lower())
        off = themed_css("tapin", grain=False, vignette=False)
        self.assertNotIn("noise", off.lower())

    def test_vault_path_and_username_are_redacted_in_html(self):
        from core.chrome import redact_operator_paths

        vault = r"C:\Users\jonma\Documents\Obsidian\TapIn"
        with patch.dict(os.environ, {"OBSIDIAN_VAULT_PATH": vault, "USERNAME": "jonma"}):
            cleaned = redact_operator_paths(f"Wrote {vault}\\_runs\\71.md for jonma on this PC")
        self.assertNotIn("jonma", cleaned.lower())
        self.assertNotIn("obsidian", cleaned.lower())
        self.assertIn("[vault]", cleaned.lower())
        page = themed_page("Dump", f"<pre>{vault}</pre>", channel_id="tapin")
        self.assertNotIn("jonma", page.lower())
