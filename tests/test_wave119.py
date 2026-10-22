"""Wave 119 (2026-10-21 evening): the next ten.

Measured first: overnight's first follow-up (run 179, the Pistons) said "Since then, Detroit
clinched the No. 1 seed" - last season's playoff page, which the claim check passed because the
source supports it - and only "hard to say" stood between it and an unattended render. The sign-in
lapses tonight, and "Yours today" listed it only while it was still in its Testing window.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

TITLE = "Detroit Pistons bench outplays Boston Celtics reserves in key stretch"


class FollowUpDateTests(unittest.TestCase):
    """#1536: the follow-up names the original's date, and is still made once per video."""

    def _topic(self, recent):
        from core import batch_generation

        published = datetime(2026, 10, 18, 15, 8, tzinfo=timezone.utc)
        rows = [{"run_id": 162, "title": TITLE[:60], "subs": 2, "published": published}]
        repo = SimpleNamespace(get=lambda rid: SimpleNamespace(title=TITLE))
        with (
            patch("analytics.growth._rows", return_value=rows),
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),
            patch("core.channel_context.recent_input_topics", return_value=recent),
            patch.object(batch_generation, "unreviewed_draft", return_value=None),
        ):
            return batch_generation.follow_up_topic("tapin", now=published + timedelta(days=3))

    def test_the_date_is_in_it(self):
        self.assertEqual(
            self._topic([]),
            f'Follow-up to "{TITLE}" (Oct 18): what has happened since Oct 18',
        )

    def test_once_even_in_the_old_words(self):
        self.assertEqual(self._topic([f'Follow-up to "{TITLE}": what has happened since']), "")


class FollowUpHoldTests(unittest.TestCase):
    """#1536 (the operator: hold for review): a follow-up that says "since" waits for a person."""

    def _reason(self, topic, script):
        from core import batch_review

        draft = batch_review.PendingDraft(
            folder="f", meta={"run_id": 179, "title": "Pistons", "topic": topic}, script=script
        )
        with (
            patch.object(batch_review, "dead_reason", return_value=""),
            patch.object(batch_review, "_blocking_claims", return_value=False),
            patch.object(batch_review, "authenticity_now", return_value=("ok", "")),
            patch.object(batch_review, "game_block_reason", return_value=""),
            patch.object(batch_review, "arc_counter_reason", return_value=""),
        ):
            return batch_review.unattended_block_reason(draft)

    def test_run_179_is_held(self):
        reason = self._reason(
            f'Follow-up to "{TITLE}": what has happened since',
            "23-0 run. Since then, Detroit clinched the No. 1 seed in the East.",
        )
        self.assertIn("follow-up", reason)
        self.assertIn("since", reason)

    def test_other_drafts_and_follow_ups_without_it_render(self):
        self.assertEqual(
            self._reason("Xbox Game Pass adds Final Fantasy 7", "Since launch, it sold well."), ""
        )
        self.assertEqual(
            self._reason(
                f'Follow-up to "{TITLE}" (Oct 18)', "The bench went 23-0. That is the story."
            ),
            "",
        )


class YoursAfterTheLapseTests(unittest.TestCase):
    """#1537: once the sign-in has lapsed, "Yours today" says to sign in again."""

    def test_the_lapse_is_named(self):
        from core import status_summary

        with (
            patch(
                "youtube.oauth.sign_in_status",
                return_value="YouTube sign-in for tapin has expired or been revoked",
            ),
            patch(
                "youtube.oauth.sign_in_expiry",
                return_value=datetime.now(timezone.utc) - timedelta(hours=1),
            ),
            patch("core.stale_renders.shelf_rows", return_value=[]),
            patch("os.path.isdir", return_value=False),
        ):
            items = status_summary.yours_items("tapin")
        self.assertEqual(len(items), 1)
        self.assertTrue(
            items[0].startswith(
                "sign in again - uploads wait: py -m youtube.oauth_setup --channel tapin"
            )
        )


if __name__ == "__main__":
    unittest.main()
