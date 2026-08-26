"""#133 .ics of scheduled publishes — written beside HTML dumps, not under data/."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from storage.repositories.publish_log import PublishLogRecord


class TestPublishIcs(unittest.TestCase):
    def test_writes_vevent_next_to_html_dumps(self):
        from core.publish_ics import write_scheduled_ics

        when = datetime.now(timezone.utc) + timedelta(days=2)
        log = PublishLogRecord(
            id=9,
            content_run_id=9,
            channel_id="tapin",
            youtube_video_id="abc",
            status="scheduled",
            published_at=when,
            detail="GTA 6 leak scheduled",
        )
        repo = MagicMock()
        repo.list_future_scheduled.return_value = [log]
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.dict(os.environ, {"CONTENT_HTML_DIR": tmp}, clear=False),
                patch(
                    "storage.repositories.publish_log.get_publish_log_repository",
                    return_value=repo,
                ),
            ):
                path = write_scheduled_ics("tapin")
            self.assertTrue(path.startswith(tmp))
            self.assertTrue(path.endswith(".ics"))
            self.assertNotIn(os.path.join("data", ""), path.replace("/", os.sep))
            with open(path, encoding="utf-8") as fh:
                body = fh.read()
        self.assertIn("BEGIN:VCALENDAR", body)
        self.assertIn("BEGIN:VEVENT", body)
        self.assertIn("GTA 6 leak", body)

    def test_ops_command_is_registered(self):
        from scripts.ops import COMMANDS

        self.assertIn("publish-ics", COMMANDS)


if __name__ == "__main__":
    unittest.main()
