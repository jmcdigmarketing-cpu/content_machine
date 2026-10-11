"""#1065: one checklist before an upload - disclosure, credits, chapters, title, made-for-kids.

Each check wraps the function that already decides it; they ran in different places or not at
all at publish time. Two refuse the upload because they cannot be put right afterwards without
someone noticing: a title YouTube will reject, and a footage credit a clip's licence requires
that is no longer in the description. The rest warn.
"""

from __future__ import annotations

import io
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

DISCLOSURE = "This video uses AI-assisted narration."
RUN_DESC = "Body.\n\nFootage:\nFortnite gameplay: CC BY 4.0 - Some Creator"


def _request(**kw):
    from publishing.base import PublishRequest

    base = {
        "file_path": "out.mp4",
        "title": "Can the Chargers still make the Super Bowl?",
        "description": f"Body.\n\n{DISCLOSURE}\n\n0:00 Intro\n0:40 The schedule",
        "privacy_status": "unlisted",
    }
    base.update(kw)
    return PublishRequest(**base)


class ChecklistTests(unittest.TestCase):
    def _checks(self, request, run=None):
        from publishing import prepublish

        with (
            patch.object(prepublish, "_disclosure_line", return_value=DISCLOSURE),
            patch.object(prepublish, "_run", return_value=run),
        ):
            return {
                c.name: c
                for c in prepublish.checklist(request, channel_id="tapin", content_run_id=7)
            }

    def test_a_clean_upload_passes_every_check(self):
        checks = self._checks(_request())
        self.assertEqual(
            sorted(checks), ["chapters", "credits", "disclosure", "made_for_kids", "title"]
        )
        self.assertTrue(all(c.ok for c in checks.values()), checks)

    def test_an_empty_or_overlong_title_blocks(self):
        for title in ("", "   ", "x" * 101):
            check = self._checks(_request(title=title))["title"]
            self.assertFalse(check.ok, title)
            self.assertTrue(check.blocks)
        self.assertTrue(self._checks(_request(title="x" * 100))["title"].ok)

    def test_a_missing_disclosure_warns(self):
        check = self._checks(_request(description="Body only."))["disclosure"]
        self.assertFalse(check.ok)
        self.assertFalse(check.blocks)

    def test_a_dropped_footage_credit_blocks(self):
        run = SimpleNamespace(description=RUN_DESC, features_json="{}")
        check = self._checks(_request(), run)["credits"]
        self.assertFalse(check.ok)
        self.assertTrue(check.blocks)
        self.assertIn("Some Creator", check.detail)

    def test_a_kept_footage_credit_passes(self):
        run = SimpleNamespace(description=RUN_DESC, features_json="{}")
        request = _request(description=RUN_DESC + f"\n\n{DISCLOSURE}")
        self.assertTrue(self._checks(request, run)["credits"].ok)

    def test_an_all_angles_video_without_chapters_warns(self):
        run = SimpleNamespace(description="", features_json='{"all_angles": true}')
        check = self._checks(_request(description=f"Body.\n\n{DISCLOSURE}"), run)["chapters"]
        self.assertFalse(check.ok)
        self.assertFalse(check.blocks)

    def test_a_single_angle_video_needs_no_chapters(self):
        run = SimpleNamespace(description="", features_json="{}")
        self.assertTrue(self._checks(_request(description=DISCLOSURE), run)["chapters"].ok)

    def test_blocking_reads_as_one_reason(self):
        from publishing import prepublish

        checks = [
            prepublish.Check("title", False, "title is empty", True),
            prepublish.Check("disclosure", False, "no disclosure line", False),
        ]
        self.assertEqual(
            prepublish.block_reason(checks), "pre-publish check failed: title is empty"
        )
        self.assertEqual(prepublish.block_reason(checks[1:]), "")
        lines = prepublish.render(checks)
        self.assertIn("[BLOCK] title", lines[0])
        self.assertIn("[warn] disclosure", lines[1])


class PublisherGateTests(unittest.TestCase):
    def test_the_publisher_refuses_a_blocked_upload_before_any_api_call(self):
        from publishing import prepublish, youtube_publisher

        blocked = [prepublish.Check("title", False, "title is empty", True)]
        publisher = youtube_publisher.YouTubePublisher()
        with (
            patch.object(youtube_publisher, "is_youtube_configured", return_value=True),
            patch.object(youtube_publisher.os.path, "isfile", return_value=True),
            patch("core.publish_deadman.deadman_block_reason", return_value=None),
            patch("core.first_frame.inspect_video", return_value=None),
            patch("core.shorts_eligibility.shorts_refuse_reason", return_value=None),
            patch.object(prepublish, "checklist", return_value=blocked),
            patch.object(
                youtube_publisher, "get_youtube_service", side_effect=AssertionError("API reached")
            ),
        ):
            result = publisher.publish(_request(), channel_id="tapin", content_run_id=None)
        self.assertEqual(result.status, "blocked")
        self.assertIn("title is empty", result.detail)

    def test_the_command_prints_the_checklist(self):
        from publishing import prepublish
        from scripts.ops import COMMANDS

        checks = [prepublish.Check("title", True, "44 characters", True)]
        with (
            patch.object(prepublish, "checklist", return_value=checks),
            patch("core.review_booth.last_trace", return_value={"title": "T", "mp4_path": "x.mp4"}),
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                COMMANDS["publish-dry-run"][1](Namespace(channel="tapin"))
        self.assertIn("[ok] title", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
