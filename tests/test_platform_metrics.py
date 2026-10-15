"""#1195: one Buffer posts query per channel, views stored, unmeasured is not zero.

No network. The recorded body goes through graphql's ``post=`` hook. The crosspost
store and the metrics store are temp files.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

RECORDED = {
    "data": {
        "posts": {
            "edges": [
                {
                    "node": {
                        "id": "p-tiktok",
                        "metricsUpdatedAt": "2026-10-15T12:00:00.000Z",
                        "metrics": [
                            {"name": "views", "type": "count", "unit": "", "value": 1200},
                            {"name": "likes", "type": "count", "unit": "", "value": 40},
                            {"name": "comments", "type": "count", "unit": "", "value": 3},
                            {"name": "shares", "type": "count", "unit": "", "value": 2},
                            {"name": "saves", "type": "count", "unit": "", "value": 1},
                            {
                                "name": "engagementRate",
                                "type": "percentage",
                                "unit": "%",
                                "value": 4.2,
                            },
                        ],
                    }
                },
                {
                    "node": {
                        "id": "p-bare",
                        "metrics": [{"name": "views", "type": "count", "unit": "", "value": 0}],
                    }
                },
            ]
        }
    }
}

NOW = datetime(2026, 10, 15, 18, 0, tzinfo=timezone.utc)


class _Resp:
    def __init__(self, body):
        self.status_code = 200
        self._body = body
        self.headers: dict[str, str] = {}

    def json(self):
        return self._body


class MetricsQueryTests(unittest.TestCase):
    def test_one_posts_query_keeps_the_status_and_buffer_names(self):
        from publishing.buffer_api import channel_post_metrics

        sent: list[dict] = []

        def post(url, **kw):
            sent.append(kw)
            return _Resp(RECORDED)

        with patch.dict(os.environ, {"BUFFER_API_KEY": "k"}):
            rows = channel_post_metrics("org", "tt1", post=post)
        query = sent[0]["json"]["query"]
        self.assertIn("metrics { name type unit value }", query)
        self.assertIn("metricsUpdatedAt", query)
        self.assertEqual(len(sent), 1)
        measured = rows[0]
        self.assertEqual(measured["id"], "p-tiktok")
        self.assertTrue(measured["measured"])
        self.assertEqual(measured["views"], 1200)
        self.assertEqual(measured["likes"], 40)
        self.assertEqual(measured["comments"], 3)
        self.assertEqual(measured["shares"], 2)
        self.assertEqual(measured["saves"], 1)
        self.assertEqual(measured["buffer"]["engagementRate"], 4.2)
        bare = rows[1]
        self.assertFalse(bare["measured"])
        self.assertIsNone(bare["views"])

    def test_find_posts_still_asks_for_no_metrics(self):
        from publishing.buffer_api import find_posts

        sent: dict = {}

        def post(url, **kw):
            sent.update(kw)
            return _Resp({"data": {"posts": {"edges": []}}})

        with patch.dict(os.environ, {"BUFFER_API_KEY": "k"}):
            find_posts("org", "tt1", post=post)
        self.assertNotIn("metrics", sent["json"]["query"])


class StoreTests(unittest.TestCase):
    def test_status_shows_views_and_a_missing_update_is_not_zero(self):
        from publishing import crosspost
        from publishing.platform_metrics import refresh

        calls: list[str] = []

        def post(url, **kw):
            calls.append(kw["json"]["variables"]["input"]["filter"]["channelIds"][0])
            body = json.loads(json.dumps(RECORDED))
            if calls[-1] == "ig1":
                body["data"]["posts"]["edges"] = [
                    {
                        "node": {
                            "id": "p-ig",
                            "metrics": [{"name": "views", "type": "count", "unit": "", "value": 0}],
                        }
                    }
                ]
            return _Resp(body)

        with (
            tempfile.TemporaryDirectory() as tmp,
            (
                patch(
                    "publishing.crosspost.CROSSPOST_TEMPLATE",
                    os.path.join(tmp, "crosspost_{channel}.json"),
                )
            ),
            patch(
                "publishing.platform_metrics.METRICS_TEMPLATE",
                os.path.join(tmp, "platform_metrics_{channel}.json"),
            ),
            patch.dict(os.environ, {"BUFFER_API_KEY": "k"}),
        ):
            crosspost.save_channels("tapin", "org1", {"tiktok": "tt1", "instagram": "ig1"})
            data = crosspost._load("tapin")
            data["posts"] = {
                "132": {
                    "title": "Topuria",
                    "tiktok": {"state": "sent", "post_id": "p-tiktok", "link": "https://tt/1"},
                    "instagram": {"state": "sent", "post_id": "p-ig", "link": "https://ig/1"},
                }
            }
            crosspost._save("tapin", data)
            refresh("tapin", post=post, now=NOW)
            self.assertEqual(calls, ["tt1", "ig1"])
            text = "\n".join(crosspost.status_lines("tapin"))
            self.assertIn("1200 views", text)
            instagram = next(
                line for line in text.splitlines() if line.strip().startswith("Instagram")
            )
            self.assertIn("not measured yet", instagram)
            self.assertNotIn("0 views", instagram)
            refresh("tapin", post=post, now=NOW)
            self.assertEqual(calls, ["tt1", "ig1"])
