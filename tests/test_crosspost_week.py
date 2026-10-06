"""#979: Buffer posts in the weekly report.

`ops crosspost` (#968) packs each render for TikTok and Instagram and `ops crosspost done`
stamps when the operator posted it; nothing counted either, so the weekly report and the
status showed YouTube only. `publishing.crosspost.week_counts` counts packed and posted in the
last seven days and `week_line` says it in one line; the weekly report ends with it and
`ops status` shows it when anything was packed.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

NOW = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)


def _iso(days_ago: float) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat(timespec="seconds")


STORE = {
    "runs": {
        "101": {"packed": _iso(1), "posted": _iso(0.5)},
        "102": {"packed": _iso(2), "posted": ""},
        "103": {"packed": _iso(3), "posted": _iso(2)},
        "90": {"packed": _iso(12), "posted": _iso(11)},  # last week's
        "bad": "not a dict",
    }
}


class CountTests(unittest.TestCase):
    def test_packed_and_posted_this_week(self):
        from publishing.crosspost import week_counts

        with patch("publishing.crosspost._load", return_value=STORE):
            self.assertEqual(week_counts("tapin", now=NOW), (3, 2))

    def test_the_line(self):
        from publishing.crosspost import week_line

        with patch("publishing.crosspost._load", return_value=STORE):
            line = week_line("tapin", now=NOW)
        self.assertIn("3 packed", line)
        self.assertIn("2 posted", line)
        self.assertIn("TikTok", line)

    def test_nothing_packed_says_nothing(self):
        from publishing.crosspost import week_line

        with patch("publishing.crosspost._load", return_value={}):
            self.assertEqual(week_line("tapin", now=NOW), "")


class ReportTests(unittest.TestCase):
    def test_the_weekly_report_ends_with_it(self):
        from analytics.weekly_report import format_report

        with (
            patch("analytics.weekly_report._scoreboard_head", return_value=""),
            patch("publishing.crosspost.week_line", return_value="Buffer this week: 3 packed"),
        ):
            text = format_report({"channel_id": "tapin", "ready": False, "n": 1})
        self.assertIn("Buffer this week: 3 packed", text)

    def test_status_shows_it(self):
        from core import status

        with patch("publishing.crosspost.week_line", return_value="Buffer this week: 3 packed"):
            lines = status.build_status_lines("tapin")
        self.assertIn("Buffer this week: 3 packed", lines)


if __name__ == "__main__":
    unittest.main()
