"""Wave 78 (#1051): one place lays out what sits under a description's body.

Measured 2026-10-10 on the last 40 TapIn runs: the block order was the same every time
(disclosure, sources, chapters), but three functions each attached their own piece, and the
one that wrote most of it joined with a single newline. On all 10 runs with sources,
"Sources:" sat directly under "Made with AI-assisted narration and editing." with no blank
line.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

DISCLOSURE = "Made with AI-assisted narration and editing."
SOURCES = "Sources:\nhttps://example.com/a\nhttps://example.com/b"
CHAPTERS = "0:00 The setup\n0:41 The numbers\n1:30 What it means"


def _apply(
    body="Body line.", *, urls=("https://example.com/a", "https://example.com/b"), chapters=""
):
    from core import description_extras

    with (
        patch.object(description_extras, "ai_disclosure_line", return_value=DISCLOSURE),
        patch.object(description_extras, "finance_disclaimer_line", return_value=""),
        patch.object(description_extras, "ftc_affiliate_line", return_value=""),
        patch.object(description_extras, "monetization_ctas", return_value=[]),
        patch.object(description_extras, "ensure_seo_first_line", side_effect=lambda d, t="": d),
        patch("core.chapters.chapter_block", return_value=chapters),
        patch.dict("os.environ", {"DESCRIPTION_SOURCES": "true"}),
    ):
        return description_extras.apply_description_extras(
            body, channel_id="tapin", source_urls=list(urls)
        )


class JoinBlocksTests(unittest.TestCase):
    def test_a_blank_line_between_every_block(self):
        from core.description_extras import join_blocks

        self.assertEqual(
            join_blocks("Body.", [DISCLOSURE, SOURCES, CHAPTERS]),
            f"Body.\n\n{DISCLOSURE}\n\n{SOURCES}\n\n{CHAPTERS}",
        )

    def test_empty_blocks_leave_no_gap(self):
        from core.description_extras import join_blocks

        self.assertEqual(join_blocks("Body.", ["", SOURCES, "  "]), f"Body.\n\n{SOURCES}")
        self.assertEqual(join_blocks("", [DISCLOSURE]), DISCLOSURE)
        self.assertEqual(join_blocks("Body.\n\n", []), "Body.")


class BuilderTests(unittest.TestCase):
    def test_sources_are_no_longer_glued_under_the_disclosure(self):
        text = _apply()
        self.assertIn(f"{DISCLOSURE}\n\nSources:\n", text)
        self.assertNotIn(f"{DISCLOSURE}\nSources:", text)

    def test_the_blocks_come_in_the_fixed_order(self):
        text = _apply(chapters=CHAPTERS)
        self.assertEqual(text, f"Body line.\n\n{DISCLOSURE}\n\n{SOURCES}\n\n{CHAPTERS}")

    def test_running_it_twice_changes_nothing(self):
        once = _apply(chapters=CHAPTERS)
        self.assertEqual(_apply(once, chapters=CHAPTERS), once)

    def test_footage_credits_go_last_through_the_same_join(self):
        from core.description_extras import add_footage_credits

        text = add_footage_credits(_apply(), ["Madden 26: owned gameplay"])
        self.assertTrue(text.endswith("\n\nFootage:\nMadden 26: owned gameplay"))
        self.assertEqual(add_footage_credits(text, ["Madden 26: owned gameplay"]), text)

    def test_late_chapters_attach_through_the_same_join(self):
        from core.chapters import _replace_chapter_lines

        text = _replace_chapter_lines("Body.\n\n" + DISCLOSURE + "\n", "", CHAPTERS)
        self.assertEqual(text, f"Body.\n\n{DISCLOSURE}\n\n{CHAPTERS}")


class LayoutCheckTests(unittest.TestCase):
    def _problem(self, text):
        from core import description_extras

        with patch.object(description_extras, "ai_disclosure_line", return_value=DISCLOSURE):
            return description_extras.layout_problem(text, "tapin")

    def test_what_the_builder_writes_has_no_problem(self):
        self.assertEqual(self._problem(_apply(chapters=CHAPTERS)), "")
        self.assertEqual(self._problem("Body only."), "")

    def test_a_glued_sources_block_is_named(self):
        old = f"Body.\n\n{DISCLOSURE}\n{SOURCES}"
        self.assertEqual(self._problem(old), '"Sources:" is glued to the line above it')

    def test_blocks_out_of_order_are_named(self):
        wrong = f"Body.\n\n{CHAPTERS}\n\n{DISCLOSURE}\n\n{SOURCES}"
        self.assertIn("expected notes > sources > chapters", self._problem(wrong))

    def test_the_publish_checklist_carries_it_as_a_warning(self):
        from core import description_extras
        from publishing import prepublish
        from publishing.base import PublishRequest

        old = f"Body.\n\n{DISCLOSURE}\n{SOURCES}"
        request = PublishRequest(file_path="x.mp4", title="T", description=old)
        with (
            patch.object(description_extras, "ai_disclosure_line", return_value=DISCLOSURE),
            patch.object(prepublish, "_disclosure_line", return_value=DISCLOSURE),
            patch.object(prepublish, "_run", return_value=None),
        ):
            checks = {c.name: c for c in prepublish.checklist(request, channel_id="tapin")}
            self.assertFalse(checks["layout"].ok)
            self.assertFalse(checks["layout"].blocks)
            self.assertEqual(prepublish.block_reason(list(checks.values())), "")
            good = PublishRequest(file_path="x.mp4", title="T", description=_apply())
            checks = {c.name: c for c in prepublish.checklist(good, channel_id="tapin")}
            self.assertTrue(checks["layout"].ok)
            self.assertEqual(checks["layout"].detail, "notes > sources")


if __name__ == "__main__":
    unittest.main()
