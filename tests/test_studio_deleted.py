"""#106 Studio-deleted detection cancels publish_log — mocked videos.list."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from storage.repositories.publish_log import PublishLogRecord


def _log(log_id, video_id, status="uploaded"):
    return PublishLogRecord(
        id=log_id,
        content_run_id=log_id,
        channel_id="tapin",
        youtube_video_id=video_id,
        status=status,
        published_at=datetime.now(timezone.utc),
    )


class TestStudioDeleted(unittest.TestCase):
    def test_missing_video_cancels_publish_log(self):
        from youtube.studio_deleted import detect_studio_deleted

        kept = _log(1, "keep1")
        gone = _log(2, "gone1")
        repo = MagicMock()
        repo.list_uploaded_for_channel.return_value = [kept, gone]
        service = MagicMock()
        service.videos.return_value.list.return_value.execute.return_value = {
            "items": [{"id": "keep1"}]
        }
        with patch(
            "storage.repositories.publish_log.get_publish_log_repository",
            return_value=repo,
        ):
            cancelled = detect_studio_deleted("tapin", service=service)
        self.assertEqual([c.youtube_video_id for c in cancelled], ["gone1"])
        repo.update.assert_called()
        update_id = repo.update.call_args.args[0]
        payload = repo.update.call_args.args[1]
        self.assertEqual(update_id, 2)
        self.assertEqual(payload["status"], "cancelled")

    def test_ops_command_is_registered(self):
        from scripts.ops import COMMANDS

        self.assertIn("studio-deleted", COMMANDS)


if __name__ == "__main__":
    unittest.main()
