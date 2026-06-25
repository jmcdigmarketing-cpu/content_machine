"""Tests for retention-curve modelling (core/retention)."""

import unittest
from unittest.mock import patch

from core import retention


def _curve(drop_at: float):
    """A synthetic curve that stays ~1.0 then falls to ~0.2 after `drop_at`."""
    return [(round(i / 20, 2), 1.0 if (i / 20) < drop_at else 0.2) for i in range(21)]


class TestRetention(unittest.TestCase):
    def test_no_model_below_min_videos(self):
        with patch.object(retention, "_curves", return_value=[_curve(0.5)]):
            self.assertIsNone(retention.average_curve("tapin", min_videos=3))
            self.assertEqual(retention.pacing_hint("tapin"), "")

    def test_average_curve_when_enough_videos(self):
        curves = [_curve(0.4), _curve(0.5), _curve(0.6)]
        with patch.object(retention, "_curves", return_value=curves):
            avg = retention.average_curve("tapin", min_videos=3)
        self.assertIsNotNone(avg)
        self.assertEqual(len(avg), 21)
        # Early retention high, late retention low.
        self.assertGreater(avg[1][1], avg[-1][1])

    def test_drop_off_point_detected(self):
        # All three drop at 50% → average crosses the 0.5 floor around there.
        curves = [_curve(0.5), _curve(0.5), _curve(0.5)]
        with patch.dict("os.environ", {"RETENTION_DROPOFF_FLOOR": "0.5"}, clear=False):
            with patch.object(retention, "_curves", return_value=curves):
                pos = retention.drop_off_ratio("tapin", min_videos=3)
        self.assertIsNotNone(pos)
        self.assertGreaterEqual(pos, 0.45)
        self.assertLessEqual(pos, 0.6)

    def test_pacing_hint_text(self):
        curves = [_curve(0.4), _curve(0.4), _curve(0.4)]
        with patch.object(retention, "_curves", return_value=curves):
            hint = retention.pacing_hint("tapin")
        self.assertIn("RETENTION DATA", hint)
        self.assertIn("%", hint)

    def test_no_channel_id(self):
        self.assertEqual(retention.pacing_hint(None), "")

    def test_display_handles_no_data(self):
        lines: list[str] = []
        with patch.object(retention, "_curves", return_value=[]):
            retention.display_retention("tapin", print_fn=lines.append)
        self.assertTrue(any("need" in line.lower() for line in lines))


if __name__ == "__main__":
    unittest.main()
