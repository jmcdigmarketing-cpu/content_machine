"""#244 WT profile, #239 print CSS, #243 wordmark, #187 end-card preview, #188 intro waveform.

Fail-then-fix: each test calls the real helper, not a mock of the unit under test.
"""

from __future__ import annotations

import json
import logging
import os
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from config.paths import ROOT_DIR


class TestWindowsTerminalProfile(unittest.TestCase):
    def test_snippet_parses_and_names_both_channels(self):
        path = Path(ROOT_DIR) / "config" / "windows-terminal" / "profiles.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        schemes = data.get("schemes") or []
        names = {str(s.get("name") or "") for s in schemes}
        self.assertTrue(any("TapIn" in n for n in names), names)
        self.assertTrue(any("MoneyWise" in n for n in names), names)
        tapin = next(s for s in schemes if "TapIn" in str(s.get("name")))
        money = next(s for s in schemes if "MoneyWise" in str(s.get("name")))
        self.assertEqual(tapin.get("background"), "#0B0F14")
        self.assertEqual(money.get("background"), "#1B2430")

    def test_startup_docs_point_at_the_snippet(self):
        docs = (Path(ROOT_DIR) / "docs" / "startup-powershell.md").read_text(encoding="utf-8")
        self.assertIn("windows-terminal/profiles.json", docs.replace("\\", "/"))


class TestWeeklyReportPrintCss(unittest.TestCase):
    def test_print_media_hides_header_and_keeps_body(self):
        from core import html_report

        page = html_report.themed_page("Weekly", html_report.pre_body("quota leftover"))
        self.assertIn("@media print", page)
        print_block = page.split("@media print", 1)[1]
        self.assertIn("display: none", print_block)
        self.assertIn("header", print_block)
        self.assertIn("pre {", page)
        self.assertIn("position: sticky", page)
        self.assertIn("quota leftover", page)


class TestPngWordmark(unittest.TestCase):
    def test_flag_off_does_not_embed_the_mark(self):
        from core import html_report
        from core.ascii_art import startup_banner_lines

        with patch.dict(os.environ, {"CONTENT_UI_WORDMARK": "0"}, clear=False):
            page = html_report.themed_page("T", "<p>x</p>")
            banner = startup_banner_lines("tapin")
        self.assertNotIn("wordmark.png", page)
        self.assertTrue(banner)

    def test_flag_on_includes_the_png_in_html(self):
        from core import html_report
        from core.wordmark import wordmark_path

        path = wordmark_path()
        self.assertTrue(path.is_file(), path)
        with patch.dict(os.environ, {"CONTENT_UI_WORDMARK": "1"}, clear=False):
            page = html_report.themed_page("T", "<p>x</p>")
        self.assertIn("wordmark.png", page.replace("\\", "/"))
        self.assertIn('class="wordmark"', page.replace("'", '"'))


class TestEndCardPreview(unittest.TestCase):
    def test_tapin_preview_png_is_not_the_blank_canvas(self):
        from video.end_card_preview import render_end_card_preview

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "card.png"
            result = render_end_card_preview(str(dest), channel_id="tapin")
            self.assertEqual(result.text, "TAP IN FOR MORE")
            self.assertTrue(Path(result.path).is_file())
            image = Image.open(result.path)
            self.assertEqual(image.size, (1080, 1920))
            bg = image.getpixel((0, 0))
            self.assertEqual(bg, (11, 15, 20))
            painted = any(
                image.getpixel((x, y)) != bg
                for y in range(800, 1120, 8)
                for x in range(200, 880, 8)
            )
            self.assertTrue(painted, "end card PNG is a blank background")

    def test_disabled_card_refuses_honestly(self):
        from video.end_card_preview import render_end_card_preview

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "card.png"
            with self.assertRaises(ValueError) as ctx:
                render_end_card_preview(str(dest), channel_id="default")
        self.assertIn("end card", str(ctx.exception).lower())
        self.assertFalse(dest.is_file())

    def test_ops_verb_usage_line(self):
        from argparse import Namespace
        from io import StringIO
        from unittest.mock import patch as mock_patch

        from scripts import ops

        self.assertIn("end-card-preview", ops.COMMANDS)
        buf = StringIO()
        with mock_patch("sys.stdout", buf):
            rc = ops.COMMANDS["end-card-preview"][1](Namespace(channel="tapin", path=""))
        self.assertEqual(rc, 2)
        self.assertIn("end-card-preview requires --path", buf.getvalue())


class TestIntroWaveform(unittest.TestCase):
    def _sine_wav(self, path: Path, *, seconds: float = 0.4, rate: int = 8000) -> None:
        import math

        n = int(rate * seconds)
        with wave.open(str(path), "w") as fh:
            fh.setnchannels(1)
            fh.setsampwidth(2)
            fh.setframerate(rate)
            frames = b"".join(
                struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * i / rate)))
                for i in range(n)
            )
            fh.writeframes(frames)

    def test_fixture_wav_reports_duration_and_offset(self):
        from video.intro_waveform import describe_intro_waveform

        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "sting.wav"
            self._sine_wav(wav, seconds=0.4)
            dest = Path(tmp) / "wave.png"
            result = describe_intro_waveform(str(wav), dest_path=str(dest), channel_id="tapin")
            self.assertAlmostEqual(result.duration_seconds, 0.4, places=1)
            self.assertAlmostEqual(result.offset_seconds, 2.15, places=2)
            self.assertIn("0.4", result.line)
            self.assertIn("2.15", result.line)
            self.assertTrue(Path(result.path).is_file())

    def test_missing_file_refuses_without_warning(self):
        from video.intro_waveform import describe_intro_waveform

        with self.assertLogs(level="WARNING") as cm:
            logging.getLogger("video.intro_waveform").warning("sentinel")
            result = describe_intro_waveform(
                os.path.join("no", "such", "intro.wav"),
                dest_path=os.path.join("no", "such", "out.png"),
            )
        self.assertFalse(result.ok)
        self.assertIn("not found", result.line.lower())
        self.assertEqual([r.getMessage() for r in cm.records], ["sentinel"])

    def test_ops_verb_usage_line(self):
        from argparse import Namespace
        from io import StringIO
        from unittest.mock import patch as mock_patch

        from scripts import ops

        self.assertIn("intro-waveform", ops.COMMANDS)
        buf = StringIO()
        with mock_patch("sys.stdout", buf):
            rc = ops.COMMANDS["intro-waveform"][1](Namespace(channel="tapin", path=""))
        self.assertEqual(rc, 2)
        self.assertIn("intro-waveform requires --path", buf.getvalue())
