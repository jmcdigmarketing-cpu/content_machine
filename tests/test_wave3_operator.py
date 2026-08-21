"""Wave 3 operator surfaces: SEO/FTC, stock UFC rewrite, booth, toast launch, tray."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from apis.apify_catalog import remaining_enabled_actors
from assets.background_query import resolve_background_query, sanitize_trademark_stock_query
from core import html_report, review_booth, unit_economics, win_notify
from core.description_extras import (
    DEFAULT_FTC_DISCLOSURE,
    apply_description_extras,
    ensure_seo_first_line,
)
from core.video_grade import GradeComponent, VideoGrade, grade_as_markdown


class TestSeoFirstLineAndFtc(unittest.TestCase):
    def test_hashtag_first_line_gets_title(self):
        with patch.dict(os.environ, {"DESCRIPTION_SEO_FIRST_LINE": "true"}):
            out = ensure_seo_first_line("#UFC #shorts\n\nBody here.", "Topuria stops the streak")
        self.assertTrue(out.startswith("Topuria stops the streak"))
        self.assertIn("Body here.", out)

    def test_strong_first_line_untouched(self):
        with patch.dict(os.environ, {"DESCRIPTION_SEO_FIRST_LINE": "true"}):
            body = "Topuria walks in as champion.\n\nMore context."
            self.assertEqual(ensure_seo_first_line(body, "Other title"), body)

    def test_ftc_line_when_affiliate_cta_present(self):
        with (
            patch.dict(
                os.environ, {"FTC_DISCLOSURE": "true", "DESCRIPTION_SEO_FIRST_LINE": "false"}
            ),
            patch(
                "core.description_extras.get_seo_profile",
                return_value={"monetization_cta": ["Gear: example.com"]},
            ),
        ):
            out = apply_description_extras("Body.", "tapin")
        self.assertIn(DEFAULT_FTC_DISCLOSURE, out)
        self.assertIn("Gear: example.com", out)

    def test_no_ftc_without_cta(self):
        with (
            patch.dict(os.environ, {"FTC_DISCLOSURE": "true"}),
            patch("core.description_extras.get_seo_profile", return_value={}),
        ):
            out = apply_description_extras("Body.", "tapin")
        self.assertNotIn(DEFAULT_FTC_DISCLOSURE, out)


class TestStockUfcRewrite(unittest.TestCase):
    def test_strips_ufc_token(self):
        self.assertNotIn("ufc", sanitize_trademark_stock_query("UFC octagon fight").lower())
        self.assertIn("mma", sanitize_trademark_stock_query("UFC octagon fight").lower())

    def test_resolve_never_sends_ufc_to_pexels(self):
        resolve_background_query.cache_clear()
        with patch.dict(
            os.environ, {"BACKGROUND_QUERY_LLM": "false", "STOCK_QUERY_UFC_REWRITE": "true"}
        ):
            q = resolve_background_query("UFC 319 Topuria vs Oliveira", "sports", "tapin")
        self.assertNotIn("ufc", q.lower())


class TestApifyPills(unittest.TestCase):
    def test_remaining_actors_are_the_two_paid_ones(self):
        names = remaining_enabled_actors()
        self.assertIn("tiktok_trends", names)
        self.assertIn("youtube_competitors", names)
        self.assertNotIn("twitter_breaking", names)
        self.assertNotIn("reddit_community", names)


class TestBoothWave3(unittest.TestCase):
    def test_skip_link_copy_markdown_and_header(self):
        html = review_booth.booth_html(
            run_id=12,
            grade="B (80)",
            authenticity="ok",
            cost="tts $0.31",
            cost_share="tts $0.31 · 91% of this render",
            blocking="thin facts: 1 verified line(s)",
            uploads_left="YouTube: ~6 uploads left this reset",
            elevenlabs_chars="ElevenLabs: 99,000 chars leftover",
            apify_pills=review_booth.apify_pills_html(),
            escaped_pill="<p class='redpill'>Escaped free-first LLM</p>",
            standard_billed="Standard would have billed: $0.3100",
            allocated_line="allocated $0.24/video vs marginal $0.31",
            thin_banner=review_booth.thin_facts_banner_html("thin facts: 1"),
        )
        self.assertIn("Skip to content", html)
        href_player = "href='#player'"
        self.assertIn(href_player, html)
        self.assertIn("Copy as markdown", html)
        self.assertIn("uploads left", html)
        self.assertIn("ElevenLabs", html)
        self.assertIn("tiktok_trends", html)
        self.assertIn("youtube_competitors", html)
        self.assertNotIn("reddit_community", html)
        self.assertNotIn("twitter_breaking", html)
        self.assertIn("Escaped free-first LLM", html)
        self.assertIn("Standard would have billed", html)
        self.assertIn("allocated", html)
        self.assertIn("Thin-facts", html)
        self.assertIn("prefers-contrast", html)

    def test_markdown_helper(self):
        md = review_booth.booth_markdown(grade="A (90)", cost="tts $0.31", run_id=3)
        self.assertIn("# Report card A (90)", md)
        self.assertIn("#3", md)

    def test_grade_as_markdown(self):
        grade = VideoGrade(
            score=80,
            letter="B",
            components=[GradeComponent(name="hook", score=70, weight=0.28)],
        )
        md = grade_as_markdown(grade)
        self.assertIn("# Report card B", md)
        self.assertIn("hook", md)

    def test_allocated_oneliner(self):
        with patch.dict(os.environ, {"COST_TTS_PLAN_USD": "22", "COST_TTS_PLAN_CHARS": "100000"}):
            line = unit_economics.allocated_vs_marginal_oneliner(n_videos=21, marginal=0.31)
        self.assertIn("allocated $1.05/video", line)
        self.assertIn("marginal $0.31", line)


class TestToastOpensMp4(unittest.TestCase):
    def test_launch_attr_in_script(self):
        script = win_notify._toast_script("t", "b", launch="file:///C:/out/a.mp4")
        self.assertIn("activationType", script)
        self.assertIn("file:///C:/out/a.mp4", script)

    def test_file_uri_from_temp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "clip.mp4")
            Path(path).write_bytes(b"x")
            uri = win_notify._file_launch_uri(path)
        self.assertTrue(uri.startswith("file:"))
        self.assertIn("clip.mp4", uri)


class TestTrayGradeAndDoctor(unittest.TestCase):
    def test_chip_includes_grade_when_enabled(self):
        snap = {
            "youtube": {"used": 0, "limit": 10000, "remaining": 10000},
            "elevenlabs": {"chars_used": 0},
            "apify": {"exhausted": False},
        }
        with (
            patch.dict(
                os.environ,
                {"CONTENT_TRAY_GRADE": "true", "ELEVENLABS_MONTHLY_CHAR_BUDGET": "100000"},
            ),
            patch("core.win_notify.last_grade_letter", return_value="B"),
            patch("apis.youtube_quota.uploads_remaining", return_value=6),
        ):
            blob = " | ".join(win_notify.quota_chip_lines(snap))
        self.assertIn("Grade: B", blob)

    def test_doctor_html_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"CONTENT_HTML_DIR": tmp, "CONTENT_HTML_OPEN": "false"}):
                with patch("core.ops_doctor.render", return_value="PASS cuda"):
                    path = win_notify.open_doctor_html("tapin")
            self.assertTrue(os.path.isfile(path))
            text = Path(path).read_text(encoding="utf-8")
        self.assertIn("PASS cuda", text)
        self.assertIn("Skip to content", text)

    def test_html_high_contrast_css(self):
        page = html_report.themed_page("T", "<p>x</p>")
        self.assertIn("prefers-contrast", page)
        self.assertIn("Skip to content", page)
        self.assertIn("id='main'", page)


if __name__ == "__main__":
    unittest.main()
