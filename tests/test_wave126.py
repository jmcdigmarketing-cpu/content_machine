"""Wave 126 (2026-10-23 late): the next ten - a phantom slot first.

Measured first, at 22:51 CDT: run 186, a chapter Short of run 185 (both rendered past the
grounding gate), sat in job 82 for Sat noon EDT. The uploader strips a held run's publish time,
so it would never go public then - but its job still held the slot, and run 184's UFC 333
preview, due to move before the card at the 3:05 AM EDT pass, would have gone out at 3:50 AM.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

NOON = datetime(2026, 10, 24, 16, 0, tzinfo=timezone.utc)


def _job(job_id, run_id, publish_at, privacy):
    payload = {"youtube_publish_at": publish_at.isoformat(), "privacy_status": privacy,
               "title": f"run {run_id}"}  # fmt: skip
    return SimpleNamespace(id=job_id, content_run_id=run_id, status="pending", job_type="upload",
                           channel_id="tapin", payload_json=json.dumps(payload), last_error="")  # fmt: skip


class PhantomSlotTests(unittest.TestCase):
    """#1558: a slot that will not be used is not taken."""

    def _taken(self, held):
        from core import spaced_queue

        repo = MagicMock()
        repo.list_active_jobs.return_value = [_job(82, 186, NOON, "unlisted")]
        log = MagicMock()
        log.list_future_scheduled.return_value = []
        with (
            patch("storage.repositories.jobs.get_job_repository", return_value=repo),
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=log),
            patch("publishing.go_public.override_held", side_effect=lambda r: r in held),
        ):
            return spaced_queue._taken_slots("tapin")

    def test_a_held_run_reserves_nothing(self):
        self.assertEqual(self._taken({186}), set())

    def test_a_run_that_will_publish_keeps_its_slot(self):
        self.assertEqual(self._taken(set()), {NOON})

    def test_the_queue_does_not_list_it(self):
        from analytics import upload_queue

        repo = MagicMock()
        repo.list_upload_jobs.return_value = [
            _job(82, 186, datetime.now(timezone.utc) + timedelta(hours=12), "unlisted")
        ]
        log = MagicMock()
        log.list_uploaded_for_channel.return_value = []
        log.list_future_scheduled.return_value = []
        with (
            patch("storage.repositories.jobs.get_job_repository", return_value=repo),
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=log),
            patch.object(upload_queue, "_logged_runs", return_value=set()),
            patch("publishing.go_public.override_held", return_value=True),
        ):
            entries = upload_queue.list_queue_entries("tapin")
        self.assertEqual([e for e in entries if e.source == "job"], [])

    def test_a_held_run_is_queued_with_no_time(self):
        from core import spaced_queue

        slot = spaced_queue.SpacedSlot(run_id=186, title="Chiefs' line", publish_at=NOON)
        record = SimpleNamespace(mp4_path="v.mp4", tags_json="[]", title="t", description="",
                                 features_json="{}")  # fmt: skip
        runs = MagicMock()
        runs.get.return_value = record
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=runs
            ),
            patch.object(
                spaced_queue, "slot_privacy", return_value="unlisted"
            ),  # held: public asked
            patch.object(
                spaced_queue, "enqueue_repurpose_jobs", return_value=SimpleNamespace(job_ids=[1])
            ) as enq,
        ):
            spaced_queue.queue_spaced_uploads([slot], channel_id="tapin")
        self.assertIsNone(enq.call_args.kwargs["youtube_publish_at"])
        self.assertEqual(enq.call_args.kwargs["privacy_status"], "unlisted")


class PassLineTests(unittest.TestCase):
    """#1559: "Sent 3 due job(s)" was printed for a pass that uploaded none."""

    def test_the_line_says_tried(self):
        from jobs import worker

        with (
            patch.object(worker, "drain_due", return_value=3),
            patch.object(worker, "_sync_metrics"),
            patch.object(worker, "_overnight_watch"),
            patch.object(worker, "_sign_in_watch"),
            patch.object(worker, "_tonight_watch"),
            patch("sys.argv", ["worker"]),
            patch("builtins.print") as said,
        ):
            worker.main()
        line = said.call_args.args[0]
        self.assertNotIn("Sent", line)
        self.assertIn("3 due upload job(s) tried", line)


if __name__ == "__main__":
    unittest.main()
