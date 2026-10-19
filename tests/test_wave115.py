"""Wave 115 (2026-10-19): the next ten.

Measured first: uploads stopped at 4 on 10-19 - 8,629 of 10,000 units, 1,200 of them three
caption files at 400 each; the unattended sync tried the "default" channel again, whose sign-in
file exists without the analytics permission; the first weekly compilation was scheduled public
without the AI disclosure, which the pre-publish check only warned about.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

NOW = datetime(2026, 10, 19, 22, 30, tzinfo=timezone.utc)
ANALYTICS = "https://www.googleapis.com/auth/yt-analytics.readonly"
UPLOAD = "https://www.googleapis.com/auth/youtube.upload"


class SyncScopeTests(unittest.TestCase):
    """#1523: the daily sync only for a channel signed in with the analytics permission."""

    def test_a_sign_in_without_analytics_is_skipped(self):
        from jobs import worker

        with tempfile.TemporaryDirectory() as tmp:
            paths = {}
            for cid, scopes in (("tapin", [UPLOAD, ANALYTICS]), ("default", [UPLOAD])):
                paths[cid] = os.path.join(tmp, f"{cid}.json")
                with open(paths[cid], "w", encoding="utf-8") as handle:
                    json.dump({"scopes": scopes}, handle)
            with (
                patch("config.channels.active_channel_ids", return_value=["tapin", "default"]),
                patch(
                    "youtube.oauth.token_path_for_channel", side_effect=lambda cid=None: paths[cid]
                ),
                patch("analytics.sync_metrics.maybe_sync") as sync,
            ):
                worker._sync_metrics()
        sync.assert_called_once_with("tapin")


class DisclosureAtUploadTests(unittest.TestCase):
    """#1524 (the operator: append it): an upload without the AI line gets it, not a warning."""

    def _request(self, description):
        from publishing.base import PublishRequest

        return PublishRequest(file_path="v.mp4", title="Week in Review", description=description)

    def test_a_missing_line_is_appended(self):
        from publishing import prepublish

        line = "Made with AI-assisted narration and editing."
        with patch.object(prepublish, "_disclosure_line", return_value=line):
            fixed, added = prepublish.with_disclosure(
                self._request("Every Short.\n\n0:00 One"), "tapin"
            )
            same, again = prepublish.with_disclosure(self._request(f"Body.\n\n{line}"), "tapin")
        self.assertTrue(added)
        self.assertTrue(fixed.description.endswith(line))
        self.assertIn("0:00 One", fixed.description)
        self.assertFalse(again)
        self.assertEqual(same.description, f"Body.\n\n{line}")

    def test_no_line_set_changes_nothing(self):
        from publishing import prepublish

        with patch.object(prepublish, "_disclosure_line", return_value=""):
            request, added = prepublish.with_disclosure(self._request("Body."), "tapin")
        self.assertFalse(added)
        self.assertEqual(request.description, "Body.")

    def test_the_publisher_appends_before_the_checklist(self):
        import inspect

        from publishing import youtube_publisher

        source = inspect.getsource(youtube_publisher)
        self.assertLess(source.index("with_disclosure("), source.index("prepublish.checklist("))


class CaptionQuotaTests(unittest.TestCase):
    """#1525 (the operator: only when quota allows): a caption file is 400 units."""

    def _upload(self, remaining):
        from youtube import captions

        service = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            track = os.path.join(tmp, "v.vtt")
            with open(track, "w", encoding="utf-8") as handle:
                handle.write("WEBVTT\n")
            with (
                patch(
                    "apis.youtube_quota.get_usage_summary", return_value={"remaining": remaining}
                ),
                patch("apis.youtube_quota.record_usage"),
                patch.object(captions, "MediaFileUpload", MagicMock()),
            ):
                result = captions.maybe_upload_captions(service, video_id="abc", caption_path=track)
        return result, service

    def test_it_keeps_an_uploads_units(self):
        result, service = self._upload(1_371)
        self.assertEqual(result.status, "skipped")
        self.assertIn("upload", result.detail)
        service.captions.assert_not_called()

    def test_with_room_it_goes_up(self):
        result, service = self._upload(6_000)
        self.assertEqual(result.status, "set")
        service.captions.return_value.insert.assert_called_once()

    def test_the_rule_itself(self):
        from youtube.captions import caption_quota_ok

        self.assertTrue(caption_quota_ok(2_000))
        self.assertFalse(caption_quota_ok(1_999))


if __name__ == "__main__":
    unittest.main()
