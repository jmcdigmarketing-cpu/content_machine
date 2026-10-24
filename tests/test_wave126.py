"""Wave 126 (2026-10-23 late): the next ten - a phantom slot first.

Measured first, at 22:51 CDT: run 186, a chapter Short of run 185 (both rendered past the
grounding gate), sat in job 82 for Sat noon EDT. The uploader strips a held run's publish time,
so it would never go public then - but its job still held the slot, and run 184's UFC 333
preview, due to move before the card at the 3:05 AM EDT pass, would have gone out at 3:50 AM.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, ClassVar
from unittest.mock import MagicMock, patch

NOON = datetime(2026, 10, 24, 16, 0, tzinfo=timezone.utc)


def _job(job_id, run_id, publish_at, privacy):
    payload = {"youtube_publish_at": publish_at.isoformat(), "privacy_status": privacy,
               "title": f"run {run_id}"}  # fmt: skip
    return SimpleNamespace(id=job_id, content_run_id=run_id, status="pending", job_type="upload",
                           channel_id="tapin", payload_json=json.dumps(payload), last_error="")  # fmt: skip


class PhantomSlotTests(unittest.TestCase):
    """#1558: a slot that will not be used is not taken."""

    def _taken(self, held):
        from core import spaced_queue

        repo = MagicMock()
        repo.list_active_jobs.return_value = [_job(82, 186, NOON, "unlisted")]
        log = MagicMock()
        log.list_future_scheduled.return_value = []
        with (
            patch("storage.repositories.jobs.get_job_repository", return_value=repo),
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=log),
            patch("publishing.go_public.override_held", side_effect=lambda r: r in held),
        ):
            return spaced_queue._taken_slots("tapin")

    def test_a_held_run_reserves_nothing(self):
        self.assertEqual(self._taken({186}), set())

    def test_a_run_that_will_publish_keeps_its_slot(self):
        self.assertEqual(self._taken(set()), {NOON})

    def test_the_queue_does_not_list_it(self):
        from analytics import upload_queue

        repo = MagicMock()
        repo.list_upload_jobs.return_value = [
            _job(82, 186, datetime.now(timezone.utc) + timedelta(hours=12), "unlisted")
        ]
        log = MagicMock()
        log.list_uploaded_for_channel.return_value = []
        log.list_future_scheduled.return_value = []
        with (
            patch("storage.repositories.jobs.get_job_repository", return_value=repo),
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=log),
            patch.object(upload_queue, "_logged_runs", return_value=set()),
            patch("publishing.go_public.override_held", return_value=True),
        ):
            entries = upload_queue.list_queue_entries("tapin")
        self.assertEqual([e for e in entries if e.source == "job"], [])

    def test_a_held_run_is_queued_with_no_time(self):
        from core import spaced_queue

        slot = spaced_queue.SpacedSlot(run_id=186, title="Chiefs' line", publish_at=NOON)
        record = SimpleNamespace(mp4_path="v.mp4", tags_json="[]", title="t", description="",
                                 features_json="{}")  # fmt: skip
        runs = MagicMock()
        runs.get.return_value = record
        with (
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=runs
            ),
            patch.object(
                spaced_queue, "slot_privacy", return_value="unlisted"
            ),  # held: public asked
            patch.object(
                spaced_queue, "enqueue_repurpose_jobs", return_value=SimpleNamespace(job_ids=[1])
            ) as enq,
        ):
            spaced_queue.queue_spaced_uploads([slot], channel_id="tapin")
        self.assertIsNone(enq.call_args.kwargs["youtube_publish_at"])
        self.assertEqual(enq.call_args.kwargs["privacy_status"], "unlisted")


class PassLineTests(unittest.TestCase):
    """#1559: "Sent 3 due job(s)" was printed for a pass that uploaded none."""

    def test_the_line_says_tried(self):
        from jobs import worker

        with (
            patch.object(worker, "drain_due", return_value=3),
            patch.object(worker, "_sync_metrics"),
            patch.object(worker, "_overnight_watch"),
            patch.object(worker, "_sign_in_watch"),
            patch.object(worker, "_tonight_watch"),
            patch("sys.argv", ["worker"]),
            patch("builtins.print") as said,
        ):
            worker.main()
        line = said.call_args.args[0]
        self.assertNotIn("Sent", line)
        self.assertIn("3 due upload job(s) tried", line)


SCRIPT = "So today we talk about the Heat. They went 11 and 1, 11 of 12 games, and Bam looks new."


def _variants(openers, guidance, script=SCRIPT):
    from core import content_engine

    with (
        patch.object(content_engine, "_call_content_llm", return_value={"openers": openers}),
        patch.object(content_engine, "_first_line_rule", return_value=""),
        patch("analytics.hook_learning.regen_guidance", return_value=guidance),
        patch("core.hook_score.hook_regen_enabled", return_value=True),
    ):
        return content_engine._hook_variants(script, channel_id="")


class MeasuredTraitsTests(unittest.TestCase):
    """#1556 (the operator, 2026-10-23: measured traits) - decision 73."""

    QUESTION: ClassVar[dict[str, Any]] = {
        "prefer": [{"trait": "a question", "gap": 0.21, "with": 0.42, "without": 0.21}],
        "avoid": [], "examples": [], "settled": True,
    }  # fmt: skip

    def test_a_small_measured_edge_beats_a_higher_score(self):
        # The current opener scores 93 and has no problem; the question scores 85. Score plus a
        # +6 learned edge kept the current one - the measured trait alone takes the question.
        script = "The Heat won 11 of 12 preseason games. Bam looks new and the bench is deep."
        small = {**self.QUESTION, "prefer": [{"trait": "a question", "gap": 0.06,
                                             "with": 0.30, "without": 0.24}]}  # fmt: skip
        out, extra = _variants(["Can the Heat keep winning 11 of 12?"], small, script=script)
        self.assertTrue(out.startswith("Can the Heat keep winning 11 of 12?"), extra)

    def test_no_score_threshold(self):
        from core import hook_score

        real = hook_score.score_hook

        def low(text):
            got = real(text)
            if text.startswith("Here is a fun one"):
                return type(got)(score=0, hook=got.hook, reasons=got.reasons)
            return got

        with patch.object(hook_score, "score_hook", side_effect=low):
            _out, extra = _variants(["Here is a fun one about the Heat."], self.QUESTION)
        refused = [v.get("refused", "") or "" for v in extra["variants"]]
        self.assertFalse(any("below the hook threshold" in r for r in refused), refused)

    def test_the_rank_ignores_the_scorer(self):
        from analytics.hook_learning import rank_by_traits

        ranked = rank_by_traits(
            ["The Heat won 11 of 12.", "Can the Heat win again?"], self.QUESTION
        )
        self.assertEqual(ranked[0][0], "Can the Heat win again?")
        self.assertEqual(ranked[1][1], 0.0)


class HookArmTests(unittest.TestCase):
    """#1502 (the operator: alternate): overnight drafts test the rewrite on and off."""

    def test_the_lever(self):
        from core import experiment_levers

        self.assertIn("hook_rewrite", experiment_levers.levers())
        self.assertEqual(set(experiment_levers.arms("hook_rewrite")), {"on", "off"})
        self.assertEqual(experiment_levers.kind("hook_rewrite"), "hook")

    def test_the_off_arm_turns_the_rewrite_off_for_that_draft(self):
        import os

        from core.batch_generation import hook_arm_env

        with patch.dict(os.environ, {"HOOK_REGEN_ENABLED": "true"}):
            with hook_arm_env(("hook_rewrite", "off", "")):
                self.assertEqual(os.environ["HOOK_REGEN_ENABLED"], "false")
            self.assertEqual(os.environ["HOOK_REGEN_ENABLED"], "true")
            with hook_arm_env(("hook_rewrite", "on", "")):
                self.assertEqual(os.environ["HOOK_REGEN_ENABLED"], "true")
            with hook_arm_env(None):
                self.assertEqual(os.environ["HOOK_REGEN_ENABLED"], "true")


class ThumbnailConfirmTests(unittest.TestCase):
    """#1540: live 2026-10-23 - run 180's videos.list listed default, medium, high, standard and
    maxres as `*default.jpg`, so `maxres` said nothing about a custom image."""

    def _set(self, response):
        import os
        import tempfile

        from youtube import thumbnails

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"\xff\xd8\xff")
        self.addCleanup(os.remove, f.name)
        service = MagicMock()
        service.thumbnails.return_value.set.return_value.execute.return_value = response
        with (
            patch.object(thumbnails, "has_quota_for_thumbnail", return_value=True),
            patch.object(thumbnails, "record_thumbnail_usage"),
            patch.object(thumbnails, "MediaFileUpload"),
        ):
            got = thumbnails.set_video_thumbnail(service, "v", f.name)
        return got, service

    def test_the_set_response_confirms(self):
        got, service = self._set(
            {"items": [{"default": {"url": "https://i.ytimg.com/vi/v/default.jpg"}}]}
        )
        self.assertEqual(got.status, "set")
        service.videos.assert_not_called()  # no extra videos.list

    def test_an_empty_response_is_unverified(self):
        got, _service = self._set({})
        self.assertEqual(got.status, "unverified")


class ExpiryTests(unittest.TestCase):
    """#1509: an idea with no measurement is retired at 90 days (decision 68)."""

    LINES: ClassVar[list[str]] = [
        "- [ ] 1500. **Each hook feature** *(S21.2, filed 2026-10-18)* `[S]`",
        "- [ ] 1405. **Old one** *(S10.3, filed 2026-07-01)* `[S]`",
        "- [x] 1499. **Done** *(S21.1, filed 2026-07-01)* `[M]`",
    ]

    def test_overdue_and_next(self):
        from datetime import date

        from core.roadmap_index import idea_expiry

        got = idea_expiry(self.LINES, today=date(2026, 10, 23))
        self.assertEqual(got["overdue"], [1405])
        self.assertEqual(got["next_due"], date(2027, 1, 16))

    def test_no_live_idea_is_overdue(self):
        from core.roadmap_index import _lines, idea_expiry

        got = idea_expiry(_lines("backlog.md"))
        self.assertEqual(got["overdue"], [], "retire these with the reason (decision 68, #1509)")


class PerVideoTests(unittest.TestCase):
    """#1515: open items per public video."""

    def test_the_line(self):
        from core.roadmap_index import counts, render

        text = render(counts(), public_videos=62)
        self.assertIn("per public video", text)
        self.assertIn("62 public", text)

    def test_unknown_public_count_is_said(self):
        from core.roadmap_index import counts, render

        self.assertNotIn("per public video", render(counts()))


if __name__ == "__main__":
    unittest.main()
