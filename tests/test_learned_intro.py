"""#28 learned intro duration — keep 2.15s until drop-off samples exist."""

from __future__ import annotations

import unittest
from unittest.mock import patch


class TestLearnedIntroDuration(unittest.TestCase):
    def test_without_dropoff_samples_keeps_current_duration(self):
        from video.channel_intro import DEFAULT_INTRO_DURATION, learned_intro_duration

        with patch("core.retention.drop_off_ratio", return_value=None):
            self.assertEqual(learned_intro_duration("tapin"), DEFAULT_INTRO_DURATION)
            self.assertAlmostEqual(DEFAULT_INTRO_DURATION, 2.15, places=2)

    def test_known_gap_n_below_floor_does_not_pretend_it_learned(self):
        """Retention needs ≥RETENTION_MIN_VIDEOS curves. Below that, plumbing
        returns the current sting duration rather than a fake learned value.
        Close by feeding real drop-off samples; invert this assertion then.
        """
        from video.channel_intro import learned_intro_duration

        with patch("core.retention.drop_off_ratio", return_value=None):
            self.assertEqual(learned_intro_duration("tapin"), 2.15)

    def test_with_early_dropoff_can_shorten(self):
        from video.channel_intro import learned_intro_duration

        with patch("core.retention.drop_off_ratio", return_value=0.05):
            dur = learned_intro_duration("tapin")
        self.assertLess(dur, 2.15)
        self.assertGreaterEqual(dur, 0.5)


if __name__ == "__main__":
    unittest.main()
