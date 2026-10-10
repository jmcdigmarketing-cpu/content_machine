"""#1044 black and frozen stretches longer than half a second, with a start time.

The input is ffmpeg's stderr. No file is rendered.
"""

from __future__ import annotations

import unittest

from core.technical_qc import frame_filter, parse_frame_findings

STDERR = """
[blackdetect @ 0x1] black_start:1.25 black_end:1.60 black_duration:0.35
[blackdetect @ 0x1] black_start:4.00 black_end:4.80 black_duration:0.80
[freezedetect @ 0x1] freeze_start: 2.50 freeze_duration: 0.40 freeze_end: 2.90
[freezedetect @ 0x1] freeze_start: 8.00 freeze_duration: 1.20 freeze_end: 9.20
"""


class TestFrameFindings(unittest.TestCase):
    def test_only_stretches_longer_than_half_a_second_are_kept(self):
        findings = parse_frame_findings(STDERR)
        self.assertEqual(
            [(item.kind, item.start) for item in findings], [("black", 4.0), ("frozen", 8.0)]
        )
        self.assertGreater(findings[0].duration, 0.5)
        self.assertGreater(findings[1].duration, 0.5)

    def test_the_end_card_stretch_is_not_a_finding(self):
        # Runs 131-133: a 1.467s black and freeze at the appended card warned every render.
        from core.technical_qc import without_tail

        stderr = (
            "black_start:4.00 black_end:4.80 black_duration:0.80\n"
            "black_start:101.367 black_end:102.834 black_duration:1.467\n"
            "freeze_start:101.367 freeze_duration:1.467\n"
        )
        kept = without_tail(parse_frame_findings(stderr), duration=102.834, tail_s=1.5)
        self.assertEqual([(item.kind, item.start) for item in kept], [("black", 4.0)])

    def test_both_filters_use_half_a_second(self):
        text = frame_filter()
        self.assertIn("blackdetect=d=0.5", text)
        self.assertIn("freezedetect=n=-60dB:d=0.5", text)
        self.assertNotIn("d=0.25", text)
        self.assertNotIn("d=1.0", text)


if __name__ == "__main__":
    unittest.main()
