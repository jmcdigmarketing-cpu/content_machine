"""#602 end-card vs caption safe area, #512 grain/vignette ffmpeg, #612 font cache.

Fail-then-fix: Stage 1 centers end-card text at y=(h-text_h)/2 with no safe-area
clamp, and the render graph has no noise=/vignette= from tokens.
"""

from __future__ import annotations

import unittest

from core.design_tokens import channel_tokens, load_tokens
from video.channel_outro import TARGET_H, TARGET_W, build_outro_concat_command, resolve_end_card


class TestEndCardAvoidsCaptionSafeArea(unittest.TestCase):
    def test_drawtext_y_stays_above_the_bottom_fifth(self):
        from video.channel_outro import end_card_text_y

        y = end_card_text_y(text_h=80)
        bottom = int(TARGET_H * 0.80)
        top = int(TARGET_H * 0.12)
        self.assertGreaterEqual(y, top)
        self.assertLessEqual(y + 80, bottom)
        cmd = build_outro_concat_command(
            body_path="in.mp4",
            output_path="out.mp4",
            card=resolve_end_card("tapin")
            or {
                "enabled": True,
                "duration": 1.5,
                "text": "TapIn",
                "bg": "#000000",
                "fg": "#FFFFFF",
            },
        )
        graph = " ".join(cmd)
        self.assertIn("drawtext=", graph)
        self.assertNotIn("y=(h-text_h)/2", graph)

    def test_preview_png_places_text_in_the_same_band(self):
        from video.channel_outro import end_card_text_y
        from video.end_card_preview import preview_text_xy

        y = end_card_text_y(text_h=64)
        _x, py = preview_text_xy(text_w=100, text_h=64, bbox=(0, 0, 100, 64))
        self.assertEqual(py, y)


class TestGrainVignetteFilters(unittest.TestCase):
    def test_render_command_includes_token_driven_look_filters(self):
        from video.render_video import build_render_ffmpeg_command, look_filter_fragment

        tapin = look_filter_fragment("tapin")
        money = look_filter_fragment("moneywise")
        self.assertIn("noise=", tapin)
        self.assertIn("vignette=", tapin)
        self.assertNotEqual(tapin, money)
        grain = channel_tokens("tapin").get("grain")
        self.assertIsNotNone(grain)
        self.assertIn(str(int(grain)), tapin)
        cmd = build_render_ffmpeg_command(
            background_path="bg.mp4",
            mp3_path="vo.mp3",
            output_path="out.mp4",
            subtitle_path="captions.ass",
            duration=12.0,
            channel_id="tapin",
        )
        blob = " ".join(cmd)
        self.assertIn("noise=", blob)
        self.assertIn("vignette=", blob)


class TestPillowFontCache(unittest.TestCase):
    def test_same_path_and_size_returns_the_same_object(self):
        from core.font_cache import load_font

        a = load_font("arial.ttf", 24)
        b = load_font("arial.ttf", 24)
        c = load_font("arial.ttf", 32)
        self.assertIs(a, b)
        self.assertIsNot(a, c)


class TestDoubleSignatures(unittest.TestCase):
    def test_known_doubles_still_bind_the_live_parameters(self):
        from tests.signature_audit import audit_known_doubles

        self.assertEqual(audit_known_doubles(), [])
