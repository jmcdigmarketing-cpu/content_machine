"""Wave 94 (#1212-#1214): reaction angles, the review's reasons, the end-to-end Buffer check.

- Run 154 (overnight, 2026-10-15) took the angle "Fans react to GTA 6 reveal with cautious
  optimism and hype". Nothing in its facts carried a reaction - `youtube_comments` gave none -
  so its title was flagged as unbacked and the draft waits.
- The review and the overnight plan said "authenticity check says review" and never which check;
  a clean draft held for a missing phrase looked like a bad one.
- Buffer's create call has never succeeded end to end: the one live draft found that Buffer cannot
  read a presigned link (#1207). The check was a one-off script.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# ---- #1212: a reaction angle needs reactions in the facts -------------------------------------------


class ReactionTests(unittest.TestCase):
    def test_run154_fans_react_with_no_audience_is_scored_down(self):
        from core.pipeline import reaction_penalty

        signals = {"youtube_comments": {"active": False}, "rss": {"active": True}}
        self.assertGreater(
            reaction_penalty("Fans react to GTA 6 reveal with cautious optimism and hype", signals),
            0,
        )

    def test_with_comments_the_angle_stands(self):
        from core.pipeline import reaction_penalty

        signals = {"youtube_comments": {"active": True}}
        self.assertEqual(reaction_penalty("Fans react to the GTA 6 trailer", signals), 0)

    def test_an_angle_that_is_not_a_reaction_is_untouched(self):
        from core.pipeline import reaction_penalty

        self.assertEqual(
            reaction_penalty("GTA 6 trailer: five details in the mission shots", {}), 0
        )

    def test_the_seed_scoring_path_applies_it(self):
        from core import pipeline

        with (
            patch.object(pipeline, "composite_score", return_value=60.0),
            patch("apis.topic_scorer.composite_score_raw", return_value=60.0),
        ):
            _v, plain, _s, _r = pipeline._seed_score_variant("GTA 6 trailer details", "tapin", {})
            _v, react, _s, _r = pipeline._seed_score_variant(
                "Fans react to the GTA 6 trailer", "tapin", {}
            )
        self.assertLess(react, plain)


# ---- #1213: the review names the failing check --------------------------------------------------------


class ReasonTests(unittest.TestCase):
    def _draft(self, meta):
        from core.batch_review import PendingDraft

        base = {"run_id": 150, "topic": "x", "title": "A fine title",
                "claim_verification": {"unsupported": [], "claims": []}}  # fmt: skip
        return PendingDraft(folder=tempfile.mkdtemp(), meta={**base, **meta}, script="s")

    def test_the_reason_names_the_check(self):
        from core.batch_review import unattended_block_reason

        draft = self._draft({"authenticity_verdict": "review",
                             "authenticity_failed": ["original_insight"]})  # fmt: skip
        with patch("core.run_features.load_features", return_value={}):
            reason = unattended_block_reason(draft)
        self.assertIn("no take found", reason)

    def test_an_old_draft_without_the_names_still_says_review(self):
        from core.batch_review import unattended_block_reason

        draft = self._draft({"authenticity_verdict": "review"})
        with patch("core.run_features.load_features", return_value={}):
            self.assertEqual(unattended_block_reason(draft), "authenticity check says review")

    def test_a_new_draft_stores_the_failing_checks(self):
        from core.authenticity import AuthenticityCheck, AuthenticityReport
        from core.batch_generation import authenticity_fields

        report = AuthenticityReport(
            score=50, verdict="review", gate_score=65, semantic_overlap=0.0, recurrence={},
            checks=[AuthenticityCheck("variation", True, 40, "", 40.0),
                    AuthenticityCheck("original_insight", False, 35, "", 0.0),
                    AuthenticityCheck("substance", True, 25, "", 25.0)],
        )  # fmt: skip
        self.assertEqual(
            authenticity_fields(report),
            {"authenticity_verdict": "review", "authenticity_failed": ["original_insight"]},
        )


# ---- #1214: the end-to-end Buffer check ------------------------------------------------------------


class BufferCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mp4 = os.path.join(self.tmp.name, "v.mp4")
        with open(self.mp4, "wb") as f:
            f.write(b"mp4")

    def _check(self, *, missing=(), create=None):
        from publishing import crosspost

        run = SimpleNamespace(id=132, mp4_path=self.mp4, title="Topuria")
        created = create or MagicMock(return_value={"id": "d1", "status": "draft"})
        with (
            patch.object(crosspost, "setup_missing", return_value=list(missing)),
            patch.object(crosspost, "_rendered_runs", return_value=[run]),
            patch.object(crosspost, "buffer_channel_ids", return_value={"tiktok": "tt1"}),
            patch("publishing.video_host.host", return_value="https://pub-x.r2.dev/k.mp4"),
            patch("publishing.video_host.remove", return_value=True) as remove,
            patch("publishing.buffer_api.create_video_post", created),
            patch("publishing.buffer_api.get_post", return_value={"id": "d1", "status": "draft"}),
            patch("publishing.buffer_api.delete_post", return_value=True) as delete,
        ):
            lines = crosspost.buffer_check("tapin")
        return lines, created, remove, delete

    def test_a_draft_is_made_read_and_deleted(self):
        lines, created, remove, delete = self._check()
        self.assertTrue(created.call_args.kwargs["draft"])
        delete.assert_called_once_with("d1")
        remove.assert_called_once()
        self.assertIn("ok", "\n".join(lines))

    def test_it_waits_on_what_is_missing(self):
        lines, created, _remove, _delete = self._check(missing=["R2_PUBLIC_BASE_URL"])
        created.assert_not_called()
        self.assertIn("R2_PUBLIC_BASE_URL", "\n".join(lines))

    def test_a_refusal_is_said_and_the_copy_still_removed(self):
        from publishing.buffer_api import BufferError

        refuse = MagicMock(side_effect=BufferError("input", "Video could not be read from its URL"))
        lines, _created, remove, delete = self._check(create=refuse)
        self.assertIn("Video could not be read from its URL", "\n".join(lines))
        remove.assert_called_once()
        delete.assert_not_called()


_ = datetime, timezone  # imported for readers comparing due times

if __name__ == "__main__":
    unittest.main()
