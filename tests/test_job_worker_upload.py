import unittest
from unittest.mock import MagicMock, patch

from jobs.worker import _finalize_upload_job
from storage.repositories.jobs import JOB_COMPLETED, JOB_FAILED, JOB_PENDING
from youtube.upload import (
    UPLOAD_STATUS_TERMINAL_FAILURE,
    UploadResult,
)


class TestUploadJobLifecycle(unittest.TestCase):
    def test_not_implemented_marks_failed_not_completed(self):
        job = MagicMock(id=7, attempts=1, max_attempts=3, content_run_id=1)
        result = UploadResult(
            video_id=None,
            status="not_implemented",
            detail="Phase 8",
        )
        repo = MagicMock()

        with patch("jobs.worker.get_job_repository", return_value=repo):
            _finalize_upload_job(job, result)

        repo.update.assert_called_once()
        args = repo.update.call_args[0]
        self.assertEqual(args[0], 7)
        self.assertEqual(args[1]["status"], JOB_FAILED)

    def test_not_configured_is_terminal_failure(self):
        self.assertIn("not_configured", UPLOAD_STATUS_TERMINAL_FAILURE)

    def test_scheduled_completes_job(self):
        job = MagicMock(id=3, attempts=1, max_attempts=3, content_run_id=5)
        result = UploadResult(video_id="abc123", status="scheduled", detail="YouTube scheduled")
        repo = MagicMock()

        with (
            patch("jobs.worker.get_job_repository", return_value=repo),
            patch("jobs.worker.get_content_run_repository") as runs,
        ):
            runs.return_value.update = MagicMock()
            _finalize_upload_job(job, result)

        self.assertEqual(repo.update.call_args[0][1]["status"], JOB_COMPLETED)
        runs.return_value.update.assert_called_once()
        self.assertEqual(runs.return_value.update.call_args[0][1]["status"], "scheduled")

    def test_uploaded_completes(self):
        job = MagicMock(id=2, attempts=1, max_attempts=3, content_run_id=5)
        result = UploadResult(video_id="abc123", status="uploaded", detail="ok")
        repo = MagicMock()

        with (
            patch("jobs.worker.get_job_repository", return_value=repo),
            patch("jobs.worker.get_content_run_repository") as runs,
        ):
            runs.return_value.update = MagicMock()
            _finalize_upload_job(job, result)

        self.assertEqual(repo.update.call_args[0][1]["status"], JOB_COMPLETED)


if __name__ == "__main__":
    unittest.main()
