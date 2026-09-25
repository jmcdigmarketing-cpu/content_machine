"""#185 / #297. Caption fill vs sampled background — WCAG-ish ratio, plus the number."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image


def _frame(band_color: tuple[int, int, int], *, rest=(10, 10, 10)) -> Path:
    tmp = tempfile.mkdtemp()
    path = Path(tmp) / "frame.png"
    img = Image.new("RGB", (108, 192), rest)
    y0 = int(192 * 0.8)
    for y in range(y0, 192):
        for x in range(108):
            img.putpixel((x, y), band_color)
    img.save(path)
    return path


class TestCaptionContrast(unittest.TestCase):
    def test_white_on_black_band_passes_and_names_the_ratio(self):
        from core.caption_contrast import inspect_caption_band, render_check

        check = inspect_caption_band(_frame((5, 5, 5)), fill_hex="#FFFFFF")
        self.assertGreaterEqual(check.ratio, 4.5)
        self.assertTrue(check.passed)
        text = render_check(check)
        self.assertIn(f"{check.ratio:.1f}", text)
        self.assertIn("PASS", text)

    def test_white_on_light_band_fails(self):
        from core.caption_contrast import inspect_caption_band

        check = inspect_caption_band(_frame((240, 240, 240)), fill_hex="#FFFFFF")
        self.assertLess(check.ratio, 4.5)
        self.assertFalse(check.passed)

    def test_shipped_tapin_fill_is_white(self):
        """Auditor reads the live caption skin, not a fixture pallete."""
        from config.channels import get_channel_profile
        from core.caption_contrast import fill_hex_for_channel

        skin = get_channel_profile("tapin").caption_skin or {}
        self.assertEqual(str(skin.get("fill_color")), "#FFFFFF")
        self.assertEqual(fill_hex_for_channel("tapin"), "#FFFFFF")
