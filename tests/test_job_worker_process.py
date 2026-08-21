"""jobs.worker.process_one quota gate + _defer_for_quota retry accounting.

Roadmap coverage wave: if process_one inverts the quota gate it burns ~1,600 YouTube
units per attempt. A quota deferral that consumes a retry silently exhausts
max_attempts over a few blocked days and the video never posts.

No real DB / data/ / config/secrets/ (tests/CLAUDE.md).
"""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch

from jobs.worker import _defer_for_quota, _process_render, process_one
from storage.repositories.jobs import JOB_FAILED, JOB_PENDING
from youtube.upload import UploadResult


class TestProcessOneQuotaGate(unittest.TestCase):
    def _repo(self) -> MagicMock:
        repo = MagicMock()
        repo.reclaim_stuck_running.return_value = 0
        repo.claim_next.return_value = None
        return repo

    def test_exhausted_claims_only_render_jobs(self):
        repo = self._repo()
        upload = MagicMock()
        render = MagicMock()
        with (
            patch("jobs.worker.get_job_repository", return_value=repo),
            patch("apis.youtube_quota.has_quota_for_upload", return_value=False),
            patch.dict("jobs.worker._HANDLERS", {"upload": upload, "render": render}, clear=False),
        ):
            self.assertFalse(process_one())
        repo.claim_next.assert_called_once_with(job_type="render")
        upload.assert_not_called()

    def test_available_claims_unfiltered(self):
        repo = self._repo()
        with (
            patch("jobs.worker.get_job_repository", return_value=repo),
            patch("apis.youtube_quota.has_quota_for_upload", return_value=True),
        ):
            self.assertFalse(process_one())
        repo.claim_next.assert_called_once_with()

    def test_unknown_job_type_fails_and_returns_true(self):
        repo = self._repo()
        job = MagicMock(id=11, job_type="nope")
        repo.claim_next.return_value = job
        with (
            patch("jobs.worker.get_job_repository", return_value=repo),
            patch("apis.youtube_quota.has_quota_for_upload", return_value=True),
        ):
            self.assertTrue(process_one())
        repo.update.assert_called_once_with(
            11, {"status": JOB_FAILED, "last_error": "Unknown job_type: nope"}
        )

    def test_handler_raise_marks_failed_and_survives(self):
        repo = self._repo()
        job = MagicMock(id=5, job_type="render")
        repo.claim_next.return_value = job
        boom = MagicMock(side_effect=RuntimeError("ffmpeg missing"))
        with (
            patch("jobs.worker.get_job_repository", return_value=repo),
            patch("apis.youtube_quota.has_quota_for_upload", return_value=True),
            patch.dict("jobs.worker._HANDLERS", {"render": boom}, clear=False),
        ):
            self.assertTrue(process_one())
        boom.assert_called_once_with(job)
        args = repo.update.call_args[0]
        self.assertEqual(args[0], 5)
        self.assertEqual(args[1]["status"], JOB_FAILED)
        self.assertIn("ffmpeg missing", args[1]["last_error"])

    def test_no_job_returns_false(self):
        repo = self._repo()
        with (
            patch("jobs.worker.get_job_repository", return_value=repo),
            patch("apis.youtube_quota.has_quota_for_upload", return_value=True),
        ):
            self.assertFalse(process_one())

    def test_stuck_reclaim_runs_before_claim(self):
        repo = self._repo()
        repo.reclaim_stuck_running.return_value = 2
        with (
            patch("jobs.worker.get_job_repository", return_value=repo),
            patch("apis.youtube_quota.has_quota_for_upload", return_value=True),
        ):
            process_one()
        reclaim = call.reclaim_stuck_running(45)
        claim = call.claim_next()
        self.assertLess(repo.mock_calls.index(reclaim), repo.mock_calls.index(claim))


class TestDeferForQuota(unittest.TestCase):
    def test_quota_defer_does_not_consume_a_retry(self):
        job = MagicMock(id=9, attempts=2, max_attempts=3, content_run_id=4)
        result = UploadResult(video_id=None, status="quota_exceeded", detail="daily cap")
        retry_at = datetime.now(timezone.utc) + timedelta(hours=6)
        repo = MagicMock()
        with (
            patch("jobs.worker.get_job_repository", return_value=repo),
            patch("apis.youtube_quota.get_usage_summary", return_value={"remaining": 12}),
            patch("apis.youtube_quota.next_quota_retry_at", return_value=retry_at),
        ):
            self.assertTrue(_defer_for_quota(job, result))
        repo.update.assert_called_once()
        payload = repo.update.call_args[0][1]
        self.assertEqual(payload["status"], JOB_PENDING)
        self.assertEqual(payload["attempts"], 1)  # 2 - 1, retry not consumed
        self.assertEqual(payload["scheduled_at"], retry_at)
        self.assertIn("daily cap", payload["last_error"])

    def test_non_quota_status_is_a_no_op(self):
        job = MagicMock(id=1, attempts=1)
        result = UploadResult(video_id=None, status="upload_failed", detail="timeout")
        repo = MagicMock()
        with patch("jobs.worker.get_job_repository", return_value=repo):
            self.assertFalse(_defer_for_quota(job, result))
        repo.update.assert_not_called()


class TestRenderQueueGate(unittest.TestCase):
    def test_low_grade_fails_job_without_ffmpeg(self):
        job = MagicMock(id=7, content_run_id=42, channel_id="tapin", payload_json="{}")
        job.attempts = 1
        job.max_attempts = 3
        repo = MagicMock()
        with (
            patch("jobs.worker.get_job_repository", return_value=repo),
            patch(
                "core.render_gate.block_reason_for_run",
                return_value="unattended render gate: report card C (need >= B)",
            ),
            patch("jobs.worker.run_media_only") as render,
        ):
            _process_render(job)
        render.assert_not_called()
        repo.update.assert_called_once()
        payload = repo.update.call_args[0][1]
        self.assertEqual(payload["status"], JOB_FAILED)
        self.assertIn("report card C", payload["last_error"])

    def test_pass_still_renders(self):
        job = MagicMock(id=8, content_run_id=43, channel_id="tapin", payload_json="{}")
        job.attempts = 1
        job.max_attempts = 3
        repo = MagicMock()
        with (
            patch("jobs.worker.get_job_repository", return_value=repo),
            patch("core.render_gate.block_reason_for_run", return_value=None),
            patch("jobs.worker.run_media_only", return_value=("a.mp3", "b.mp4", "")) as render,
        ):
            _process_render(job)
        render.assert_called_once()
        payload = repo.update.call_args[0][1]
        self.assertEqual(payload["status"], "completed")

    def test_human_presence_blocks_render(self):
        job = MagicMock(id=9, content_run_id=44, channel_id="tapin", payload_json="{}")
        job.attempts = 1
        job.max_attempts = 3
        repo = MagicMock()
        with (
            patch("jobs.worker.get_job_repository", return_value=repo),
            patch("core.render_gate.block_reason_for_run", return_value=None),
            patch(
                "core.human_presence.unattended_render_block_reason",
                return_value="human-presence gate: no operator heartbeat",
            ),
            patch("jobs.worker.run_media_only") as render,
        ):
            _process_render(job)
        render.assert_not_called()
        self.assertEqual(repo.update.call_args[0][1]["status"], JOB_FAILED)

    def test_rpm_gate_defers_upload_without_consuming_retry(self):
        job = MagicMock(id=10, attempts=2, max_attempts=3, channel_id="tapin", payload_json="{}")
        repo = MagicMock()
        retry = datetime.now(timezone.utc) + timedelta(days=7)
        with (
            patch("jobs.worker.get_job_repository", return_value=repo),
            patch(
                "core.rpm_cost_gate.rpm_cost_gate_reason",
                return_value="rpm-cost gate: trailing RPM $0.10/1k views < fully-loaded $0.31/video",
            ),
            patch("core.rpm_cost_gate.next_retry_utc", return_value=retry),
            patch("publishing.registry.get_publisher") as pub,
        ):
            from jobs.worker import _process_upload

            _process_upload(job)
        pub.assert_not_called()
        payload = repo.update.call_args[0][1]
        self.assertEqual(payload["status"], JOB_PENDING)
        self.assertEqual(payload["attempts"], 1)
        self.assertEqual(payload["scheduled_at"], retry)


if __name__ == "__main__":
    unittest.main()
