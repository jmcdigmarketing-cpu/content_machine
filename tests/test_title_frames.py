"""#973: titles get the contrast-frame check.

Run 113 (2026-10-04) shipped the title "Heat's preseason chemistry is a trap, not a peak".
`persona_lint.contrast_frames` (#891) catches the "it's not just X - it's Y" cliche in the
script, but it needs an intensifier ("just", "only") and it never read the title. A title's
version is barer: "X, not Y". `title_contrast_frame` names it, `drop_contrast_tail` cuts the
", not Y" tail, and `title_generator` asks for no such frame and cuts one that comes back - from
the LLM or from the angle it falls back to (run 113's frame came from the angle).
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

RUN113 = "Heat's preseason chemistry is a trap, not a peak"


class DetectTests(unittest.TestCase):
    def test_the_bare_title_frame_is_found(self):
        from core.persona_lint import title_contrast_frame

        self.assertTrue(title_contrast_frame(RUN113))
        self.assertTrue(title_contrast_frame("Wemby's defense is the story, not his scoring"))
        self.assertTrue(title_contrast_frame("It's not just a patch - it's a new game"))

    def test_a_plain_title_is_not(self):
        from core.persona_lint import title_contrast_frame

        self.assertFalse(title_contrast_frame("Heat's preseason chemistry looks real"))
        self.assertFalse(title_contrast_frame("Why the Lakers are not a contender yet"))
        self.assertFalse(title_contrast_frame("Not even close: Jokic wins MVP again"))

    def test_the_tail_is_cut(self):
        from core.persona_lint import drop_contrast_tail

        self.assertEqual(drop_contrast_tail(RUN113), "Heat's preseason chemistry is a trap")
        self.assertEqual(drop_contrast_tail("Plain title"), "Plain title")


class TitleTests(unittest.TestCase):
    def test_clean_title_cuts_the_frame(self):
        from core.title_generator import _clean_title

        got = _clean_title(RUN113, fallback="fallback", angle="Heat preseason chemistry trap")
        self.assertEqual(got, "Heat's preseason chemistry is a trap")

    def test_a_cut_too_short_to_stand_is_left(self):
        from core.title_generator import _clean_title

        self.assertEqual(_clean_title("A trap, not a peak", fallback="fb"), "A trap, not a peak")

    def test_the_prompt_asks_for_no_frame(self):
        from core import title_generator

        with patch.object(title_generator, "complete", return_value=RUN113) as llm:
            title = title_generator.generate_title(
                script="Heat look great. But is it real?", topic=RUN113, channel_id="tapin"
            )
        self.assertIn(", not Y", llm.call_args.args[0])
        self.assertEqual(title, "Heat's preseason chemistry is a trap")

    def test_the_angle_fallback_is_cut_too(self):
        from core import title_generator

        # The LLM title misses the angle, so the angle itself becomes the title.
        with patch.object(title_generator, "complete", return_value="Miami looks good"):
            title = title_generator.generate_title(
                script="Heat look great.", topic=RUN113, channel_id="tapin"
            )
        self.assertEqual(title, "Heat's preseason chemistry is a trap")


if __name__ == "__main__":
    unittest.main()
