"""#110 chapter timestamps for Extended; Shorts descriptions stay unchanged."""

from __future__ import annotations

import unittest

from core.chapters import chapter_block
from core.description_extras import apply_description_extras


class TestChapters(unittest.TestCase):
    SCRIPT = (
        "GTA 6 leaks forced Take-Two into court. "
        "The subpoena names Microsoft and Discord. "
        "Here is what that means for the 2026 release window."
    )

    def test_extended_emits_zero_start_chapters(self):
        block = chapter_block(self.SCRIPT, duration=480.0, length_choice="4")
        self.assertTrue(block)
        self.assertTrue(block.startswith("0:00"))
        self.assertIn("\n", block)

    def test_shorts_skip_chapters(self):
        block = chapter_block(self.SCRIPT, duration=45.0, length_choice="1")
        self.assertEqual(block, "")

    def test_description_extras_appends_only_for_extended(self):
        body = apply_description_extras(
            "A look at the leak.",
            "tapin",
            title="GTA 6 leak",
            topic="GTA 6 leak",
            length_choice="4",
            script=self.SCRIPT,
            duration_s=480.0,
        )
        self.assertIn("0:00", body)
        short = apply_description_extras(
            "A look at the leak.",
            "tapin",
            title="GTA 6 leak",
            topic="GTA 6 leak",
            length_choice="1",
            script=self.SCRIPT,
            duration_s=45.0,
        )
        self.assertNotIn("0:00", short)
