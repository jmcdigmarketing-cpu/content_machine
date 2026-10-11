"""Wave 79 (#1129 #1130 #1131): a queued upload that nothing sends, and the shelf row by row.

Measured 2026-10-11: job 54 - run 132, public, due 9:30 pm on Oct 10 - was still pending the
next morning. Uploads go out only while `jobs.worker` runs; every queue path prints "Run the
worker" and nothing starts it. The header said "queue 3": that job plus two the operator had
removed in June. And the shelf called run 132 "never uploaded" when it was queued.
"""

from __future__ import annotations

import io
import os
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

NOW = datetime(2026, 10, 11, 5, 0, tzinfo=timezone.utc)


def _job(job_id, *, status="pending", kind="upload", run=132, due=None, error="", channel="tapin"):
    return SimpleNamespace(
        id=job_id,
        channel_id=channel,
        job_type=kind,
        status=status,
        content_run_id=run,
        last_error=error,
        scheduled_at=due,
    )


LATE = _job(54, due=NOW - timedelta(hours=3))


class QueueTruthTests(unittest.TestCase):
    def test_a_job_the_operator_removed_is_not_active(self):
        from core import job_queue

        removed = _job(4, status="failed", run=7, error=job_queue.REMOVED_BY_OPERATOR)
        quota = _job(9, status="failed", run=9, error="quotaExceeded")
        repo = SimpleNamespace(list_active_jobs=lambda: [removed, quota, LATE])
        self.assertEqual([j.id for j in job_queue.list_active_jobs(repo)], [9, 54])

    def test_the_cancel_path_writes_the_same_reason(self):
        import inspect

        from analytics import queue_manager
        from core.job_queue import REMOVED_BY_OPERATOR

        default = inspect.signature(queue_manager.cancel_queue_slots).parameters["reason"].default
        self.assertEqual(default, REMOVED_BY_OPERATOR)

    def test_a_pending_upload_past_its_time_is_overdue(self):
        from core.job_queue import overdue_uploads

        jobs = [
            LATE,
            _job(55, due=NOW - timedelta(minutes=5)),  # inside the grace
            _job(56, due=NOW + timedelta(hours=2)),  # not due yet
            _job(57, kind="render", due=NOW - timedelta(hours=3)),
            _job(58, status="failed", due=NOW - timedelta(hours=3)),
            _job(59, due=None),
        ]
        self.assertEqual([j.id for j in overdue_uploads(jobs, now=NOW)], [54])

    def test_a_text_time_is_read_too(self):
        from core.job_queue import overdue_uploads

        job = _job(54, due="2026-10-10 21:30:00-04:00")
        self.assertEqual(len(overdue_uploads([job], now=NOW)), 1)

    def test_the_header_and_status_name_it(self):
        from core import job_queue, status

        with (
            patch.object(job_queue, "overdue_uploads", return_value=[LATE]),
            patch("core.job_queue.get_job_repository") as repo,
        ):
            repo.return_value.list_active_jobs.return_value = [LATE]
            self.assertEqual(status._hdr_queue("tapin"), "queue 1 (1 upload overdue - ops worker)")
            (line,) = job_queue.overdue_lines([LATE], "tapin")
        self.assertIn("Upload overdue: run 132 was due", line)
        self.assertIn("py -m scripts.ops worker", line)
        self.assertIn("worker-task --install", line)

    def test_another_channels_late_upload_is_not_this_channels(self):
        from core import job_queue

        other = _job(60, channel="moneywise", due=NOW - timedelta(hours=3))
        with patch.object(job_queue, "overdue_uploads", return_value=[other]):
            self.assertEqual(job_queue.overdue_short([other], "tapin"), "")
            self.assertEqual(job_queue.overdue_lines([other], "tapin"), [])


class WorkerTaskTests(unittest.TestCase):
    def test_the_task_runs_a_pass_every_fifteen_minutes(self):
        from core import nightly_task

        argv = nightly_task.worker_install_argv(python=r"C:\Py\python.exe", repo=r"C:\dev\cm")
        self.assertEqual(argv[:6], ["schtasks", "/Create", "/SC", "MINUTE", "/MO", "15"])
        self.assertEqual(argv[argv.index("/TN") + 1], nightly_task.WORKER_TASK)
        command = argv[argv.index("/TR") + 1]
        self.assertIn(os.path.join(r"C:\dev\cm", "scripts", "worker_task.pyw"), command)

    def test_the_launcher_it_points_at_exists(self):
        from core import nightly_task

        self.assertTrue(
            os.path.isfile(os.path.join(nightly_task.REPO_ROOT, nightly_task.WORKER_SCRIPT))
        )

    def test_a_windowless_interpreter_is_used_when_there_is_one(self):
        from core import nightly_task

        with patch("os.path.isfile", return_value=True):
            self.assertTrue(nightly_task._windowless(r"C:\Py\python.exe").endswith("pythonw.exe"))
        with patch("os.path.isfile", return_value=False):
            self.assertEqual(nightly_task._windowless(r"C:\Py\python.exe"), r"C:\Py\python.exe")

    def _doctor(self, late, installed):
        from core import nightly_task

        with (
            patch("core.job_queue.list_active_jobs", return_value=late),
            patch("core.job_queue.overdue_uploads", return_value=late),
            patch.object(nightly_task, "worker_installed", return_value=installed),
        ):
            return nightly_task.worker_doctor("tapin")

    def test_the_doctor_fails_on_an_overdue_upload_and_names_the_fix(self):
        ok, line = self._doctor([LATE], installed=False)
        self.assertFalse(ok)
        self.assertIn("1 upload(s) overdue", line)
        self.assertIn("worker-task --install", line)
        ok, line = self._doctor([LATE], installed=True)
        self.assertFalse(ok)
        self.assertIn("worker_task.log", line)

    def test_the_doctor_passes_with_nothing_waiting(self):
        ok, line = self._doctor([], installed=True)
        self.assertTrue(ok)
        self.assertIn("every 15 minutes", line)
        ok, line = self._doctor([], installed=False)
        self.assertTrue(ok)
        self.assertIn("worker-task --install", line)

    def _ops(self, **kwargs):
        from scripts.ops import COMMANDS

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = COMMANDS["worker-task"][1](Namespace(channel="tapin", **kwargs))
        return code, buf.getvalue()

    def test_ops_worker_task_installs_only_when_asked(self):
        from core import nightly_task

        with (
            patch.object(nightly_task, "run_schtasks", return_value=(1, "not found")) as run,
            patch("core.job_queue.list_active_jobs", return_value=[]),
        ):
            code, text = self._ops(install=False, remove=False)
            self.assertEqual(code, 0)
            self.assertIn("not installed", text)
            self.assertIn("worker-task --install", text)
            for call in run.call_args_list:
                self.assertIn("/Query", call.args[0])
        with patch.object(nightly_task, "run_schtasks", return_value=(0, "SUCCESS")) as run:
            code, text = self._ops(install=True, remove=False)
            self.assertEqual(code, 0)
            self.assertIn("/Create", run.call_args.args[0])
            self.assertIn("every 15 minutes", text)


class ShelfRowTests(unittest.TestCase):
    def _rows(self, renders, ages, queued, holds, overrides=()):
        from core import stale_renders

        with (
            patch("scripts.requeue_upload.list_recyclable", return_value=renders),
            patch.object(stale_renders, "render_age_days", side_effect=lambda run: ages[run.id]),
            patch.object(stale_renders, "_queued_runs", return_value=queued),
            patch("publishing.go_public.unlisted_holds", return_value=holds),
            patch("publishing.go_public.override_held", side_effect=lambda rid: rid in overrides),
            patch.object(stale_renders, "_upload_title", side_effect=lambda row: f"Video {row.id}"),
        ):
            return stale_renders.shelf_rows("tapin")

    def test_each_row_says_what_it_waits_on_and_the_exact_command(self):
        renders = [
            SimpleNamespace(id=132, title="Topuria's outlook"),
            SimpleNamespace(id=114, title="Shevchenko demands a title shot"),
            SimpleNamespace(id=59, title="Mbappe breaks a record"),
        ]
        holds = [
            SimpleNamespace(id=7, content_run_id=140, youtube_video_id="abc123"),
            SimpleNamespace(id=8, content_run_id=141, youtube_video_id="def456"),
        ]
        rows = self._rows(renders, {132: 0.5, 114: 5.0, 59: 80.0}, {132: LATE}, holds, (141,))
        by = {r["run_id"]: r for r in rows}
        self.assertEqual(by[132]["state"], "queued, waiting for the worker")
        self.assertEqual(by[132]["command"], "py -m scripts.ops worker")
        self.assertIn("requeue_upload --channel tapin --run-id 114 --queue", by[114]["command"])
        self.assertIn("80 days ago", by[59]["state"])
        self.assertIn("retire-renders --channel tapin --run-id 59 --apply", by[59]["command"])
        self.assertEqual(
            by[140]["command"], "py -m scripts.ops go-public abc123 --channel tapin --apply"
        )
        self.assertEqual(by[141]["state"], "unlisted, held for a claim")
        self.assertEqual(by[141]["command"], "py -m scripts.ops verify-claim --run-id 141")

    def test_ops_shelf_prints_the_rows(self):
        from core import stale_renders
        from scripts.ops import COMMANDS

        row = {
            "run_id": 132,
            "title": "Topuria's outlook",
            "age_days": 0.5,
            "state": "queued, waiting for the worker",
            "command": "py -m scripts.ops worker",
        }
        buf = io.StringIO()
        with patch.object(stale_renders, "shelf_rows", return_value=[row]), redirect_stdout(buf):
            code = COMMANDS["shelf"][1](Namespace(channel="tapin"))
        self.assertEqual(code, 0)
        self.assertIn("1 finished video(s) not public", buf.getvalue())
        self.assertIn("run 132  Topuria's outlook", buf.getvalue())
        self.assertIn("py -m scripts.ops worker", buf.getvalue())

    def test_an_empty_shelf_says_so(self):
        from core import stale_renders

        with patch.object(stale_renders, "shelf_rows", return_value=[]):
            self.assertEqual(
                stale_renders.shelf_report("tapin"),
                ["Shelf - tapin: every finished video is public."],
            )


if __name__ == "__main__":
    unittest.main()
