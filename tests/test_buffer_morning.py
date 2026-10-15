"""#1199: the morning names a Buffer error, a paused queue, a disconnected
channel, and a request count near the daily cap.

Not configured: the line is absent and nothing is logged at warning.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch


class _Resp:
    def __init__(self, body):
        self.status_code = 200
        self._body = body
        self.headers: dict[str, str] = {}

    def json(self):
        return self._body


class MorningBufferTests(unittest.TestCase):
    def test_each_graphql_call_is_counted(self):
        from publishing.buffer_api import graphql, requests_made

        before = requests_made()

        def post(url, **kw):
            return _Resp({"data": {"account": {"organizations": []}}})

        with patch.dict(os.environ, {"BUFFER_API_KEY": "k"}):
            graphql("query { account { organizations { id } } }", post=post)
        self.assertEqual(requests_made(), before + 1)

    def test_unconfigured_is_absent_and_adds_no_warning(self):
        from publishing.buffer_api import morning_line

        with (
            patch.dict(os.environ, {"BUFFER_API_KEY": ""}),
            self.assertNoLogs("content_machine.publishing.buffer_api", level="WARNING"),
        ):
            self.assertEqual(morning_line("tapin"), "")

    def test_the_morning_names_an_error_a_paused_queue_and_the_budget(self):
        from publishing import crosspost
        from publishing.buffer_api import morning_line

        rows = [
            {
                "name": "tapinmedia47",
                "service": "tiktok",
                "isQueuePaused": True,
                "isDisconnected": False,
            },
            {
                "name": "tapinmedia03",
                "service": "instagram",
                "isQueuePaused": False,
                "isDisconnected": True,
            },
        ]
        with (
            tempfile.TemporaryDirectory() as tmp,
            (
                patch(
                    "publishing.crosspost.CROSSPOST_TEMPLATE",
                    os.path.join(tmp, "crosspost_{channel}.json"),
                )
            ),
            patch("publishing.buffer_api.channels", return_value=rows),
            patch("publishing.buffer_api.requests_made", return_value=210),
            patch.dict(os.environ, {"BUFFER_API_KEY": "k"}),
        ):
            crosspost.save_channels("tapin", "org1", {"tiktok": "tt1", "instagram": "ig1"})
            data = crosspost._load("tapin")
            data["posts"] = {
                "132": {"tiktok": {"state": "error", "error": "Video could not be read"}}
            }
            crosspost._save("tapin", data)
            line = morning_line("tapin")
        self.assertIn("Video could not be read", line)
        self.assertIn("tapinmedia47 queue paused", line)
        self.assertIn("tapinmedia03 disconnected", line)
        self.assertIn("210/250", line)

    def test_a_healthy_buffer_adds_no_line_and_no_warning(self):
        from publishing import crosspost
        from publishing.buffer_api import morning_line

        with (
            tempfile.TemporaryDirectory() as tmp,
            (
                patch(
                    "publishing.crosspost.CROSSPOST_TEMPLATE",
                    os.path.join(tmp, "crosspost_{channel}.json"),
                )
            ),
            patch(
                "publishing.buffer_api.channels",
                return_value=[{"name": "ok", "isQueuePaused": False, "isDisconnected": False}],
            ),
            patch("publishing.buffer_api.requests_made", return_value=3),
            patch.dict(os.environ, {"BUFFER_API_KEY": "k"}),
            self.assertNoLogs("content_machine.publishing.buffer_api", level="WARNING"),
        ):
            crosspost.save_channels("tapin", "org1", {"tiktok": "tt1"})
            self.assertEqual(morning_line("tapin"), "")

    def test_a_later_process_sees_todays_calls_and_not_yesterdays(self):
        from publishing.buffer_api import graphql, morning_line, requests_made

        today = datetime.now(timezone.utc).date().isoformat()
        yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()

        def post(url, **kw):
            return _Resp({"data": {"account": {"organizations": []}}})

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch(
                "publishing.crosspost.CROSSPOST_TEMPLATE",
                os.path.join(tmp, "crosspost_{channel}.json"),
            ),
            patch(
                "publishing.buffer_api.REQUESTS_FILE",
                os.path.join(tmp, "buffer_requests.json"),
                create=True,
            ),
            patch("publishing.buffer_api._REQUESTS", 0),
            patch.dict(os.environ, {"BUFFER_API_KEY": "k"}),
        ):
            path = os.path.join(tmp, "buffer_requests.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"day": today, "count": 210}, handle)
            self.assertIn("210/250", morning_line("tapin"))

            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"day": yesterday, "count": 210}, handle)
            self.assertNotIn("Buffer requests", morning_line("tapin"))

            before = requests_made()
            graphql("query { account { organizations { id } } }", post=post)
            self.assertEqual(requests_made(), before + 1)
