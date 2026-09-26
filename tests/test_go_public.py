"""#864: `ops go-public` flips a review-held unlisted upload to public.

The review hold (#109) lands every immediate public upload unlisted, and until now the
only way out was YouTube Studio by hand. The flip must send status only, stay a dry run
unless asked, and never promote a run that was rendered past the grounding gate (#754).
"""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from storage.repositories.publish_log import PublishLogRecord


def _row(rid, vid, privacy="unlisted", run_id=None):
    return PublishLogRecord(
        id=rid,
        content_run_id=run_id,
        channel_id="tapin",
        youtube_video_id=vid,
        privacy_status=privacy,
        status="uploaded",
    )


class GoPublicTests(unittest.TestCase):
    def _repo(self, rows):
        repo = MagicMock()
        repo.list_uploaded_for_channel.return_value = rows
        return repo

    def test_plan_is_status_only(self):
        from publishing.go_public import go_public_plan

        body = go_public_plan("abc123")
        self.assertEqual(body, {"id": "abc123", "status": {"privacyStatus": "public"}})

    def test_no_video_id_picks_newest_unlisted_hold(self):
        from publishing.go_public import apply_go_public

        repo = self._repo([_row(1, "old", "unlisted"), _row(3, "pub", "public"), _row(2, "new")])
        with patch("publishing.go_public.load_features", return_value={}):
            result = apply_go_public("", channel_id="tapin", repo=repo)
        self.assertEqual(result.status, "dry_run")
        self.assertEqual(result.video_id, "new")

    def test_dry_run_sends_nothing(self):
        from publishing.go_public import apply_go_public

        repo = self._repo([_row(1, "abc")])
        with (
            patch("publishing.go_public.load_features", return_value={}),
            patch("youtube.oauth.get_youtube_service") as svc,
        ):
            result = apply_go_public("abc", channel_id="tapin", repo=repo)
        self.assertEqual(result.status, "dry_run")
        svc.assert_not_called()
        repo.update.assert_not_called()

    def test_grounding_override_is_refused(self):
        from publishing.go_public import apply_go_public

        repo = self._repo([_row(1, "abc", run_id=42)])
        with (
            patch(
                "publishing.go_public.load_features",
                return_value={"grounding_override": True},
            ),
            patch("youtube.oauth.get_youtube_service") as svc,
        ):
            result = apply_go_public("abc", channel_id="tapin", repo=repo, dry_run=False)
        self.assertEqual(result.status, "refused")
        self.assertIn("grounding", result.detail)
        svc.assert_not_called()

    def test_short_cut_from_override_parent_is_refused(self):
        from publishing.go_public import apply_go_public

        repo = self._repo([_row(1, "abc", run_id=43)])
        features = {43: {"parent_run_id": 42}, 42: {"grounding_override": True}}
        with patch(
            "publishing.go_public.load_features", side_effect=lambda rid: features.get(rid, {})
        ):
            result = apply_go_public("abc", channel_id="tapin", repo=repo, dry_run=False)
        self.assertEqual(result.status, "refused")

    def test_apply_sends_status_part_and_records_public(self):
        from publishing.go_public import apply_go_public

        repo = self._repo([_row(7, "abc", run_id=5)])
        service = MagicMock()
        with (
            patch("publishing.go_public.load_features", return_value={}),
            patch("youtube.oauth.get_youtube_service", return_value=service),
            patch.dict(os.environ, {"YOUTUBE_UPLOAD_ENABLED": "true"}),
        ):
            result = apply_go_public("abc", channel_id="tapin", repo=repo, dry_run=False)
        self.assertEqual(result.status, "updated", result.detail)
        kwargs = service.videos.return_value.update.call_args.kwargs
        self.assertEqual(kwargs["part"], "status")
        self.assertEqual(kwargs["body"]["status"], {"privacyStatus": "public"})
        repo.update.assert_called_once_with(7, {"privacy_status": "public"})

    def test_apply_blocked_without_upload_flag(self):
        from publishing.go_public import apply_go_public

        repo = self._repo([_row(1, "abc")])
        with (
            patch("publishing.go_public.load_features", return_value={}),
            patch.dict(os.environ, {"YOUTUBE_UPLOAD_ENABLED": "false"}),
            patch("youtube.oauth.get_youtube_service") as svc,
        ):
            result = apply_go_public("abc", channel_id="tapin", repo=repo, dry_run=False)
        self.assertEqual(result.status, "blocked")
        svc.assert_not_called()

    def test_nothing_held(self):
        from publishing.go_public import apply_go_public

        repo = self._repo([_row(1, "abc", "public")])
        result = apply_go_public("", channel_id="tapin", repo=repo)
        self.assertEqual(result.status, "invalid")

    def test_ops_verb_registered(self):
        from scripts.ops import COMMANDS

        self.assertIn("go-public", COMMANDS)

    def test_review_hold_message_names_the_command(self):
        from publishing.youtube_publisher import review_hold_detail

        text = review_hold_detail("abc123", channel_id="tapin")
        self.assertIn("py -m scripts.ops go-public abc123", text)
        self.assertIn("--apply", text)
        json.dumps(text)


if __name__ == "__main__":
    unittest.main()
