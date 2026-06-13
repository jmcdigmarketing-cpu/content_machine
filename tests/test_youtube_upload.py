import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from storage.repositories.publish_log import PublishLogRecord
from youtube.upload import (
    UploadRequest,
    build_video_status,
    upload_video,
)


class TestYouTubeUpload(unittest.TestCase):
    def test_build_video_status_scheduled_publish(self):
        future = datetime.now(timezone.utc) + timedelta(hours=24)
        status = build_video_status(
            UploadRequest(
                file_path="x.mp4",
                title="T",
                description="D",
                privacy_status="public",
                publish_at=future,
            )
        )
        self.assertEqual(status["privacyStatus"], "private")
        self.assertIn("publishAt", status)

    def test_not_configured_without_oauth(self):
        mock_repo = MagicMock()
        mock_repo.create.return_value = PublishLogRecord(
            id=1,
            content_run_id=1,
            channel_id="tapin",
            status="not_configured",
        )
        with (
            patch("publishing.youtube_publisher.is_youtube_configured", return_value=False),
            patch(
                "publishing.youtube_publisher.get_publish_log_repository", return_value=mock_repo
            ),
        ):
            result = upload_video(
                UploadRequest(
                    file_path="output/video/test.mp4",
                    title="Test",
                    description="Desc",
                ),
                channel_id="tapin",
                content_run_id=1,
            )
        self.assertEqual(result.status, "not_configured")
        self.assertIsNone(result.video_id)

    def test_invalid_file_when_configured(self):
        with patch("publishing.youtube_publisher.is_youtube_configured", return_value=True):
            result = upload_video(
                UploadRequest(
                    file_path="missing_file_xyz.mp4",
                    title="Test",
                    description="Desc",
                ),
                channel_id="tapin",
            )
        self.assertEqual(result.status, "invalid_file")

    def test_idempotent_skip_when_already_uploaded(self):
        existing = PublishLogRecord(
            id=3,
            content_run_id=10,
            channel_id="tapin",
            youtube_video_id="vid123",
            status="uploaded",
            idempotency_key="run:tapin:10",
        )
        mock_repo = MagicMock()
        mock_repo.find_by_idempotency.return_value = existing

        with (
            patch("publishing.youtube_publisher.is_youtube_configured", return_value=True),
            patch(
                "publishing.youtube_publisher.get_publish_log_repository", return_value=mock_repo
            ),
            patch("publishing.youtube_publisher.maybe_upload_thumbnail") as mock_thumb,
        ):
            mock_thumb.return_value = MagicMock(status="skipped", detail="")
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp.write(b"fake")
                path = tmp.name
            try:
                result = upload_video(
                    UploadRequest(file_path=path, title="T", description="D"),
                    channel_id="tapin",
                    content_run_id=10,
                )
            finally:
                os.unlink(path)

        self.assertEqual(result.status, "uploaded")
        self.assertEqual(result.video_id, "vid123")
        self.assertIn("Idempotent", result.detail or "")

    def test_quota_exceeded_blocks_upload(self):
        mock_repo = MagicMock()
        mock_repo.find_by_idempotency.return_value = None

        with (
            patch("publishing.youtube_publisher.is_youtube_configured", return_value=True),
            patch("publishing.youtube_publisher.has_quota_for_upload", return_value=False),
            patch(
                "publishing.youtube_publisher.get_publish_log_repository", return_value=mock_repo
            ),
        ):
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp.write(b"fake")
                path = tmp.name
            try:
                result = upload_video(
                    UploadRequest(file_path=path, title="T", description="D"),
                    channel_id="tapin",
                    content_run_id=5,
                )
            finally:
                os.unlink(path)

        self.assertEqual(result.status, "quota_exceeded")

    def test_successful_upload_records_quota_and_publish_log(self):
        mock_repo = MagicMock()
        mock_repo.find_by_idempotency.return_value = None
        mock_repo.create.return_value = PublishLogRecord(
            id=7,
            content_run_id=5,
            channel_id="tapin",
            status="pending",
        )

        mock_insert = MagicMock()
        mock_insert.next_chunk.return_value = (None, {"id": "yt999"})
        mock_service = MagicMock()
        mock_service.videos.return_value.insert.return_value = mock_insert

        with (
            patch("publishing.youtube_publisher.is_youtube_configured", return_value=True),
            patch("publishing.youtube_publisher.has_quota_for_upload", return_value=True),
            patch("publishing.youtube_publisher.get_youtube_service", return_value=mock_service),
            patch(
                "publishing.youtube_publisher.get_publish_log_repository", return_value=mock_repo
            ),
            patch("publishing.youtube_publisher.record_upload_usage") as mock_quota,
            patch("publishing.youtube_publisher.MediaFileUpload"),
            patch("publishing.youtube_publisher.maybe_upload_thumbnail") as mock_thumb,
        ):
            mock_thumb.return_value = MagicMock(status="not_found", detail="")
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp.write(b"fake")
                path = tmp.name
            try:
                result = upload_video(
                    UploadRequest(file_path=path, title="Title", description="Body"),
                    channel_id="tapin",
                    content_run_id=5,
                )
            finally:
                os.unlink(path)

        self.assertEqual(result.status, "uploaded")
        self.assertEqual(result.video_id, "yt999")
        mock_quota.assert_called_once()
        self.assertGreaterEqual(mock_repo.update.call_count, 1)
        first_update = mock_repo.update.call_args_list[0][0][1]
        self.assertEqual(first_update.get("youtube_video_id"), "yt999")

    def test_pending_healed_without_reupload(self):
        pending = PublishLogRecord(
            id=9,
            content_run_id=11,
            channel_id="tapin",
            youtube_video_id="",
            status="pending",
            idempotency_key="run:tapin:11",
        )
        mock_repo = MagicMock()
        mock_repo.find_by_idempotency.return_value = pending

        mock_service = MagicMock()
        with (
            patch("publishing.youtube_publisher.is_youtube_configured", return_value=True),
            patch("publishing.youtube_publisher.has_quota_for_upload", return_value=True),
            patch("publishing.youtube_publisher.get_youtube_service", return_value=mock_service),
            patch("publishing.youtube_publisher._find_video_on_channel", return_value="healed123"),
            patch(
                "publishing.youtube_publisher.get_publish_log_repository", return_value=mock_repo
            ),
            patch("publishing.youtube_publisher.maybe_upload_thumbnail") as mock_thumb,
        ):
            mock_thumb.return_value = MagicMock(status="skipped", detail="")
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp.write(b"fake")
                path = tmp.name
            try:
                result = upload_video(
                    UploadRequest(file_path=path, title="My Title", description="D"),
                    channel_id="tapin",
                    content_run_id=11,
                )
            finally:
                os.unlink(path)

        self.assertEqual(result.video_id, "healed123")
        self.assertIn("Healed", result.detail or "")
        mock_service.videos.return_value.insert.assert_not_called()


if __name__ == "__main__":
    unittest.main()
