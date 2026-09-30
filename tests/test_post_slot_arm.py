"""#916 + #912: the ledger scores the slot a video used; an opt-in off-slot arm tests it.

#916: `ledger._post_time` asked `get_recommended_time` right after the upload, when the
video's own publish time was already reserved - so `next_optimal_post_time` skipped it
and the frozen `recommended_at` / `expected` described the *next* slot, and `post_error`
scored a claim about a different slot. The ledger now freezes the time the video used,
whether that time is one of the schedule's slots, and that slot's learned rate; only
on-slot videos are scored (as length is scored only when followed).

#912 (operator's choice: an opt-in experiment): the scheduler always takes the slot, so
"following it" could never be tested. A `post_time` lever in the existing experiments
alternates on-slot and off-slot (`POST_TIME_OFF_SLOT_HOURS`, default 4, later); nothing
changes until `py -m core.experiments start post_time`.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from tests.test_prediction_ledger import _Ledger

# Wednesday 2026-09-30 17:00 UTC is the one slot of the test schedule.
SLOT = datetime(2026, 9, 30, 17, 0, tzinfo=timezone.utc)


def _schedule():
    from analytics.post_timing import PostScheduleConfig, PostSlot

    return PostScheduleConfig(timezone="UTC", slots=(PostSlot(SLOT.weekday(), 17, 0),))


class _Schedule(unittest.TestCase):
    def setUp(self):
        self._patches = [
            patch("analytics.post_timing.get_post_schedule", return_value=_schedule()),
            patch("analytics.post_timing.learn_slots_from_analytics", return_value=_schedule()),
            patch("analytics.post_timing.infer_domain", return_value="neutral"),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()


class SlotClaimTests(_Schedule):
    def _samples(self):
        # (domain, when, rate): two past posts in this slot, one elsewhere.
        return [
            ("neutral", SLOT - timedelta(days=7), 0.30),
            ("neutral", SLOT - timedelta(days=14), 0.40),
            ("neutral", SLOT - timedelta(days=7, hours=5), 0.10),
        ]

    def test_the_slot_used_is_on_slot_with_its_rate(self):
        from analytics.post_timing import slot_claim

        with patch("analytics.post_timing._collect_timed_samples", return_value=self._samples()):
            claim = slot_claim("tapin", "UFC 320", SLOT)
        self.assertTrue(claim["on_slot"])
        self.assertAlmostEqual(claim["expected"], 0.35)
        self.assertEqual((claim["source"], claim["n"]), ("analytics", 2))
        self.assertEqual(claim["used_at"], SLOT.isoformat())

    def test_four_hours_off_is_off_slot(self):
        from analytics.post_timing import slot_claim

        with patch("analytics.post_timing._collect_timed_samples", return_value=self._samples()):
            claim = slot_claim("tapin", "UFC 320", SLOT + timedelta(hours=4))
        self.assertFalse(claim["on_slot"])

    def test_a_few_minutes_late_is_still_the_slot(self):
        from analytics.post_timing import slot_claim

        with patch("analytics.post_timing._collect_timed_samples", return_value=[]):
            self.assertTrue(slot_claim("tapin", "", SLOT + timedelta(minutes=6))["on_slot"])


class _JsonLog:
    def _log(self, rows):
        self._tmp = tempfile.TemporaryDirectory()
        path = os.path.join(self._tmp.name, "publish_log.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rows, f)
        for p in (
            patch("storage.repositories.publish_log.LOG_FILE", path),
            patch("storage.repositories.publish_log._repo", None),
            patch("storage.repositories.publish_log.postgres_authoritative", return_value=False),
        ):
            self.stack.enter_context(p)
        self.addCleanup(self._tmp.cleanup)


class LedgerTests(_Ledger, _JsonLog):
    def setUp(self):
        super().setUp()
        for p in (
            patch("analytics.post_timing.get_post_schedule", return_value=_schedule()),
            patch("analytics.post_timing.learn_slots_from_analytics", return_value=_schedule()),
            patch("analytics.post_timing.infer_domain", return_value="neutral"),
            patch(
                "analytics.post_timing._collect_timed_samples",
                return_value=[("neutral", SLOT - timedelta(days=7), 0.30)],
            ),
        ):
            self.stack.enter_context(p)

    def _scheduled(self, run_id, when):
        return {
            "id": run_id, "content_run_id": run_id, "channel_id": "tapin",
            "youtube_video_id": f"v{run_id}", "status": "scheduled",
            "published_at": when.isoformat(), "idempotency_key": f"run:tapin:{run_id}",
        }  # fmt: skip

    def test_the_frozen_claim_is_about_the_slot_the_video_used(self):
        from core.predictions.ledger import freeze

        # Upload just happened; the video is scheduled for the slot, which is now reserved.
        self._log([self._scheduled(9, SLOT)])
        post = freeze(9, "tapin")["post_time"]
        self.assertEqual(post["used_at"], SLOT.isoformat())
        self.assertTrue(post["on_slot"])
        self.assertAlmostEqual(post["expected"], 0.30)

    def test_only_on_slot_videos_are_scored(self):
        from core.predictions.ledger import freeze, ledger_rows

        self._log([self._scheduled(1, SLOT), self._scheduled(2, SLOT + timedelta(hours=4))])
        freeze(1, "tapin")
        freeze(2, "tapin")
        rows = {r["run_id"]: r for r in ledger_rows("tapin")}
        self.assertAlmostEqual(rows[1]["post_error"], 0.10 - 0.30)
        self.assertNotIn("post_error", rows[2])

    def test_an_entry_frozen_before_the_fix_is_not_scored(self):
        from core.predictions.ledger import LEDGER_KEY, ledger_rows, report_lines
        from core.run_features import merge_features

        old = {"recommended_at": SLOT.isoformat(), "expected": 0.25, "source": "analytics"}
        for run_id in (1, 2):
            merge_features(run_id, {LEDGER_KEY: {"backfilled": False, "post_time": old}})
        self.assertFalse(any("post_error" in r for r in ledger_rows("tapin")))
        self.assertIn("2 frozen before #916, not scored", "\n".join(report_lines("tapin")))

    def test_the_arm_is_kept(self):
        from core.predictions.ledger import freeze

        self._log([self._scheduled(9, SLOT + timedelta(hours=4))])
        with patch(
            "core.experiments.assignment_for_run",
            return_value={"lever": "post_time", "arm": "off_slot"},
        ):
            self.assertEqual(freeze(9, "tapin")["post_time"]["arm"], "off_slot")


class _Experiments(_Schedule):
    def setUp(self):
        super().setUp()
        import config.paths as paths

        self._tmp = tempfile.TemporaryDirectory()
        self._exp = patch.object(
            paths, "EXPERIMENTS_FILE", os.path.join(self._tmp.name, "experiments.json")
        )
        self._exp.start()
        self._next = patch("analytics.post_timing.next_optimal_post_time", return_value=SLOT)
        self._next.start()

    def tearDown(self):
        self._next.stop()
        self._exp.stop()
        self._tmp.cleanup()
        super().tearDown()


class LeverTests(_Experiments):
    def test_the_lever_exists_and_is_its_own_kind(self):
        from core import experiment_levers

        self.assertEqual(experiment_levers.kind("post_time"), "post_time")
        self.assertEqual(experiment_levers.arms("post_time"), ["on_slot", "off_slot"])

    def test_it_never_reaches_the_script_prompt(self):
        from core.experiments import next_arm, start_experiment

        with patch("core.experiments._measured_n", return_value=0):
            start_experiment("tapin", "post_time")
        self.assertIsNone(next_arm("tapin", kind="script"))
        self.assertIsNone(next_arm("tapin", kind="thumbnail"))


class PlannedTimeTests(_Experiments):
    def test_no_experiment_changes_nothing(self):
        from analytics.post_timing import planned_post_time

        self.assertEqual(planned_post_time("tapin", "UFC", run_id=5), SLOT)

    def test_a_script_experiment_changes_nothing(self):
        from analytics.post_timing import planned_post_time
        from core.experiments import start_experiment

        with patch("core.experiments._measured_n", return_value=0):
            start_experiment("tapin", "hook_style")
        self.assertEqual(planned_post_time("tapin", "UFC", run_id=5), SLOT)

    def test_the_arms_alternate_and_are_recorded(self):
        from analytics.post_timing import planned_post_time
        from core.experiments import assignment_for_run, start_experiment

        with patch("core.experiments._measured_n", return_value=0):
            start_experiment("tapin", "post_time")
        with patch.dict(os.environ, {"POST_TIME_OFF_SLOT_HOURS": ""}):
            first = planned_post_time("tapin", "UFC", run_id=5)
            second = planned_post_time("tapin", "UFC", run_id=6)
        self.assertEqual(first, SLOT)
        self.assertEqual(second, SLOT + timedelta(hours=4))
        self.assertEqual(assignment_for_run(5)["arm"], "on_slot")
        self.assertEqual(assignment_for_run(6)["arm"], "off_slot")

    def test_the_offset_can_be_set(self):
        from analytics.post_timing import planned_post_time
        from core.experiments import record_assignment, start_experiment

        with patch("core.experiments._measured_n", return_value=0):
            start_experiment("tapin", "post_time")
        record_assignment("tapin", 1, "post_time", "on_slot")  # off_slot is next
        with patch.dict(os.environ, {"POST_TIME_OFF_SLOT_HOURS": "2"}):
            self.assertEqual(planned_post_time("tapin", "", run_id=7), SLOT + timedelta(hours=2))

    def test_without_a_run_nothing_is_assigned(self):
        from analytics.post_timing import planned_post_time
        from core.experiments import start_experiment

        with patch("core.experiments._measured_n", return_value=0):
            start_experiment("tapin", "post_time")
        self.assertEqual(planned_post_time("tapin", "", run_id=None), SLOT)


class CallerTests(unittest.TestCase):
    def test_spaced_queue_passes_each_run(self):
        from core import spaced_queue
        from core.cadence import CadenceStatus

        with (
            patch.object(spaced_queue, "cadence_status", return_value=CadenceStatus(0, 0, 5, 7)),
            patch.object(spaced_queue, "planned_post_time", return_value=SLOT) as planned,
        ):
            spaced_queue.plan_spaced_uploads([(11, "a"), (12, "b")], channel_id="tapin")
        self.assertEqual([c.kwargs["run_id"] for c in planned.call_args_list], [11, 12])

    def test_auto_generate_and_the_menu_use_it(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        auto = (root / "scripts" / "auto_generate.py").read_text(encoding="utf-8")
        ui = (root / "core" / "ui.py").read_text(encoding="utf-8")
        main = (root / "main.py").read_text(encoding="utf-8")
        call = "planned_post_time(channel_id, topic, run_id=result.run_id)"
        self.assertTrue(call in auto, "auto_generate does not plan its slot per run")
        self.assertTrue("planned_post_time(" in ui, "the upload menu does not plan its slot")
        menu_call = main.split("prompt_upload_plan(")[1][:600]
        self.assertTrue("run_id=result.run_id" in menu_call, "main.py does not pass the run")


if __name__ == "__main__":
    unittest.main()
