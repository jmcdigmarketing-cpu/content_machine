"""jobs.worker.process_one quota gate + _defer_for_quota retry accounting.

Roadmap coverage wave: if process_one inverts the quota gate it burns ~1,600 YouTube
units per attempt. A quota deferral that consumes a retry silently exhausts
max_attempts over a few blocked days and the video never posts.

No real DB / data/ / config/secrets/ (tests/CLAUDE.md).
"""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch

from jobs.worker import _defer_for_quota, process_one
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


if __name__ == "__main__":
    unittest.main()
