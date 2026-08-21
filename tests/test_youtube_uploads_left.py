"""YouTube remaining units as upload-count ceiling — no data/youtube_quota.json."""

from __future__ import annotations

import unittest

from apis.youtube_quota import (
    UNITS_VIDEO_INSERT,
    format_uploads_left,
    uploads_remaining,
)


class TestUploadsRemaining(unittest.TestCase):
    def test_floor_divide_by_1600(self):
        self.assertEqual(UNITS_VIDEO_INSERT, 1600)
        self.assertEqual(uploads_remaining({"remaining": 8000}), 5)
        self.assertEqual(uploads_remaining({"remaining": 1599}), 0)
        self.assertEqual(uploads_remaining({"remaining": 1600}), 1)
        self.assertEqual(uploads_remaining({"remaining": 0}), 0)

    def test_format_line(self):
        line = format_uploads_left({"remaining": 3200})
        self.assertIn("2 upload", line)
        self.assertIn("1,600", line)


if __name__ == "__main__":
    unittest.main()
