"""Tests for the human-context layer (core/channel_persona)."""

import unittest
from unittest.mock import patch

from config.channels import ChannelProfile
from core import channel_persona as cp


def _profile(persona=None):
    return ChannelProfile(id="tapin", name="TapIn", domain="gaming", persona=persona or {})


class TestPersonaBlock(unittest.TestCase):
    def test_empty_when_unconfigured_and_no_history(self):
        with (
            patch.object(cp, "get_channel_profile", return_value=_profile({})),
            patch.object(cp, "recent_input_topics", return_value=[]),
        ):
            self.assertEqual(cp.human_context_block("tapin"), "")

    def test_persona_fields_render_in_order(self):
        persona = {"tone": "hyped but sharp", "audience": "UFC diehards", "signoff": "Tap in."}
        with (
            patch.object(cp, "get_channel_profile", return_value=_profile(persona)),
            patch.object(cp, "recent_input_topics", return_value=[]),
        ):
            block = cp.human_context_block("tapin")
        self.assertIn("CHANNEL PERSONA", block)
        self.assertIn("Tone: hyped but sharp", block)
        self.assertIn("Audience: UFC diehards", block)
        self.assertIn("Sign-off: Tap in.", block)
        # Tone (known) appears before the sign-off (stable ordering).
        self.assertLess(block.index("Tone:"), block.index("Sign-off:"))

    def test_arbitrary_persona_key_supported(self):
        with (
            patch.object(
                cp, "get_channel_profile", return_value=_profile({"catchphrase": "Let's go"})
            ),
            patch.object(cp, "recent_input_topics", return_value=[]),
        ):
            block = cp.human_context_block("tapin")
        self.assertIn("Catchphrase: Let's go", block)


class TestContinuity(unittest.TestCase):
    def test_anchor_continuity(self):
        with (
            patch.object(cp, "get_channel_profile", return_value=_profile({})),
            patch.object(
                cp,
                "recent_input_topics",
                return_value=["Marvel Rivals patch", "Marvel Rivals meta", "Marvel Rivals season"],
            ),
            patch.object(cp, "dominant_anchor", return_value="Marvel Rivals"),
        ):
            block = cp.human_context_block("tapin")
        self.assertIn("CONTINUITY", block)
        self.assertIn("Marvel Rivals", block)
        self.assertIn("NEVER invent", block)

    def test_theme_continuity_without_anchor(self):
        with (
            patch.object(cp, "get_channel_profile", return_value=_profile({})),
            patch.object(cp, "recent_input_topics", return_value=["UFC 300 recap", "NBA trades"]),
            patch.object(cp, "dominant_anchor", return_value=None),
        ):
            block = cp.human_context_block("tapin")
        self.assertIn("CONTINUITY", block)
        self.assertIn("UFC 300 recap", block)

    def test_no_continuity_with_thin_history(self):
        with (
            patch.object(cp, "get_channel_profile", return_value=_profile({})),
            patch.object(cp, "recent_input_topics", return_value=["only one topic"]),
        ):
            self.assertEqual(cp.human_context_block("tapin"), "")


if __name__ == "__main__":
    unittest.main()
