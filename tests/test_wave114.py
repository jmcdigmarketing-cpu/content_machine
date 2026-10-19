"""Wave 114 (2026-10-18): the next ten.

Measured first: wave 113's unattended sync also tried the generic "default" channel, which has
no sign-in, and keeps retrying it; run 154 was moved on YouTube to 10-21 02:00Z (probably in
Studio) while its record kept the old slot, so the Buffer round sent its TikTok and Instagram
posts for a day before YouTube publishes it, and the privacy sync then wrote "private" over it.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

NOW = datetime(2026, 10, 19, 3, 30, tzinfo=timezone.utc)
SLOT = "2026-10-21T02:00:00Z"


def _service(statuses):
    """videos.list(part=status) answering {id: (privacyStatus, publishAt or "")}."""
    service = MagicMock()

    def _list(part, id, maxResults):
        call = MagicMock()
        items = []
        for vid in id.split(","):
            if vid in statuses:
                privacy, publish_at = statuses[vid]
                status = {"privacyStatus": privacy}
                if publish_at:
                    status["publishAt"] = publish_at
                items.append({"id": vid, "status": status})
        call.execute.return_value = {"items": items}
        return call

    service.videos.return_value.list.side_effect = _list
    return service


class SyncSignInTests(unittest.TestCase):
    """#1518: the worker's daily sync skips a channel nobody signed in for."""

    def test_a_channel_with_no_sign_in_is_skipped(self):
        from jobs import worker

        with tempfile.TemporaryDirectory() as tmp:
            token = os.path.join(tmp, "tapin.json")
            with open(token, "w", encoding="utf-8") as handle:
                handle.write("{}")
            paths = {"tapin": token, "default": os.path.join(tmp, "default.json")}
            with (
                patch("config.channels.active_channel_ids", return_value=["tapin", "default"]),
                patch(
                    "youtube.oauth.token_path_for_channel", side_effect=lambda cid=None: paths[cid]
                ),
                patch("analytics.sync_metrics.maybe_sync") as sync,
            ):
                worker._sync_metrics()
        sync.assert_called_once_with("tapin")


class ScheduledHoldTests(unittest.TestCase):
    """#1519: a video YouTube still holds for its slot keeps its record, at YouTube's slot."""

    def test_drift_leaves_a_held_video_alone(self):
        from analytics.privacy_sync import drift

        self.assertEqual(drift({"e7G": "public"}, {"e7G": "private"}, held={"e7G"}), {})
        self.assertEqual(
            drift({"e7G": "public"}, {"e7G": "private"}), {"e7G": ["public", "private"]}
        )

    def test_the_status_read_keeps_the_slot(self):
        from analytics.privacy_sync import fetch_status

        with patch("apis.youtube_quota.record_usage"):
            got = fetch_status(
                _service({"e7G": ("private", SLOT), "a": ("public", "")}), ["e7G", "a"]
            )
        self.assertEqual(got["e7G"], {"privacy": "private", "publish_at": SLOT})
        self.assertEqual(got["a"], {"privacy": "public", "publish_at": ""})

    def test_the_sync_moves_the_slot_and_keeps_it_public(self):
        from analytics import privacy_sync

        row = SimpleNamespace(id=7, youtube_video_id="e7G", privacy_status="private", content_run_id=154,
                              published_at=datetime(2026, 10, 19, 2, 0, tzinfo=timezone.utc), metrics_json="{}")  # fmt: skip
        updates = []
        log = SimpleNamespace(list_uploaded_for_channel=lambda channel: [row],
                              update=lambda rid, data: updates.append((rid, data)))  # fmt: skip
        with (
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=log),
            patch("apis.youtube_quota.record_usage"),
            patch.object(privacy_sync, "_publish_runs", return_value=[]),
        ):
            report = privacy_sync.sync_privacy(
                "tapin", service=_service({"e7G": ("private", SLOT)})
            )
        self.assertEqual(report["changed"], [])
        self.assertEqual(updates, [(7, {"privacy_status": "public",
                                        "published_at": datetime(2026, 10, 21, 2, 0, tzinfo=timezone.utc)})])  # fmt: skip
        self.assertEqual(report["rescheduled"][0]["run_id"], 154)

    def test_the_buffer_round_waits_for_youtube(self):
        from publishing import crosspost

        with (
            patch(
                "analytics.privacy_sync._service",
                return_value=_service({"e7G": ("private", SLOT), "b": ("public", "")}),
            ),
            patch("apis.youtube_quota.record_usage"),
            patch("youtube.oauth.live_youtube_forbidden", return_value=False),
        ):
            held = crosspost._held_by_youtube("tapin", {154: "e7G", 155: "b"})
        self.assertEqual(held, {154: SLOT})

    def test_a_failed_read_holds_nothing(self):
        from publishing import crosspost

        with patch("analytics.privacy_sync._service", side_effect=RuntimeError("no sign-in")):
            self.assertEqual(crosspost._held_by_youtube("tapin", {154: "e7G"}), {})

    def test_a_removed_copy_is_hosted_again(self):
        from publishing.crosspost import _needs_hosting

        self.assertTrue(_needs_hosting({}))
        self.assertFalse(_needs_hosting({"object_key": "tapin/run154.mp4", "url": "https://x"}))
        self.assertTrue(
            _needs_hosting({"object_key": "tapin/run154.mp4", "object_removed": "2026-10-19"})
        )


class FormatTests(unittest.TestCase):
    """B: #1491 Shorts against Shorts, #1323 which content converts, #1314 compilation hours."""

    def test_a_long_video_is_read_apart(self):
        from core import channel_health

        rates = {98: 0.31, 99: 0.33, 109: 0.30, 110: 0.32, 111: 0.29, 120: 0.11}
        info = {rid: {"seconds": 406.0 if rid == 120 else 40.0} for rid in rates}
        with (
            patch("core.engagement_predictor.run_engagement_map", return_value=rates),
            patch.object(channel_health, "_engagement_info", return_value=info),
            patch.object(channel_health, "_unmeasured_recent", return_value=[]),
        ):
            sub = channel_health._engagement_sub("tapin")
        self.assertEqual(sub.status, channel_health.GREEN, sub.detail)
        self.assertIn("(runs 98-111)", sub.detail)
        self.assertIn("1 long video read apart (median 11%", sub.detail)

    def test_subscribers_per_1000_by_domain_and_format(self):
        from analytics import growth

        rows = [{"run_id": 1, "subs": 1, "views": 500, "paid": 0}, {"run_id": 2, "subs": 0, "views": 300, "paid": 0},
                {"run_id": 3, "subs": 1, "views": 250, "paid": 0}, {"run_id": 4, "subs": 0, "views": 50, "paid": 0}]  # fmt: skip
        kinds = {
            1: ("gaming", "Shorts"),
            2: ("gaming", "Shorts"),
            3: ("nfl", "Shorts"),
            4: ("ufc", "long"),
        }
        with patch.object(growth, "_kind", side_effect=lambda rid: kinds[rid]):
            got = growth.conversion(rows)
        self.assertEqual([(g["domain"], g["format"], g["per_1k"]) for g in got],
                         [("gaming", "Shorts", 1.25), ("nfl", "Shorts", 4.0)])  # fmt: skip
        line = growth.conversion_line({"subscribers": {"by": got}})
        self.assertTrue(
            line.startswith("subscribers per 1,000 organic views: gaming Shorts 1.2"), line
        )

    def _compilations(self, runs, logs):
        from core import ypp_readiness

        with (
            patch("storage.repositories.content_runs.get_content_run_repository",
                  return_value=SimpleNamespace(list_for_channel=lambda c: runs)),
            patch("storage.repositories.publish_log.get_publish_log_repository",
                  return_value=SimpleNamespace(list_uploaded_for_channel=lambda c: logs)),
        ):  # fmt: skip
            return ypp_readiness.compilation_line("tapin")

    def test_what_the_compilations_add(self):
        week = SimpleNamespace(
            id=200, features_json=json.dumps({"compilation": {"week": "2026-10-19"}})
        )
        short = SimpleNamespace(id=150, features_json="{}")
        log = SimpleNamespace(
            content_run_id=200, metrics_json=json.dumps({"estimated_minutes_watched": 120})
        )
        self.assertIn("none made yet", self._compilations([short], []))
        self.assertIn("1 made, none measured yet", self._compilations([week, short], []))
        line = self._compilations([week, short], [log])
        self.assertIn("1 made, 2.0 long-form hours from 1 measured", line)
        self.assertIn("4,000 hours is", line)


if __name__ == "__main__":
    unittest.main()
