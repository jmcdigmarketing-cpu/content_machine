"""#463: the benches print a miss and exit 0, so a regression never fails.

The historical miss is WORDS_PER_SECOND at 2.4 against delivery near 3.3 (decisions
§20, run 66). The caption bench's own line is 150ms. These call the verdicts. They
do not read output/ and they do not download a model.
"""

from __future__ import annotations

import unittest


class DurationThresholdTests(unittest.TestCase):
    def test_the_historical_rate_miss_fails(self):
        from scripts.bench_script_duration import duration_verdict

        self.assertEqual(duration_verdict(3.3, 2.4), 1)

    def test_a_rate_inside_five_percent_passes(self):
        from scripts.bench_script_duration import duration_verdict

        self.assertEqual(duration_verdict(3.3, 3.3), 0)
        self.assertEqual(duration_verdict(3.4, 3.3), 0)


class CaptionThresholdTests(unittest.TestCase):
    def test_a_line_start_past_150ms_fails(self):
        from scripts.bench_caption_align import caption_verdict

        self.assertEqual(caption_verdict([{"ok": True, "line_p90": 0.200, "seconds": 1.0}]), 1)

    def test_a_line_start_inside_150ms_passes(self):
        from scripts.bench_caption_align import caption_verdict

        rows = [
            {"ok": False, "line_p90": 0.400, "seconds": 2.0},
            {"ok": True, "line_p90": 0.100, "seconds": 1.0},
        ]
        self.assertEqual(caption_verdict(rows), 0)
