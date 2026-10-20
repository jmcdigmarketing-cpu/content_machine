"""Wave 116 (2026-10-19 evening): the next ten.

Measured first: job 74 (run 173) was held by the quota and `ops status` called it overdue with
"nothing is sending uploads - py -m scripts.ops worker"; the worker's log said "No pending jobs."
and gave a requeue command. The morning's queue printed job times in UTC and YouTube's in EDT, and
listed runs 162, 164 and 165 - public since 10-18 - at their finished jobs' old slots, so the next
free slot was Sat 10-24 noon.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

NOW = datetime(2026, 10, 19, 23, 30, tzinfo=timezone.utc)


def _job(job_id, run_id, slot, status="completed"):
    return SimpleNamespace(
        id=job_id,
        content_run_id=run_id,
        status=status,
        job_type="upload",
        channel_id="tapin",
        last_error="",
        scheduled_at=None,
        payload_json=json.dumps({"youtube_publish_at": slot.isoformat(), "title": f"run {run_id}"}),
    )


def _row(row_id, run_id, when, video="vid"):
    return SimpleNamespace(
        id=row_id,
        content_run_id=run_id,
        published_at=when,
        status="scheduled",
        youtube_video_id=f"{video}{run_id}",
        title=f"run {run_id}",
    )


class QueueTruthTests(unittest.TestCase):
    """#1527: a run YouTube has is listed at the publish log's time, not its job's old slot."""

    def _patched(self, jobs, uploaded, future):
        jobs_repo = MagicMock()
        jobs_repo.list_upload_jobs.return_value = jobs
        log_repo = MagicMock()
        log_repo.list_uploaded_for_channel.return_value = uploaded
        log_repo.list_future_scheduled.return_value = future
        return (
            patch("storage.repositories.jobs.get_job_repository", return_value=jobs_repo),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=log_repo,
            ),
        )

    def _world(self):
        now = datetime.now(timezone.utc)
        moved_from, moved_to = now + timedelta(hours=20), now + timedelta(hours=68)
        stale = now + timedelta(days=3)
        jobs = [
            _job(66, 161, moved_from),  # moved on YouTube: the log says moved_to
            _job(69, 164, stale),  # public since 10-18: the log's time has passed
            _job(74, 173, now + timedelta(hours=22), status="pending"),  # not on YouTube yet
        ]
        uploaded = [_row(1648, 164, now - timedelta(days=1))]
        future = [_row(1645, 161, moved_to)]
        return jobs, uploaded, future, moved_to

    def test_each_video_once_at_youtubes_time(self):
        from analytics.upload_queue import list_queue_entries

        jobs, uploaded, future, moved_to = self._world()
        a, b = self._patched(jobs, uploaded, future)
        with a, b:
            entries = list_queue_entries("tapin")
        self.assertEqual([e.content_run_id for e in entries], [173, 161])
        self.assertEqual(entries[1].publish_at, moved_to)

    def test_a_finished_jobs_old_slot_is_not_reserved(self):
        from analytics.upload_queue import get_reserved_publish_times

        jobs, uploaded, future, moved_to = self._world()
        a, b = self._patched(jobs, uploaded, future)
        with a, b:
            reserved = get_reserved_publish_times("tapin")
        self.assertEqual(len(reserved), 2)
        self.assertEqual(max(reserved), moved_to)


class QueueLinesTests(unittest.TestCase):
    """#1527 and #1429: one zone with its label, a clash named, and the next two weeks."""

    def _entry(self, run_id, when, status="scheduled"):
        from analytics.upload_queue import QueueEntry

        return QueueEntry("youtube", run_id, f"run {run_id}", when, status, run_id, True)

    def test_every_time_in_the_channels_zone(self):
        from analytics.upload_queue import queue_lines

        entries = [
            self._entry(156, datetime(2026, 10, 20, 16, 0, tzinfo=timezone.utc)),
            self._entry(173, datetime(2026, 10, 20, 22, 0, tzinfo=timezone.utc), "awaiting_upload"),
        ]
        lines = queue_lines(entries, "tapin")
        self.assertIn("Tue 10-20 12:00 PM EDT", lines[0])
        self.assertIn("Tue 10-20 6:00 PM EDT", lines[1])

    def test_two_at_one_minute_are_named(self):
        from analytics.upload_queue import queue_lines

        noon = datetime(2026, 10, 20, 16, 0, tzinfo=timezone.utc)
        lines = queue_lines([self._entry(156, noon), self._entry(161, noon)], "tapin")
        self.assertIn("the same minute as run 156", lines[1])
        self.assertNotIn("same minute", lines[0].split("run 156")[-1])

    def test_the_next_fourteen_days(self):
        from analytics.upload_queue import two_week_line

        now = datetime(2026, 10, 19, 23, 30, tzinfo=timezone.utc)  # Mon 7:30 PM EDT
        times = [
            datetime(2026, 10, 20, 2, 0, tzinfo=timezone.utc),  # Mon 10 PM
            datetime(2026, 10, 20, 16, 0, tzinfo=timezone.utc),  # Tue
            datetime(2026, 10, 20, 22, 0, tzinfo=timezone.utc),  # Tue
            datetime(2026, 10, 22, 16, 0, tzinfo=timezone.utc),  # Thu
        ]
        line = two_week_line([self._entry(i, t) for i, t in enumerate(times)], "tapin", now=now)
        self.assertEqual(
            line,
            "Next 14 days: 4 scheduled on 3 of 14 days - first empty day Wed 10-21, "
            "nothing after Thu 10-22",
        )
        self.assertEqual(
            two_week_line([], "tapin", now=now), "Next 14 days: nothing scheduled on YouTube"
        )


class QuotaWaitTests(unittest.TestCase):
    """#1526: an upload held by the quota waits for the reset; it is not overdue."""

    def setUp(self):
        reset = datetime(2026, 10, 20, 7, 0, tzinfo=timezone.utc)  # midnight Pacific
        self._patches = [
            patch("apis.youtube_quota.has_quota_for_upload", return_value=False),
            patch("apis.youtube_quota.next_quota_retry_at", return_value=reset),
            patch("core.job_queue._signed_out", return_value=False),
        ]
        for p in self._patches:
            p.start()
        self.job = _job(74, 173, NOW, status="pending")
        self.job.scheduled_at = (NOW - timedelta(hours=1)).isoformat()

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def test_the_status_lines_name_the_reset(self):
        from core.job_queue import overdue_lines, overdue_short

        lines = overdue_lines([self.job], "tapin")
        self.assertEqual(len(lines), 1)
        self.assertIn("waits for the quota reset at Tue 3:00 AM EDT", lines[0])
        self.assertNotIn("ops worker", lines[0])
        self.assertEqual(overdue_short([self.job], "tapin"), "1 upload waits for the quota reset")

    def test_with_quota_it_is_overdue_as_before(self):
        from core.job_queue import overdue_lines

        with patch("apis.youtube_quota.has_quota_for_upload", return_value=True):
            lines = overdue_lines([self.job], "tapin")
        self.assertIn("nothing is sending uploads", lines[0])

    def test_the_shelf_line_asks_for_nothing(self):
        from core import stale_renders

        with patch.object(stale_renders, "_signed_out", return_value=False):
            lines = stale_renders.shelf_lines("tapin", {"renders": 1, "queued": 1})
        joined = " ".join(lines)
        self.assertIn("1 queued, waits for the quota reset at Tue 3:00 AM EDT", joined)
        self.assertNotIn("ops worker", joined)

    def test_the_worker_pass_says_what_it_holds(self):
        from jobs import worker

        repo = MagicMock()
        repo.list_active_jobs.return_value = [self.job]
        with (
            patch.object(worker, "drain_due", return_value=0),
            patch.object(worker, "_sync_metrics"),
            patch.object(worker, "_overnight_watch"),
            patch.object(worker, "get_job_repository", return_value=repo),
            patch("sys.argv", ["worker"]),
            patch("builtins.print") as out,
        ):
            worker.main()
        printed = " ".join(str(c.args[0]) for c in out.call_args_list)
        self.assertIn(
            "1 upload waits for the quota reset (run 173) - it goes after Tue 3:00 AM EDT", printed
        )
        self.assertNotIn("No pending jobs", printed)
        self.assertNotIn("requeue_upload", printed)

    def test_the_morning_still_reads_it_as_the_quota(self):
        from jobs.worker_log import summarize_pass

        line = "1 upload waits for the quota reset (run 173) - it goes after Tue 3:00 AM EDT"
        self.assertEqual(summarize_pass([line]), "uploads blocked by quota until the reset")


if __name__ == "__main__":
    unittest.main()
