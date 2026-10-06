"""#989: the queue count is the channel's own.

Wave 63's startup header, the app's Home and the quota chip counted `list_active_jobs()` for
every channel, so TapIn's header counted job 50 - run 113, queued public on "Default". Now
`core.job_queue.channel_depth` splits the count, and every reader says "queue 2 (+1 other
channel)" - the other channel's job stays visible, but it is not counted as TapIn's.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from storage.repositories.jobs import JobRecord


def _job(i: int, channel: str) -> JobRecord:
    return JobRecord(id=i, channel_id=channel, job_type="upload", status="pending")


JOBS = [_job(1, "tapin"), _job(2, "tapin"), _job(50, "default")]


class DepthTests(unittest.TestCase):
    def test_mine_and_others(self):
        from core.job_queue import channel_depth

        self.assertEqual(channel_depth(JOBS, "tapin"), (2, 1))
        self.assertEqual(channel_depth(JOBS, "default"), (1, 2))
        self.assertEqual(channel_depth([], "tapin"), (0, 0))
        self.assertEqual(channel_depth(None, "tapin"), (0, 0))

    def test_the_words(self):
        from core.job_queue import channel_queue_text

        self.assertEqual(channel_queue_text(JOBS, "tapin"), "queue 2 (+1 other channel)")
        self.assertEqual(channel_queue_text(JOBS[:2], "tapin"), "queue 2")
        self.assertEqual(
            channel_queue_text([_job(50, "default"), _job(51, "moneywise")], "tapin"),
            "queue 0 (+2 other channels)",
        )


class ReaderTests(unittest.TestCase):
    def test_the_header_counts_the_channel(self):
        from core import status

        with patch("core.job_queue.list_active_jobs", return_value=JOBS):
            self.assertEqual(status._hdr_queue("tapin"), "queue 2 (+1 other channel)")

    def test_home_counts_the_channel(self):
        from desktop.home import _queue_line

        with patch("core.job_queue.list_active_jobs", return_value=JOBS):
            self.assertEqual(_queue_line("tapin"), "Queue: 2 (+1 other channel)")


if __name__ == "__main__":
    unittest.main()
