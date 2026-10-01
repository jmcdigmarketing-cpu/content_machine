"""#567: the post-time experiment randomises (operator: coin flip + random hour).

#912's arm alternated on-slot / off-slot round-robin and moved off-slot videos a fixed
`POST_TIME_OFF_SLOT_HOURS` (4) later - so arm tracked upload order and every off-slot
video sat at the same hour. Each scheduled upload now flips a coin seeded by its run id
(replayable), and an off-slot video goes to a random whole hour within
+/-`POST_TIME_WINDOW_HOURS` (default 3) of the slot: never 0, never in the past, never
on another slot. The offset is recorded with the arm and the prediction ledger keeps it.
"""

from __future__ import annotations

import os
from datetime import timedelta
from itertools import pairwise
from unittest.mock import patch

from tests.test_post_slot_arm import SLOT, _Experiments


class _Started(_Experiments):
    def setUp(self):
        super().setUp()
        from core.experiments import start_experiment

        with patch("core.experiments._measured_n", return_value=0):
            start_experiment("tapin", "post_time")


class CoinTests(_Started):
    def test_the_arm_is_a_seeded_coin_not_a_rota(self):
        from core.experiments import random_arm

        arms = [random_arm("tapin", "post_time", run_id) for run_id in range(1, 201)]
        off = arms.count("off_slot")
        self.assertTrue(70 <= off <= 130, off)
        repeats = sum(1 for a, b in pairwise(arms) if a == b)
        self.assertGreater(repeats, 50)  # round-robin has none
        self.assertEqual(arms, [random_arm("tapin", "post_time", r) for r in range(1, 201)])


class HourTests(_Started):
    def _offsets(self, run_ids, *, after=None, env=None):
        from analytics.post_timing import planned_post_time
        from core.experiments import assignment_for_run

        out = {}
        with patch.dict(os.environ, env or {"POST_TIME_WINDOW_HOURS": ""}):
            for run_id in run_ids:
                when = planned_post_time(
                    "tapin", "UFC", run_id=run_id, after=after or SLOT - timedelta(hours=6)
                )
                arm = assignment_for_run(run_id)
                shift = round((when - SLOT).total_seconds() / 3600)
                out[run_id] = (arm["arm"], shift, arm.get("offset_hours"))
        return out

    def test_an_off_slot_hour_is_random_within_three(self):
        got = self._offsets(range(1, 81))
        off = [shift for arm, shift, _ in got.values() if arm == "off_slot"]
        on = [shift for arm, shift, _ in got.values() if arm == "on_slot"]
        self.assertTrue(set(on) <= {0})
        self.assertTrue(set(off) <= {-3, -2, -1, 1, 2, 3}, set(off))
        self.assertGreaterEqual(len(set(off)), 4)
        self.assertTrue(
            all(shift == recorded for arm, shift, recorded in got.values() if arm == "off_slot")
        )

    def test_never_before_now(self):
        got = self._offsets(range(1, 61), after=SLOT - timedelta(minutes=30))
        self.assertTrue(all(shift > 0 for arm, shift, _ in got.values() if arm == "off_slot"))

    def test_the_window_can_be_narrowed(self):
        got = self._offsets(range(1, 41), env={"POST_TIME_WINDOW_HOURS": "1"})
        self.assertTrue({s for a, s, _ in got.values() if a == "off_slot"} <= {-1, 1})


class LedgerTests(_Started):
    def test_the_offset_reaches_the_claim(self):
        from core.experiments import assignment_for_run, record_assignment

        record_assignment("tapin", 41, "post_time", "off_slot", offset_hours=-2)
        self.assertEqual(assignment_for_run(41)["offset_hours"], -2)
        with (
            patch("core.predictions.ledger._used_at", return_value=SLOT - timedelta(hours=2)),
            patch("analytics.post_timing.slot_claim", return_value={"on_slot": False}),
        ):
            from core.predictions.ledger import _post_time

            claim = _post_time(41, "tapin", "UFC")
        self.assertEqual((claim["arm"], claim["offset_hours"]), ("off_slot", -2))
