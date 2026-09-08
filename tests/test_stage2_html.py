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

    def test_the_token_background_actually_wins_the_cascade(self):
        """The assertions above only prove the token hexes are *present*, and one
        of them (`roles.success` #81C995) already appears in the legacy `_CSS`
        block — so that test passes with `themed_css` deleted entirely.

        What matters is which declaration wins. `_CSS` redeclares `html, body`,
        `header`, `pre`, `table`, `.card` and `a` at equal specificity, so
        whichever is emitted *last* decides every visible colour. Measured before
        this fix: token `#0B0F14` at offset 311, legacy `#111318` at 1894 — the
        legacy palette won and every HTML dump still rendered the old colours,
        while `desktop_app.md` claimed dumps share the generated CSS.
        """
        page = themed_page("Booth", "<p>x</p>", channel_id="tapin")
        low = page.lower()
        token_bg = str(channel_tokens("tapin")["end_card_bg"]).lower()

        at_token = low.find(token_bg)
        at_legacy = low.find("#111318")
        self.assertNotEqual(at_token, -1, "token background is not in the page at all")
        if at_legacy != -1:
            self.assertGreater(
                at_token,
                at_legacy,
                "the legacy palette is emitted after the token CSS, so it wins the cascade",
            )

    def test_grain_vignette_preview_class_is_token_driven(self):
        from core.chrome import themed_css

        css = themed_css("tapin", grain=True, vignette=True)
        self.assertIn("grain", css.lower())
        self.assertIn("vignette", css.lower())
        off = themed_css("tapin", grain=False, vignette=False)
        self.assertNotIn("noise", off.lower())

    def test_vault_path_and_username_are_redacted_in_html(self):
        """Both halves must exercise the *vault* branch, on any machine.

        The `themed_page` half used to sit dedented outside the `patch.dict`
        block, so it ran with no `OBSIDIAN_VAULT_PATH` — and `tests/__init__.py`
        forces that empty suite-wide anyway. It passed here only because this
        developer's `Path.home()` is `C:\\Users\\jonma`, so the *home* rule
        removed the name the *vault* rule was supposed to. Simulated on
        ubuntu-latest (`home=/home/runner`), "jonma" survived into the page and
        the assertion failed — every CI job runs ubuntu.

        `Path.home` is now pinned away from the fixture so a pass cannot come
        from the home rule, and `[vault]` is asserted in the page so the vault
        branch is proven to have run rather than merely not-failed.
        """
        from core.chrome import redact_operator_paths

        vault = r"C:\Users\jonma\Documents\Obsidian\TapIn"
        env = {"OBSIDIAN_VAULT_PATH": vault, "USERNAME": "jonma", "USER": "jonma"}
        with (
            patch.dict(os.environ, env),
            patch.object(Path, "home", staticmethod(lambda: Path("/elsewhere/nobody"))),
        ):
            cleaned = redact_operator_paths(f"Wrote {vault}\\_runs\\71.md for jonma on this PC")
            page = themed_page("Dump", f"<pre>{vault}</pre>", channel_id="tapin")

        self.assertNotIn("jonma", cleaned.lower())
        self.assertNotIn("obsidian", cleaned.lower())
        self.assertIn("[vault]", cleaned.lower())
        self.assertNotIn("jonma", page.lower())
        self.assertIn("[vault]", page.lower(), "the page did not go through the vault redactor")
