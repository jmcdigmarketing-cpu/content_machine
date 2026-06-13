import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from storage.repositories.publish_log import PublishLogRecord
from youtube.thumbnails import (
    is_thumbnail_upload_enabled,
    maybe_upload_thumbnail,
    resolve_thumbnail_path,
    set_video_thumbnail,
)
from youtube.upload import UploadRequest, upload_video


class TestYouTubeThumbnails(unittest.TestCase):
    def test_resolve_explicit_path(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(b"x")
            path = tmp.name
        try:
            got = resolve_thumbnail_path(explicit_path=path)
            self.assertEqual(got, path)
        finally:
            os.unlink(path)

    def test_set_video_thumbnail_calls_api(self):
        mock_service = MagicMock()
        fd, path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        try:
            with open(path, "wb") as f:
                f.write(b"fakejpeg")
            with (
                patch("youtube.thumbnails.has_quota_for_thumbnail", return_value=True),
                patch("youtube.thumbnails.record_thumbnail_usage"),
                patch("youtube.thumbnails.MediaFileUpload"),
            ):
                result = set_video_thumbnail(mock_service, "vid1", path)
        finally:
            os.unlink(path)

        self.assertEqual(result.status, "set")
        mock_service.thumbnails.return_value.set.assert_called_once()

    def test_upload_calls_thumbnails_set_on_success(self):
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

        fd_v, video_path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd_v)
        fd_t, thumb_path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd_t)
        with open(video_path, "wb") as f:
            f.write(b"fake")
        with open(thumb_path, "wb") as f:
            f.write(b"thumb")

        try:
            with (
                patch("publishing.youtube_publisher.is_youtube_configured", return_value=True),
                patch("publishing.youtube_publisher.has_quota_for_upload", return_value=True),
                patch(
                    "publishing.youtube_publisher.get_youtube_service", return_value=mock_service
                ),
                patch(
                    "publishing.youtube_publisher.get_publish_log_repository",
                    return_value=mock_repo,
                ),
                patch("publishing.youtube_publisher.record_upload_usage"),
                patch("publishing.youtube_publisher.MediaFileUpload"),
                patch("youtube.thumbnails.MediaFileUpload"),
                patch("youtube.thumbnails.has_quota_for_thumbnail", return_value=True),
                patch("youtube.thumbnails.record_thumbnail_usage"),
            ):
                result = upload_video(
                    UploadRequest(
                        file_path=video_path,
                        title="Title",
                        description="Body",
                        thumbnail_path=thumb_path,
                    ),
                    channel_id="tapin",
                    content_run_id=5,
                )
        finally:
            os.unlink(video_path)
            os.unlink(thumb_path)

        self.assertEqual(result.status, "uploaded")
        self.assertEqual(result.thumbnail_status, "set")
        mock_service.thumbnails.return_value.set.assert_called_once()

    def test_thumbnail_skipped_when_disabled(self):
        with patch.dict(os.environ, {"YOUTUBE_THUMBNAIL_UPLOAD": "off"}):
            self.assertFalse(is_thumbnail_upload_enabled())
            mock_service = MagicMock()
            result = maybe_upload_thumbnail(
                mock_service,
                video_id="v",
                thumbnail_path="/nonexistent.jpg",
            )
        self.assertEqual(result.status, "skipped")
        mock_service.thumbnails.return_value.set.assert_not_called()


if __name__ == "__main__":
    unittest.main()
