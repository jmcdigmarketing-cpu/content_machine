"""#1121 and #1125: a YouTube 500, or a 404 from every channel, is the feed.

`ops competitor-health` called HTTP 500 "dead or wrong UC id". The same day the
feed answered 404 for every channel and the sync spent 3 Data API units each.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from analytics.youtube_rss import FeedProbe

_A = "UCBJycsmduvYEL83R_U4JriQ"
_B = "UCXuqSBlHAE6Xw-yeJA0Tunw"


class FeedWordingTests(unittest.TestCase):
    def test_a_500_is_youtubes_error_not_a_dead_id(self):
        from core.competitor_health import inspect_competitors, render_report

        channels = [{"id": _A, "label": "MKBHD"}]
        report = inspect_competitors(
            "tapin",
            channels=channels,
            fetch=lambda _cid: FeedProbe([], 500),
        )
        text = render_report(report)
        self.assertFalse(report.ok)
        self.assertIn("500", text)
        self.assertNotIn("dead or wrong", text)

    def test_a_200_with_no_videos_is_still_a_dead_id(self):
        from core.competitor_health import inspect_competitors

        report = inspect_competitors(
            "tapin",
            channels=[{"id": _A, "label": "MKBHD"}],
            fetch=lambda _cid: FeedProbe([], 200),
        )
        self.assertIn("dead or wrong", report.checks[0].detail)

    def test_a_404_on_every_channel_is_one_feed_down_line(self):
        from core.competitor_health import inspect_competitors, render_report

        channels = [{"id": _A, "label": "MKBHD"}, {"id": _B, "label": "Linus"}]
        report = inspect_competitors(
            "tapin",
            channels=channels,
            fetch=lambda _cid: FeedProbe([], 404),
        )
        text = render_report(report)
        self.assertFalse(report.ok)
        self.assertEqual(text.count("channel feed is down"), 1)
        self.assertIn("404", text)
        self.assertNotIn("dead or wrong", text)
        self.assertNotIn("MKBHD", text)

    def test_a_404_beside_a_live_channel_is_that_id(self):
        from core.competitor_health import inspect_competitors, render_report

        def fetch(cid: str):
            if cid == _A:
                return FeedProbe([{"title": "one", "video_id": "aaaaaaaaaaa"}], 200)
            return FeedProbe([], 404)

        report = inspect_competitors(
            "tapin",
            channels=[{"id": _A, "label": "MKBHD"}, {"id": _B, "label": "Linus"}],
            fetch=fetch,
        )
        text = render_report(report)
        self.assertIn("dead or wrong", text)
        self.assertNotIn("channel feed is down", text)
        self.assertTrue(any(c.ok for c in report.checks))

    def test_a_stored_feed_down_snapshot_is_not_n_dead_ids(self):
        from core.competitor_health import inspect_competitors, render_report

        snap = {
            "feed_down": 404,
            "competitors": [
                {"youtube_channel_id": _A, "label": "MKBHD", "recent_videos": []},
                {"youtube_channel_id": _B, "label": "Linus", "recent_videos": []},
            ],
        }
        report = inspect_competitors(
            "tapin",
            channels=[
                {"id": _A, "label": "MKBHD"},
                {"id": _B, "label": "Linus"},
            ],
            snapshot=snap,
        )
        text = render_report(report)
        self.assertFalse(report.ok)
        self.assertEqual(text.count("channel feed is down"), 1)
        self.assertNotIn("dead or wrong", text)

    def test_a_stored_500_on_one_row_is_not_a_dead_id(self):
        from core.competitor_health import inspect_competitors, render_report

        snap = {
            "competitors": [
                {
                    "youtube_channel_id": _A,
                    "label": "MKBHD",
                    "recent_videos": [{"title": "one"}],
                },
                {
                    "youtube_channel_id": _B,
                    "label": "Linus",
                    "recent_videos": [],
                    "feed_status": 500,
                },
            ]
        }
        report = inspect_competitors(
            "tapin",
            channels=[{"id": _A, "label": "MKBHD"}, {"id": _B, "label": "Linus"}],
            snapshot=snap,
        )
        text = render_report(report)
        self.assertIn("500", text)
        self.assertNotIn("dead or wrong", text)


class SyncSkipsApiTests(unittest.TestCase):
    def _sync(self, probes: dict[str, FeedProbe]):
        from analytics import competitor_sync as cs

        channels = [{"id": cid, "label": cid[-4:]} for cid in probes]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "competitors.json")
            with (
                patch.object(cs, "get_competitor_channels", return_value=channels),
                patch.object(cs, "competitors_data_path", return_value=path),
                patch.object(cs, "ensure_data_dir"),
                patch(
                    "analytics.youtube_rss.probe_channel_feed",
                    side_effect=lambda cid, **_kw: probes[cid],
                ),
                patch("apis.youtube_quota.record_usage") as rec,
                patch.object(cs, "_get_youtube_service") as svc,
            ):
                snap = cs.sync_competitors("tapin", uploads_free=lambda *_args, **_kwargs: [])
            with open(path, encoding="utf-8") as handle:
                written = json.loads(handle.read())
        return snap, written, rec, svc

    def test_a_404_on_every_channel_spends_no_data_api_units(self):
        snap, written, rec, svc = self._sync({_A: FeedProbe([], 404), _B: FeedProbe([], 404)})
        self.assertEqual(snap.get("feed_down"), 404)
        self.assertEqual(written.get("feed_down"), 404)
        rec.assert_not_called()
        svc.assert_not_called()

    def test_a_404_beside_a_live_feed_may_fall_back_for_that_id_only(self):
        from analytics import competitor_sync as cs

        probes = {
            _A: FeedProbe([{"title": "one", "video_id": "aaaaaaaaaaa"}], 200),
            _B: FeedProbe([], 404),
        }
        channels = [{"id": cid, "label": cid[-4:]} for cid in probes]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "competitors.json")
            with (
                patch.object(cs, "get_competitor_channels", return_value=channels),
                patch.object(cs, "competitors_data_path", return_value=path),
                patch.object(cs, "ensure_data_dir"),
                patch(
                    "analytics.youtube_rss.probe_channel_feed",
                    side_effect=lambda cid, **_kw: probes[cid],
                ),
                patch.object(cs, "youtube_api_fallback_block_reason", return_value=None),
                patch.object(cs, "_get_youtube_service", return_value=object()),
                patch.object(
                    cs,
                    "fetch_channel_recent_videos_api",
                    return_value=[{"title": "api", "video_id": "bbbbbbbbbbb"}],
                ) as api,
                patch("apis.youtube_quota.record_usage") as rec,
            ):
                snap = cs.sync_competitors("tapin")
        self.assertNotIn("feed_down", snap)
        api.assert_called_once()
        self.assertEqual(api.call_args.args[1], _B)
        rec.assert_called_once()
        by_id = {row["youtube_channel_id"]: row for row in snap["competitors"]}
        self.assertEqual(by_id[_A]["recent_videos"][0]["video_id"], "aaaaaaaaaaa")
        self.assertEqual(by_id[_B]["recent_videos"][0]["video_id"], "bbbbbbbbbbb")


class ProbeStatusTests(unittest.TestCase):
    def test_a_500_response_keeps_the_status(self):
        from analytics.youtube_rss import probe_channel_feed

        reply = SimpleNamespace(status_code=500, content=b"")
        with patch("analytics.youtube_rss.requests.get", return_value=reply):
            probe = probe_channel_feed(_A)
        self.assertEqual(probe.status, 500)
        self.assertEqual(probe.videos, [])
