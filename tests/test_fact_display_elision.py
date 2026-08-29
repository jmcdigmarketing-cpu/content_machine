"""Run 74: a shortened *display* must not look like a shortened *fact*.

The key-facts prompt printed `    + {ex[:90]}` with no ellipsis at all, so a
scraped paragraph appeared on screen as "...developer" and the operator could not
tell whether the fact itself had been cut. It had also *actually* been cut, at 400
chars, elsewhere — which is why the two problems read as one.

Now the fact is never cut (see test_fact_sentence_split) and the display always
says when it is only showing part of one.
"""

from __future__ import annotations

import unittest

from core.ui import _elide

LONG = (
    "After more than 18 months since the last official glimpse of Grand Theft Auto 6, "
    "developer Rockstar has shown fans a 26-minute extended look at the game."
)


class TestElision(unittest.TestCase):
    def test_short_text_is_untouched(self):
        self.assertEqual(_elide("Six wanted stars return.", 90), "Six wanted stars return.")

    def test_text_at_the_limit_is_untouched(self):
        text = "x" * 90
        self.assertEqual(_elide(text, 90), text)

    def test_long_text_is_marked_as_elided(self):
        shown = _elide(LONG, 90)
        self.assertLess(len(shown), len(LONG))
        self.assertIn("…", shown)

    def test_the_hidden_amount_is_named(self):
        shown = _elide(LONG, 90)
        self.assertIn("+", shown)
        self.assertIn("chars", shown)

    def test_it_never_severs_a_word(self):
        shown = _elide(LONG, 90)
        head = shown.split("…")[0].strip()
        self.assertTrue(LONG.startswith(head))
        self.assertTrue(
            LONG[len(head) : len(head) + 1] in ("", " "),
            f"cut mid-word at {head[-20:]!r}",
        )

    def test_a_single_unbroken_token_still_fits_the_width(self):
        shown = _elide("x" * 300, 90)
        self.assertIn("…", shown)


class TestTheLinkFactPreviewSaysWhenItIsShowingLess(unittest.TestCase):
    def test_the_run_74_line_now_carries_an_ellipsis(self):
        # The exact fact that printed bare in run 74.
        self.assertIn("…", _elide(LONG, 90))


if __name__ == "__main__":
    unittest.main()
