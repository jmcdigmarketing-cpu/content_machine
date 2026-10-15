"""#1199: the morning names a Buffer error, a paused queue, a disconnected
channel, and a request count near the daily cap.

Not configured: the line is absent and nothing is logged at warning.
"""

from __future__ import annotations

import os
import tempfile
import unittest
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
