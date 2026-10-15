"""#1196: domain, length and post time per feed. Under four samples, YouTube's hour.

The metrics store is a temp file. No network.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

NOW = datetime(2026, 10, 15, 16, 0, tzinfo=timezone.utc)


def _rows(hour: int, n: int, *, domain: str = "ufc", length: str = "2") -> dict:
    rows = {}
    for i in range(n):
        rows[str(200 + i)] = {
            "tiktok": {
                "measured": True,
                "views": 1000 + i,
                "hour": hour,
                "domain": domain,
                "length": length,
            }
        }
    return {"fetched_on": "2026-10-15", "rows": rows}


class RecommendTests(unittest.TestCase):
    def test_four_tiktok_samples_move_the_hour_and_two_stay_on_youtube(self):
        from publishing.crosspost import _next_due
        from publishing.platform_metrics import _save
        from publishing.platform_recommend import learning_line

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch(
                "publishing.platform_metrics.METRICS_TEMPLATE",
                os.path.join(tmp, "platform_metrics_{channel}.json"),
            ),
        ):
            _save("tapin", _rows(21, 4))
            due, note = _next_due("tapin", "topic", "tiktok", {}, NOW)
            self.assertEqual(due.astimezone(timezone.utc).hour, 21)
            self.assertIn("TikTok", note)
            self.assertNotIn("YouTube", note)
            self.assertIn("ufc", learning_line("tapin", "tiktok"))
            self.assertIn("2", learning_line("tapin", "tiktok"))

            _save("tapin", _rows(21, 2))
            stayed, stayed_note = _next_due("tapin", "topic", "tiktok", {}, NOW)
            self.assertNotEqual(stayed.astimezone(timezone.utc).hour, 21)
            self.assertIn("YouTube", stayed_note)
            self.assertIn("YouTube", learning_line("tapin", "tiktok"))

    def test_the_store_writes_the_hour_the_recommender_reads(self):
        from publishing import crosspost
        from publishing.platform_metrics import get_row, refresh

        def post(url, **kw):
            return SimpleNamespace(
                status_code=200,
                headers={},
                json=lambda: {
                    "data": {
                        "posts": {
                            "edges": [
                                {
                                    "node": {
                                        "id": "p1",
                                        "metricsUpdatedAt": "2026-10-15T21:05:00.000Z",
                                        "metrics": [
                                            {
                                                "name": "views",
                                                "type": "count",
                                                "unit": "",
                                                "value": 50,
                                            }
                                        ],
                                    }
                                }
                            ]
                        }
                    }
                },
            )

        run = SimpleNamespace(
            input_topic="hello",
            timings_json='{"length_preset": "2"}',
        )
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
            patch("publishing.crosspost._content_run", return_value=run),
            patch(
                "core.run_features.load_features",
                return_value={"domains": {"effective": "ufc"}},
            ),
            patch.dict(os.environ, {"BUFFER_API_KEY": "k"}),
        ):
            crosspost.save_channels("tapin", "org", {"tiktok": "tt1"})
            data = crosspost._load("tapin")
            data["posts"] = {
                "7": {
                    "tiktok": {
                        "state": "sent",
                        "post_id": "p1",
                        "sent_at": "2026-10-15T21:05:00+00:00",
                    }
                }
            }
            crosspost._save("tapin", data)
            refresh("tapin", post=post, now=NOW)
            row = get_row("tapin", "7", "tiktok")
        self.assertEqual(row["hour"], 21)
        self.assertEqual(row["domain"], "ufc")
        self.assertEqual(row["length"], "2")

    def test_send_due_uses_that_datetime(self):
        from publishing.crosspost import send_due

        public: list[tuple[int, str]] = []
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
            patch("publishing.crosspost._public_runs", side_effect=lambda ch: list(public)),
            patch(
                "publishing.crosspost._content_run",
                return_value=SimpleNamespace(
                    id=113,
                    input_topic="t",
                    selected_topic="t",
                    title="t",
                    mp4_path=os.path.join(tmp, "v.mp4"),
                    description="d",
                    tags_json="[]",
                ),
            ),
            patch("publishing.crosspost._duration", return_value=40.0),
            patch(
                "publishing.buffer_api.create_video_post",
                return_value={"id": "p", "status": "scheduled"},
            ),
            patch("publishing.buffer_api.configured", return_value=True),
            patch("publishing.buffer_api.find_posts", return_value=[]),
            patch("publishing.video_host.configured", return_value=True),
            patch("publishing.video_host.host", return_value="https://r2/v.mp4"),
            patch("publishing.video_host.object_key", return_value="k"),
            patch.dict(os.environ, {"CROSSPOST_AUTO": "true", "BUFFER_API_KEY": "k"}),
        ):
            from publishing.crosspost import save_channels, switch_on
            from publishing.platform_metrics import _save

            open(os.path.join(tmp, "v.mp4"), "wb").close()
            save_channels("tapin", "org", {"tiktok": "tt1", "instagram": "ig1"})
            switch_on("tapin", now=NOW - timedelta(days=1))
            public.append((113, "yt"))
            _save("tapin", _rows(21, 4))
            lines = send_due("tapin", apply=False, now=NOW)
        tiktok = next(line for line in lines if "TikTok" in line and "would schedule" in line)
        self.assertIn("21:", tiktok)
        self.assertNotIn("YouTube", tiktok)
