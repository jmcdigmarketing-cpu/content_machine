"""#976: angles get the contrast-frame check too.

Run 113's angle was "Heat's preseason chemistry is a trap, not a peak"; the title then had to
keep it, and #973 could only cut the frame from the title. `apis/topic_variants._clean_angle_lines`
now cuts a ", not Y" tail from each generated angle when the rest still stands (20+ characters),
so the menu, the brief and the script never see the frame.
"""

from __future__ import annotations

import unittest


class AngleTests(unittest.TestCase):
    def test_run113s_angle_loses_the_frame(self):
        from apis.topic_variants import _clean_angle_lines

        raw = "1. Heat's preseason chemistry is a trap, not a peak\n2. Bam's new jumper is real"
        self.assertEqual(
            _clean_angle_lines(raw, []),
            ["Heat's preseason chemistry is a trap", "Bam's new jumper is real"],
        )

    def test_a_short_angle_is_left_whole(self):
        from apis.topic_variants import _clean_angle_lines

        self.assertEqual(_clean_angle_lines("A trap, not a peak", []), ["A trap, not a peak"])

    def test_a_plain_angle_is_untouched(self):
        from apis.topic_variants import _clean_angle_lines

        raw = "Why the Lakers are not a contender yet"
        self.assertEqual(_clean_angle_lines(raw, []), [raw])


if __name__ == "__main__":
    unittest.main()
