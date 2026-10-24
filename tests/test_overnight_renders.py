"""Wave 80 (#1078, first half): overnight may render, up to the channel's limit.

Operator, 2026-10-11: "Yes, up to 2 a night". Measured that day: the 5:00 am task had written
drafts every night and 69 runs had stopped at `proceed_video=False`, because overnight was
render-free by a recorded rule and the morning review was not being run. Of 31 drafts waiting,
13 had an unsupported claim, 9 an authenticity flag and 18 were past their window; three were
clean.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch


def _meta(run_id, **over):
    meta = {
        "run_id": run_id,
        "channel_id": "tapin",
        "topic": f"Topic {run_id}",
        "title": f"Title {run_id}",
        "length_choice": "2",
        "hook_score": 70,
        "hook_verdict": "strong",
        "authenticity_verdict": "ok",
        "claim_verification": {},
        "fact_conflicts": [],
        "ungrounded_entities": [],
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    meta.update(over)
    return meta


class _DraftsCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _draft(self, run_id, **over):
        folder = os.path.join(self.tmp.name, f"draft_{run_id:04d}")
        os.makedirs(folder)
        with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as fh:
            json.dump(_meta(run_id, **over), fh)
        with open(os.path.join(folder, "draft.md"), "w", encoding="utf-8") as fh:
            fh.write(f"# Draft\n\n## Script\n\nThe script of run {run_id}.\n")
        return folder

    def _stored(self, run_id):
        path = os.path.join(self.tmp.name, f"draft_{run_id:04d}", "meta.json")
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)


class LimitTests(unittest.TestCase):
    def test_the_suite_is_render_free(self):
        from core.batch_review import unattended_limit

        self.assertEqual(os.environ.get("OVERNIGHT_RENDERS"), "0")
        self.assertEqual(unattended_limit("tapin"), 0)

    def test_the_channels_own_number_is_used_when_nothing_overrides_it(self):
        from core import batch_review

        profile = type("P", (), {"overnight_renders": 2})()
        with (
            patch.dict("os.environ", {"OVERNIGHT_RENDERS": ""}),
            patch("config.channels.get_channel_profile", return_value=profile),
        ):
            self.assertEqual(batch_review.unattended_limit("tapin"), 2)

    def test_the_switch_overrides_the_channel(self):
        from core import batch_review

        profile = type("P", (), {"overnight_renders": 2})()
        with (
            patch.dict("os.environ", {"OVERNIGHT_RENDERS": "1"}),
            patch("config.channels.get_channel_profile", return_value=profile),
        ):
            self.assertEqual(batch_review.unattended_limit("tapin"), 1)

    def test_tapin_says_two_and_a_channel_that_says_nothing_says_none(self):
        from config.channels import _overnight_renders, get_channel_profile

        self.assertEqual(get_channel_profile("tapin").overnight_renders, 2)
        self.assertEqual(_overnight_renders({}), 0)
        self.assertEqual(_overnight_renders({"overnight": {"renders": "x"}}), 0)
        self.assertEqual(_overnight_renders({"overnight": {"renders": 3}}), 3)


class EligibilityTests(_DraftsCase):
    def _reason(self, **over):
        from core.batch_review import pending_drafts, unattended_block_reason

        self._draft(1, **over)
        (draft,) = pending_drafts("tapin", root=self.tmp.name)
        return unattended_block_reason(draft)

    def test_a_clean_current_draft_may_render(self):
        self.assertEqual(self._reason(), "")

    def test_an_unsupported_claim_waits_for_a_person(self):
        with patch("core.batch_review._blocking_claims", return_value=["a claim"]):
            self.assertEqual(self._reason(), "a claim is not supported")

    def test_an_authenticity_flag_waits(self):
        self.assertEqual(
            self._reason(authenticity_verdict="review"), "authenticity check says review"
        )

    def test_conflicting_facts_and_ungrounded_names_wait(self):
        from core.batch_review import pending_drafts, unattended_block_reason

        self._draft(1, fact_conflicts=["x vs y"])
        self._draft(2, ungrounded_entities=["Somebody"])
        self._draft(3, hook_verdict="weak")
        reasons = [unattended_block_reason(d) for d in pending_drafts("tapin", root=self.tmp.name)]
        # Decision 72 (#1549): a weak hook verdict no longer holds an overnight render.
        self.assertEqual(reasons, ["its facts conflict", "it names something the facts do not", ""])

    def test_a_draft_past_its_window_waits(self):
        old = (datetime.now() - timedelta(days=20)).isoformat(timespec="seconds")
        self.assertIn("past its window", self._reason(created_at=old))

    def test_the_newest_goes_first_not_the_best_hook(self):
        # Decision 70 (#1499): over 22 videos the hook score ran against who stayed.
        from core.batch_review import unattended_candidates

        day = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
        two = (datetime.now() - timedelta(days=2)).isoformat(timespec="seconds")
        self._draft(1, hook_score=70, created_at=day)
        self._draft(2, hook_score=90, created_at=two)
        self._draft(3, hook_score=70)
        self._draft(4, authenticity_verdict="review")
        eligible, skipped = unattended_candidates("tapin", root=self.tmp.name)
        self.assertEqual([d.run_id for d in eligible], [3, 1, 2])
        self.assertEqual(
            [(d.run_id, why) for d, why in skipped], [(4, "authenticity check says review")]
        )


class RenderTests(_DraftsCase):
    def _run(self, limit, *, render=None, queue=None):
        from core.batch_review import render_unattended

        rendered: list[int] = []
        queued: list[tuple[int, str]] = []
        return (
            render_unattended(
                "tapin",
                limit,
                root=self.tmp.name,
                render=render or (lambda draft, override: rendered.append(draft.run_id) or True),
                queue=queue or (lambda run_id, channel: queued.append((run_id, channel)) or 1),
            ),
            rendered,
            queued,
        )

    def test_it_renders_up_to_the_limit_and_queues_each_one(self):
        for run_id, hook, days in ((1, 60, 2), (2, 90, 0), (3, 80, 1)):  # newest first
            made = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
            self._draft(run_id, hook_score=hook, created_at=made)
        out, rendered, queued = self._run(2)
        self.assertEqual(rendered, [2, 3])
        self.assertEqual(out["rendered"], [2, 3])
        self.assertEqual(queued, [(2, "tapin"), (3, "tapin")])
        self.assertEqual(self._stored(2)["review"]["decision"], "rendered")
        self.assertEqual(self._stored(2)["review"]["by"], "overnight")
        self.assertNotIn("review", self._stored(1))

    def test_a_limit_of_zero_touches_nothing(self):
        self._draft(1)
        out, rendered, queued = self._run(0)
        self.assertEqual((rendered, queued), ([], []))
        self.assertEqual(out["rendered"], [])

    def test_a_flagged_draft_is_never_rendered(self):
        self._draft(1, authenticity_verdict="review")
        out, rendered, _queued = self._run(2)
        self.assertEqual(rendered, [])
        self.assertEqual(out["waiting"], [(1, "authenticity check says review")])

    def test_a_failed_render_is_reported_and_the_next_still_runs(self):
        self._draft(1, hook_score=90)
        self._draft(2, hook_score=80)

        def render(draft, override):
            if draft.run_id == 1:
                raise RuntimeError("ElevenLabs quota")
            return True

        out, _rendered, queued = self._run(2, render=render)
        self.assertEqual(out["rendered"], [2])
        self.assertEqual(out["failed"], [(1, "ElevenLabs quota")])
        self.assertEqual(queued, [(2, "tapin")])
        self.assertNotIn("review", self._stored(1))

    def test_the_upload_it_queues_is_unlisted(self):
        from core import batch_review

        with patch("analytics.queue_manager.requeue_content_run", return_value=9) as requeue:
            self.assertEqual(batch_review._queue_unlisted(140, "tapin"), 9)
        requeue.assert_called_once_with(140, "tapin", privacy_status="unlisted")


class OvernightTests(unittest.TestCase):
    def test_the_morning_summary_says_what_was_rendered(self):
        from core.overnight import OvernightResult, render_lines

        result = OvernightResult(channel_id="tapin")
        result.renders = {"rendered": [140, 141], "queued": [140, 141], "failed": [(142, "quota")]}
        lines = render_lines(result)
        self.assertIn("Rendered overnight: 2 (run 140, run 141), queued unlisted", lines[0])
        self.assertIn("go-public --channel tapin", lines[0])
        self.assertEqual(lines[1], "Not rendered: run 142 (quota)")

    def test_a_night_with_nothing_eligible_says_so(self):
        from core.overnight import OvernightResult, render_lines

        result = OvernightResult(channel_id="tapin")
        result.renders = {
            "rendered": [],
            "queued": [],
            "failed": [],
            "waiting": [(1, "x"), (2, "y")],
        }
        self.assertEqual(
            render_lines(result),
            ["Nothing rendered overnight: no draft qualified (2 wait for you)"],
        )
        self.assertEqual(render_lines(OvernightResult(channel_id="tapin")), [])

    def test_overnight_calls_the_render_step_with_the_channels_limit(self):
        from pathlib import Path

        text = (
            Path(__file__)
            .resolve()
            .parent.parent.joinpath("core", "overnight.py")
            .read_text(encoding="utf-8")
        )
        self.assertIn("result.renders = render_unattended(channel, limit)", text)
        self.assertIn("if limit > 0:", text)


class PlanTests(_DraftsCase):
    def test_the_plan_names_tonights_renders_and_why_the_rest_wait(self):
        from core import batch_review

        self._draft(1, hook_score=90)
        self._draft(2, hook_score=80)
        self._draft(3, hook_score=70)
        self._draft(4, authenticity_verdict="review")
        with patch.object(batch_review, "unattended_limit", return_value=2):
            lines = batch_review.unattended_plan_lines("tapin", root=self.tmp.name)
        text = "\n".join(lines)
        self.assertIn("up to 2 a night", lines[0])
        self.assertIn("would render: run 1", text)
        self.assertIn("would render: run 2", text)
        self.assertIn("next in line: run 3", text)
        self.assertIn("Waiting for you (1): 1 authenticity check says review", text)

    def test_a_render_free_channel_says_so(self):
        from core import batch_review

        self._draft(1)
        with patch.object(batch_review, "unattended_limit", return_value=0):
            lines = batch_review.unattended_plan_lines("tapin", root=self.tmp.name)
        self.assertIn("render-free", lines[1])
        self.assertNotIn("would render", "\n".join(lines))


if __name__ == "__main__":
    unittest.main()
