"""#101 YouTube captions.insert on the publish path — mocked Data API, fail-open."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from storage.repositories.publish_log import PublishLogRecord
from youtube.upload import UploadRequest, upload_video


class TestCaptionTrackUpload(unittest.TestCase):
    def test_captions_insert_called_when_track_exists(self):
        from youtube.captions import maybe_upload_captions

        mock_service = MagicMock()
        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as tmp:
            tmp.write(b"1\n00:00:00,000 --> 00:00:01,000\nHi\n")
            path = tmp.name
        try:
            with patch("youtube.captions.MediaFileUpload"):
                result = maybe_upload_captions(mock_service, video_id="vid1", caption_path=path)
        finally:
            os.unlink(path)
        self.assertEqual(result.status, "set")
        mock_service.captions.return_value.insert.assert_called_once()

    def test_no_track_file_fails_open(self):
        from youtube.captions import maybe_upload_captions

        mock_service = MagicMock()
        result = maybe_upload_captions(
            mock_service, video_id="vid1", caption_path="missing_captions.srt"
        )
        self.assertEqual(result.status, "not_found")
        mock_service.captions.assert_not_called()

    def test_publish_path_uploads_caption_track(self):
        mock_repo = MagicMock()
        mock_repo.find_by_idempotency.return_value = None
        mock_repo.create.return_value = PublishLogRecord(
            id=7, content_run_id=5, channel_id="tapin", status="pending"
        )
        mock_insert = MagicMock()
        mock_insert.next_chunk.return_value = (None, {"id": "yt999"})
        mock_service = MagicMock()
        mock_service.videos.return_value.insert.return_value = mock_insert

        fd_v, video_path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd_v)
        fd_c, caption_path = tempfile.mkstemp(suffix=".srt")
        os.close(fd_c)
        with open(video_path, "wb") as fh:
            fh.write(b"fake")
        with open(caption_path, "w", encoding="utf-8") as fh:
            fh.write("1\n00:00:00,000 --> 00:00:01,000\nHi\n")
        try:
            with (
                patch("publishing.youtube_publisher.is_youtube_configured", return_value=True),
                patch("publishing.youtube_publisher.has_quota_for_upload", return_value=True),
                patch(
                    "publishing.youtube_publisher.get_youtube_service",
                    return_value=mock_service,
                ),
                patch(
                    "publishing.youtube_publisher.get_publish_log_repository",
                    return_value=mock_repo,
                ),
                patch("publishing.youtube_publisher.record_upload_usage"),
                patch("publishing.youtube_publisher.maybe_upload_thumbnail") as thumb,
                patch("publishing.youtube_publisher.MediaFileUpload"),
                patch("youtube.captions.MediaFileUpload"),
            ):
                thumb.return_value = MagicMock(status="skipped", detail="")
                result = upload_video(
                    UploadRequest(
                        file_path=video_path,
                        title="T",
                        description="D",
                        caption_path=caption_path,
                    ),
                    channel_id="tapin",
                    content_run_id=5,
                )
        finally:
            os.unlink(video_path)
            os.unlink(caption_path)
        self.assertEqual(result.status, "uploaded")
        mock_service.captions.return_value.insert.assert_called_once()


if __name__ == "__main__":
    unittest.main()
