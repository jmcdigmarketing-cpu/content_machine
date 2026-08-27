"""#237 favicon, #263 1.25x, #235 TapIn swatch, #320 tray git describe.

#245 type pairing, #236 MoneyWise serif, #238 poster, #267 letterbox, #268 safe-area.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import html_report, review_booth, win_notify


class TestBoothFaviconRateSwatch(unittest.TestCase):
    def test_favicon_link_and_default_playback_rate(self):
        html = review_booth.booth_html()
        self.assertIn('rel="icon"', html)
        self.assertIn("favicon", html)
        self.assertIn("playbackRate", html)
        self.assertIn("1.25", html)
        self.assertIn("player.playbackRate=1", html.replace(" ", ""))

    def test_tapin_swatch_uses_shipped_end_card_colors(self):
        from config.channels import get_channel_profile

        profile = get_channel_profile("tapin")
        bg = str(profile.end_card.get("bg") or "")
        self.assertTrue(bg)
        html = html_report.themed_page("Booth", "<p>x</p>", channel_id="tapin")
        self.assertIn("swatch", html.lower())
        self.assertIn(bg.lower(), html.lower())
        money = html_report.themed_page("Booth", "<p>x</p>", channel_id="moneywise")
        self.assertNotIn(bg.lower(), money.lower())

    def test_tapin_swatch_appears_on_the_real_booth(self):
        from config.channels import get_channel_profile

        bg = str(get_channel_profile("tapin").end_card.get("bg") or "")
        html = review_booth.booth_html(channel_id="tapin")
        self.assertIn("swatch", html.lower())
        self.assertIn(bg.lower(), html.lower())


class TestHtmlTypePairingAndMoneywiseSerif(unittest.TestCase):
    def test_pre_and_textarea_use_jetbrains_mono(self):
        page = html_report.themed_page("T", html_report.pre_body("Apify ON"))
        self.assertIn("Segoe UI", page)
        self.assertIn("JetBrains Mono", page)
        self.assertNotIn("Cascadia Mono", page)

    def test_dump_pre_moneywise_uses_a_serif_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"CONTENT_HTML_DIR": tmp, "CONTENT_HTML_OPEN": "false"}):
                path = html_report.dump_pre(
                    "Reliability", "Apify ON", filename="rel.html", channel_id="moneywise"
                )
            text = Path(path).read_text(encoding="utf-8")
        self.assertIn("channel-moneywise", text)
        self.assertIn("Georgia", text)

    def test_moneywise_booth_header_is_serif(self):
        html = review_booth.booth_html(channel_id="moneywise")
        self.assertIn("channel-moneywise", html)
        self.assertIn("Georgia", html)


class TestBoothPosterLetterboxSafeArea(unittest.TestCase):
    def test_thumb_becomes_the_video_poster_and_page_chrome(self):
        with tempfile.TemporaryDirectory() as tmp:
            mp4 = os.path.join(tmp, "clip.mp4")
            thumb = os.path.join(tmp, "thumb.jpg")
            Path(mp4).write_bytes(b"mp4")
            Path(thumb).write_bytes(b"jpg")
            html = review_booth.booth_html(mp4_path=mp4, thumb_path=thumb)
        self.assertIn("poster=", html)
        self.assertIn("9/16", html.replace(" ", ""))
        self.assertIn("poster-chrome", html)

    def test_player_letterboxes_instead_of_stretching(self):
        html = review_booth.booth_html()
        self.assertIn("class='stage'", html)
        self.assertIn("object-fit: contain", html)

    def test_safe_area_overlay_is_off_until_toggled(self):
        html = review_booth.booth_html()
        self.assertIn("safe-area", html)
        self.assertIn("toggleSafeArea", html)
        self.assertNotIn("stage safe-on", html)


class TestTrayGitDescribe(unittest.TestCase):
    def test_describe_line_from_helper(self):
        snap = {
            "youtube": {"remaining": 10_000},
            "elevenlabs": {"chars_used": 0},
            "apify": {"exhausted": False},
        }
        with (
            patch.object(win_notify, "git_describe", return_value="v0.1.0-12-gabc1234"),
            patch("apis.youtube_quota.uploads_remaining", return_value=6),
        ):
            lines = win_notify.quota_chip_lines(snap)
        self.assertTrue(any("v0.1.0-12-gabc1234" in ln for ln in lines))

    def test_describe_fail_open_omits_the_line(self):
        snap = {
            "youtube": {"remaining": 10_000},
            "elevenlabs": {"chars_used": 0},
            "apify": {"exhausted": False},
        }
        with (
            patch.object(win_notify, "git_describe", return_value=""),
            patch("apis.youtube_quota.uploads_remaining", return_value=6),
        ):
            lines = win_notify.quota_chip_lines(snap)
        self.assertFalse(any(ln.startswith("Git:") for ln in lines))
