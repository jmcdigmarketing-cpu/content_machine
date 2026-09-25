import unittest
from pathlib import Path
from unittest.mock import patch

from config.paths import LUFFY_ASCII_FILE
from core.ascii_art import (
    luffy_ascii_path,
    luffy_mascot_lines,
    merge_columns,
    merge_columns_right,
    startup_banner_lines,
    startup_panel_lines,
)


def _luffy_asset_available() -> bool:
    """The mascot art (core/data/luffy_ascii.txt) is gitignored and generated
    locally via scripts/update_luffy_art.py, so it is absent in CI / clean
    checkouts. Tests that assert on its contents skip when it isn't present."""
    luffy_mascot_lines.cache_clear()
    try:
        return len(luffy_mascot_lines()) >= 40
    finally:
        luffy_mascot_lines.cache_clear()


_LUFFY_AVAILABLE = _luffy_asset_available()
_LUFFY_SKIP_REASON = "luffy_ascii.txt is gitignored/generated and not present in this checkout"


class TestAsciiArt(unittest.TestCase):
    def test_luffy_path_is_bundled_data(self):
        self.assertEqual(luffy_ascii_path(), Path(LUFFY_ASCII_FILE))
        self.assertTrue(
            str(luffy_ascii_path()).replace("\\", "/").endswith("core/data/luffy_ascii.txt")
        )

    @unittest.skipUnless(_LUFFY_AVAILABLE, _LUFFY_SKIP_REASON)
    def test_luffy_art_loaded_preserves_content(self):
        luffy_mascot_lines.cache_clear()
        lines = luffy_mascot_lines()
        self.assertGreaterEqual(len(lines), 40)
        self.assertGreaterEqual(max(len(line) for line in lines), 40)
        self.assertLessEqual(max(len(line) for line in lines), 130)
        self.assertTrue(lines[0].startswith("\u2800"))
        self.assertIn("\u28c0", lines[0])

    def test_luffy_missing_file_returns_empty(self):
        luffy_mascot_lines.cache_clear()
        missing = Path(LUFFY_ASCII_FILE).with_name("no_such_luffy.txt")
        with patch("core.ascii_art.luffy_ascii_path", return_value=missing):
            self.assertEqual(luffy_mascot_lines(), ())
        luffy_mascot_lines.cache_clear()

    def test_merge_columns_aligns_left_block(self):
        merged = merge_columns(["ab", "longer"], ["1", "22"], gap=2)
        self.assertTrue(merged[0].startswith("ab"))
        self.assertTrue(merged[0].endswith("1"))
        self.assertTrue(merged[1].startswith("longer"))
        self.assertTrue(merged[1].endswith("22"))

    def test_merge_columns_right_flushes_to_edge(self):
        merged = merge_columns_right(["ab"], ["ZZ"], cols=20, gap=2)
        self.assertTrue(merged[0].endswith("ZZ"))
        self.assertTrue(merged[0].startswith("ab"))
        self.assertGreaterEqual(len(merged[0]), 18)

    def test_startup_panel_skips_mascot_when_terminal_too_narrow(self):
        import os

        os.environ["CONTENT_UI_ASCII"] = "true"
        os.environ["CONTENT_UI_MASCOT"] = "luffy"
        left = startup_banner_lines("tapin")
        with patch(
            "core.ascii_art.shutil.get_terminal_size", return_value=os.terminal_size((60, 40))
        ):
            panel = startup_panel_lines("tapin")
        self.assertEqual(len(panel), len(left))

    @unittest.skipUnless(_LUFFY_AVAILABLE, _LUFFY_SKIP_REASON)
    def test_startup_panel_includes_mascot_when_wide(self):
        import os

        luffy_mascot_lines.cache_clear()
        os.environ["CONTENT_UI_ASCII"] = "true"
        os.environ["CONTENT_UI_MASCOT"] = "luffy"
        left = startup_banner_lines("tapin")
        mascot = luffy_mascot_lines()
        mascot_w = max(len(line) for line in mascot)
        min_cols = 50 + mascot_w + 12
        with patch(
            "core.ascii_art.shutil.get_terminal_size",
            return_value=os.terminal_size((max(min_cols, 160), 60)),
        ):
            panel = startup_panel_lines("tapin")
        self.assertGreater(len(panel), len(left))
        self.assertTrue(any("CONTENT MACHINE" in line for line in panel))
        tagline_idx = next(i for i, line in enumerate(panel) if "TapIn Media" in line)
        self.assertEqual(panel[tagline_idx - 1], "")
        self.assertNotIn("\u2800", panel[tagline_idx])


class TestDailyMascotCollapse(unittest.TestCase):
    def test_second_startup_the_same_day_drops_the_mascot(self):
        """#482. The ~60-line panel is for the first look of the day, not every menu."""
        import os
        import tempfile
        from datetime import date
        from pathlib import Path

        mascot = ("MM", "NN")
        left = ["LOGO"]
        with tempfile.TemporaryDirectory() as tmp:
            stamp = str(Path(tmp) / "shown.txt")
            env = {
                "CONTENT_UI_ASCII": "true",
                "CONTENT_UI_MASCOT": "luffy",
                "CONTENT_UI_ART": "",
                "CONTENT_UI_MASCOT_STAMP": stamp,
            }
            with (
                patch.dict(os.environ, env, clear=False),
                patch("core.ascii_art.startup_banner_lines", return_value=left),
                patch("core.ascii_art._theme_mascot_lines", return_value=mascot),
                patch(
                    "core.ascii_art.shutil.get_terminal_size",
                    return_value=os.terminal_size((80, 24)),
                ),
            ):
                first = startup_panel_lines("tapin")
                Path(stamp).write_text(date.today().isoformat(), encoding="utf-8")
                second = startup_panel_lines("tapin")
            self.assertGreater(len(first), len(left))
            self.assertEqual(second, left)
            self.assertEqual(
                Path(stamp).read_text(encoding="utf-8").strip(), date.today().isoformat()
            )

    def test_art_env_forces_the_mascot_back(self):
        import os
        import tempfile
        from pathlib import Path

        mascot = ("MM", "NN", "OO")
        left = ["LOGO"]
        with tempfile.TemporaryDirectory() as tmp:
            stamp = str(Path(tmp) / "shown.txt")
            Path(stamp).write_text("2099-01-01", encoding="utf-8")
            env = {
                "CONTENT_UI_ASCII": "true",
                "CONTENT_UI_MASCOT": "luffy",
                "CONTENT_UI_ART": "1",
                "CONTENT_UI_MASCOT_STAMP": stamp,
            }
            with (
                patch.dict(os.environ, env, clear=False),
                patch("core.ascii_art.startup_banner_lines", return_value=left),
                patch("core.ascii_art._theme_mascot_lines", return_value=mascot),
                patch(
                    "core.ascii_art.shutil.get_terminal_size",
                    return_value=os.terminal_size((80, 24)),
                ),
            ):
                panel = startup_panel_lines("tapin")
            self.assertGreater(len(panel), len(left))


if __name__ == "__main__":
    unittest.main()
