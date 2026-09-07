"""#183 font pairing, #184 motion presets, #190 disclaimer bug, #191 disclosure lower-third."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch


class TestCaptionFontPairing(unittest.TestCase):
    def test_ass_uses_title_font_then_body_font(self):
        from video.caption_timing import build_ass_karaoke
        from video.subtitles import caption_fonts

        title, body = caption_fonts("tapin")
        self.assertNotEqual(title, body)
        words = [
            {"word": "Hook", "start": 0.0, "end": 0.3},
            {"word": "line.", "start": 0.3, "end": 0.6},
            {"word": "Body", "start": 0.8, "end": 1.1},
            {"word": "next.", "start": 1.1, "end": 1.4},
        ]
        ass = build_ass_karaoke(words, title_font=title, body_font=body)
        self.assertIn(f"Style: Title,{title},", ass)
        self.assertIn(f"Style: Body,{body},", ass)
        dialogues = [ln for ln in ass.splitlines() if ln.startswith("Dialogue:")]
        self.assertGreaterEqual(len(dialogues), 2)
        self.assertIn(",Title,", dialogues[0])
        self.assertIn(",Body,", dialogues[1])

    def test_shipped_channels_still_validate_with_font_pair(self):
        from config.validate_channels import _load_raw, validate_channel

        raw = _load_raw()["channels"]
        for cid in ("tapin", "moneywise"):
            errors, _warnings = validate_channel(cid, raw[cid])
            self.assertEqual(errors, [], errors)


class TestNamedMotionPresets(unittest.TestCase):
    def test_presets_are_distinct_and_disabled_is_empty(self):
        from video.hook_motion import named_motion_filter

        words = [
            {"word": "This", "start": 0.1, "end": 0.4},
            {"word": "lands.", "start": 0.4, "end": 0.9},
        ]
        punch = named_motion_filter(words, {"enabled": True, "preset": "punch-in"})
        snap = named_motion_filter(words, {"enabled": True, "preset": "snap-zoom"})
        self.assertTrue(punch)
        self.assertTrue(snap)
        self.assertNotEqual(punch, snap)
        self.assertIn("zoompan", punch)
        self.assertIn("zoompan", snap)
        self.assertEqual(named_motion_filter(words, {"enabled": False, "preset": "punch-in"}), "")
        self.assertEqual(named_motion_filter(None, {"enabled": True, "preset": "punch-in"}), "")


class TestPolicyOverlays(unittest.TestCase):
    def test_moneywise_disclaimer_is_on_screen_tapin_is_not(self):
        from video.policy_overlays import build_policy_overlays_ass

        words = [{"word": "Hello", "start": 0.0, "end": 1.0}]
        money = build_policy_overlays_ass("moneywise", words, duration=8.0)
        tapin = build_policy_overlays_ass("tapin", words, duration=8.0)
        self.assertIn("Not financial advice", money)
        self.assertNotIn("Not financial advice", tapin)

    def test_ai_disclosure_overlay_honours_the_flag(self):
        from video.policy_overlays import build_policy_overlays_ass

        words = [{"word": "Hello", "start": 0.0, "end": 1.0}]
        with patch.dict(os.environ, {"AI_DISCLOSURE_ENABLED": "true"}, clear=False):
            on = build_policy_overlays_ass("tapin", words, duration=8.0)
        with patch.dict(os.environ, {"AI_DISCLOSURE_ENABLED": "false"}, clear=False):
            off = build_policy_overlays_ass("tapin", words, duration=8.0)
        self.assertIn("Made with AI", on)
        self.assertNotIn("Made with AI", off)
        self.assertNotIn("Not financial advice", on)
