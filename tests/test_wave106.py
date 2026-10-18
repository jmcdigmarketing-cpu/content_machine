"""#1283 #1284 #1285 (the operator, 2026-10-17: "lets do theses").

- #1283: `requeue_upload --queue` uploaded private with no publish time, and the worker's own
  quota message tells the operator to run it. Now: public at the next slot; `--private` keeps
  the old way.
- #1284: job 61 (run 159) sat "running" after an interrupted worker; the worker reclaims only
  after 45 minutes, live worker or dead. Now a worker that holds the worker lock alone frees
  them at once.
- #1285: the shelf put news first but never checked a slot against the window, and handed out
  slots other uploads already held. Now taken slots are skipped and news that would miss its
  window gets a 6 PM slot that day.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

SAT_730_PM_EDT = datetime(2026, 10, 17, 23, 30, tzinfo=timezone.utc)
SAT_10PM = datetime(2026, 10, 18, 2, 0, tzinfo=timezone.utc)
SUN_NOON = datetime(2026, 10, 18, 16, 0, tzinfo=timezone.utc)
SUN_6PM = datetime(2026, 10, 18, 22, 0, tzinfo=timezone.utc)
SUN_10PM = datetime(2026, 10, 19, 2, 0, tzinfo=timezone.utc)


def _row(run_id):
    return {"run_id": run_id, "title": f"run {run_id}", "state": "rendered, never uploaded"}


def _plan(rows, windows, ages, taken=(), metas=None, run_ids=None):
    from core import spaced_queue

    metas = metas or {}
    with (
        patch("core.stale_renders.shelf_rows", return_value=rows),
        patch("core.batch_review.draft_meta_for_run", side_effect=lambda _c, r: metas.get(r, {})),
        patch.object(spaced_queue, "_window_days", side_effect=lambda r, _c: windows[r]),
        patch.object(spaced_queue, "_age_days", side_effect=lambda r: ages[r]),
        patch.object(spaced_queue, "_taken_slots", return_value=set(taken)),
    ):
        return spaced_queue.shelf_schedule("tapin", run_ids=run_ids, now=SAT_730_PM_EDT)


# ---- #1285: taken slots and the news window ---------------------------------------------------


class TakenSlotTests(unittest.TestCase):
    def test_a_slot_another_upload_holds_is_skipped(self):
        plan = _plan([_row(170)], {170: 7}, {170: 0.1}, taken={SAT_10PM, SUN_NOON})
        self.assertEqual(plan[0].publish_at, SUN_10PM)

    def test_the_taken_slots_are_read_from_jobs_and_the_schedule(self):
        from core import spaced_queue

        job = SimpleNamespace(status="pending", job_type="upload", channel_id="tapin",
                              payload_json='{"youtube_publish_at": "2026-10-18T16:00:00+00:00"}')  # fmt: skip
        log_row = SimpleNamespace(published_at=SUN_10PM)
        with (
            patch(
                "storage.repositories.jobs.get_job_repository",
                return_value=SimpleNamespace(list_active_jobs=lambda: [job]),
            ),  # fmt: skip
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=SimpleNamespace(list_future_scheduled=lambda _c: [log_row]),
            ),  # fmt: skip
        ):
            self.assertEqual(spaced_queue._taken_slots("tapin"), {SUN_NOON, SUN_10PM})


class NewsWindowTests(unittest.TestCase):
    def test_news_that_would_miss_its_window_takes_6_pm(self):
        # Three 1-day stories at 7:30 PM Saturday: windows end Sunday ~7:30 PM. Sat 10 PM and
        # Sun noon fit; Sun 10 PM does not - the third takes Sun 6 PM.
        rows = [_row(171), _row(172), _row(173), _row(174)]
        windows = {171: 1, 172: 1, 173: 1, 174: 7}
        ages = {171: 0.0, 172: 0.0, 173: 0.0, 174: 0.0}
        plan = {s.run_id: s.publish_at for s in _plan(rows, windows, ages)}
        self.assertEqual(sorted(plan[r] for r in (171, 172, 173)), [SAT_10PM, SUN_NOON, SUN_6PM])
        self.assertEqual(plan[174], SUN_10PM)  # the 6 PM slot used up no noon/10 PM place

    def test_with_no_slot_inside_it_is_listed_not_queued(self):
        rows = [_row(175)]
        plan = _plan(rows, {175: 2}, {175: 1.95}, taken={SAT_10PM})  # ends ~8:40 PM Saturday
        self.assertIsNone(plan[0].publish_at)
        self.assertIn("window", plan[0].skipped)


# ---- #1283: requeue goes public at a slot -----------------------------------------------------


class RequeueTests(unittest.TestCase):
    def _main(self, argv, plan):
        from scripts import requeue_upload

        run = SimpleNamespace(id=170, channel_id="tapin", title="A video", selected_topic="",
                              status="rendered", mp4_path="video.mp4", tags_json="[]",
                              description="")  # fmt: skip
        queue = MagicMock(return_value=[170])
        with (
            patch.object(requeue_upload, "_lookup_run", return_value=(run, None)),
            patch.object(requeue_upload, "_resolve_mp4_path", return_value="video.mp4"),
            patch("apis.youtube_quota.has_quota_for_upload", return_value=True),
            patch("core.spaced_queue.shelf_schedule", return_value=plan),
            patch("core.spaced_queue.free_slots", return_value=[SUN_NOON]),
            patch("core.spaced_queue.queue_spaced_uploads", queue),
            patch.object(requeue_upload, "enqueue_upload_job") as private,
        ):
            code = requeue_upload.main(argv)
        return code, queue, private

    def test_queue_is_public_at_the_next_slot(self):
        from core.spaced_queue import SpacedSlot

        code, queue, private = self._main(
            ["--channel", "tapin", "--run-id", "170", "--queue"],
            [SpacedSlot(run_id=170, title="A video", publish_at=SAT_10PM)],
        )
        self.assertEqual(code, 0)
        private.assert_not_called()
        self.assertEqual(queue.call_args.args[0][0].publish_at, SAT_10PM)

    def test_a_run_the_shelf_does_not_list_takes_the_next_free_slot(self):
        code, queue, _private = self._main(["--channel", "tapin", "--run-id", "170", "--queue"], [])
        self.assertEqual(code, 0)
        self.assertEqual(queue.call_args.args[0][0].publish_at, SUN_NOON)

    def test_an_expired_story_is_not_queued(self):
        from core.spaced_queue import SpacedSlot

        code, queue, private = self._main(
            ["--channel", "tapin", "--run-id", "170", "--queue"],
            [SpacedSlot(run_id=170, title="A video", skipped="past its 2-day window")],
        )
        self.assertNotEqual(code, 0)
        queue.assert_not_called()
        private.assert_not_called()

    def test_private_keeps_the_old_upload(self):
        code, queue, private = self._main(
            ["--channel", "tapin", "--run-id", "170", "--queue", "--private"], []
        )
        self.assertEqual(code, 0)
        queue.assert_not_called()
        private.assert_called_once()


# ---- #1284: a dead worker's job is freed at once ----------------------------------------------


class WorkerLockTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = os.path.join(tmp.name, "worker.lock")

    def test_a_second_holder_is_refused_while_the_first_lives(self):
        from jobs import worker

        first = worker._try_lock(self.path)
        self.assertIsNotNone(first)
        self.assertIsNone(worker._try_lock(self.path))
        worker._release_lock(first)
        again = worker._try_lock(self.path)
        self.assertIsNotNone(again)
        worker._release_lock(again)

    def test_alone_the_stuck_jobs_are_freed_at_once(self):
        from jobs import worker

        repo = MagicMock()
        repo.reclaim_stuck_running.return_value = 1
        with (
            patch.object(worker, "_sole_worker", return_value=True),
            patch.object(worker, "get_job_repository", return_value=repo),
        ):
            worker._reclaim_stuck_jobs()
        repo.reclaim_stuck_running.assert_called_once_with(0)

    def test_beside_a_live_worker_the_45_minutes_stand(self):
        from jobs import worker

        repo = MagicMock()
        repo.reclaim_stuck_running.return_value = 0
        with (
            patch.object(worker, "_sole_worker", return_value=False),
            patch.object(worker, "get_job_repository", return_value=repo),
            patch.dict(os.environ, {"JOB_STUCK_MINUTES": ""}),
        ):
            worker._reclaim_stuck_jobs()
        repo.reclaim_stuck_running.assert_called_once_with(45)


if __name__ == "__main__":
    unittest.main()
