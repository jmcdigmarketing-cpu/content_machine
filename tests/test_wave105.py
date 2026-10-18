"""Wave 105 (the operator, 2026-10-17: "next 5 plz ... im gonna queue some vids tn").

- Seven finished videos (runs 153-161) were left on disk by the cadence cap of the morning
  (decision 65 removed it later); the shelf then said `requeue_upload --queue`, which uploads
  private with no publish time. The operator's answer: scheduled public slots, two a day,
  noon and 10 PM - the planner would have spread six over two weeks.
- CI (UTC) printed UFC 335 as "Sun Oct 25 1:00 AM", the PC (CDT) "Sat Oct 24 8:00 PM".
- A scheduled video turns public at its slot; the publish log learned it in the morning sync,
  so Buffer waited until then.
- "Bo Nickal" and "Ben Affleck" were follow-up ideas.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

SAT_730_PM_EDT = datetime(2026, 10, 17, 23, 30, tzinfo=timezone.utc)


# ---- 1: the stranded renders, two a day ------------------------------------------------------


class TwiceDailySlotTests(unittest.TestCase):
    def test_noon_and_ten_from_the_first_one_far_enough_out(self):
        from core.spaced_queue import twice_daily_slots

        slots = twice_daily_slots("tapin", 6, now=SAT_730_PM_EDT)
        want = [
            datetime(2026, 10, 18, 2, 0, tzinfo=timezone.utc),  # Sat 10 PM EDT
            datetime(2026, 10, 18, 16, 0, tzinfo=timezone.utc),  # Sun noon
            datetime(2026, 10, 19, 2, 0, tzinfo=timezone.utc),  # Sun 10 PM
            datetime(2026, 10, 19, 16, 0, tzinfo=timezone.utc),  # Mon noon
            datetime(2026, 10, 20, 2, 0, tzinfo=timezone.utc),  # Mon 10 PM
            datetime(2026, 10, 20, 16, 0, tzinfo=timezone.utc),  # Tue noon
        ]
        self.assertEqual(slots, want)

    def test_a_slot_too_close_is_skipped(self):
        from core.spaced_queue import twice_daily_slots

        nine_pm_edt = datetime(2026, 10, 18, 1, 0, tzinfo=timezone.utc)
        self.assertEqual(
            twice_daily_slots("tapin", 1, now=nine_pm_edt)[0],
            datetime(2026, 10, 18, 16, 0, tzinfo=timezone.utc),  # not 10 PM, 60 min away
        )


def _row(run_id):
    return {"run_id": run_id, "title": f"run {run_id}", "state": "rendered, never uploaded"}


class ShelfScheduleTests(unittest.TestCase):
    def _plan(self, rows, metas, windows, ages):
        from core import spaced_queue

        with (
            patch("core.stale_renders.shelf_rows", return_value=rows),
            patch(
                "core.batch_review.draft_meta_for_run",
                side_effect=lambda _c, rid: metas.get(rid, {}),
            ),  # fmt: skip
            patch.object(spaced_queue, "_window_days", side_effect=lambda rid, _c: windows[rid]),
            patch.object(spaced_queue, "_age_days", side_effect=lambda rid: ages[rid]),
        ):
            return spaced_queue.shelf_schedule("tapin", now=SAT_730_PM_EDT)

    def test_the_game_first_then_news_then_the_rest(self):
        rows = [_row(153), _row(154), _row(159)]
        metas = {159: {"event_at": "2026-10-18T17:00Z"}}
        plan = self._plan(rows, metas, {153: 7, 154: 2, 159: 2}, {153: 0.1, 154: 0.1, 159: 0.1})
        self.assertEqual([s.run_id for s in plan], [159, 154, 153])
        self.assertEqual(plan[0].publish_at, datetime(2026, 10, 18, 2, 0, tzinfo=timezone.utc))
        self.assertLess(plan[0].publish_at, datetime(2026, 10, 18, 17, 0, tzinfo=timezone.utc))

    def test_a_started_game_and_old_news_are_listed_not_scheduled(self):
        rows = [_row(150), _row(151), _row(153)]
        metas = {150: {"event_at": "2026-10-17T17:00Z"}}
        plan = self._plan(rows, metas, {150: 2, 151: 2, 153: 7}, {150: 0.2, 151: 3.0, 153: 0.1})
        by_id = {s.run_id: s for s in plan}
        self.assertIn("started", by_id[150].skipped)
        self.assertIn("window", by_id[151].skipped)
        self.assertIsNone(by_id[151].publish_at)
        self.assertEqual(by_id[153].publish_at,
                         datetime(2026, 10, 18, 2, 0, tzinfo=timezone.utc))  # fmt: skip

    def test_only_the_runs_asked_for(self):
        from core import spaced_queue

        with (
            patch("core.stale_renders.shelf_rows", return_value=[_row(153), _row(160)]),
            patch("core.batch_review.draft_meta_for_run", return_value={}),
            patch.object(spaced_queue, "_window_days", return_value=7),
            patch.object(spaced_queue, "_age_days", return_value=0.1),
        ):
            plan = spaced_queue.shelf_schedule("tapin", run_ids=[153], now=SAT_730_PM_EDT)
        self.assertEqual([s.run_id for s in plan], [153])

    def test_the_shelf_points_at_the_schedule_not_a_private_upload(self):
        from core import stale_renders

        run = SimpleNamespace(id=153, title="Rakhmonov", topic="")
        with (
            patch("scripts.requeue_upload.list_recyclable", return_value=[run]),
            patch.object(stale_renders, "_queued_runs", return_value={}),
            patch.object(stale_renders, "render_age_days", return_value=0.2),
            patch("publishing.go_public.unlisted_holds", return_value=[]),
        ):
            row = stale_renders.shelf_rows("tapin")[0]
        self.assertIn("shelf --schedule", row["command"])
        self.assertNotIn("requeue_upload", row["command"])


# ---- 2: event times in the channel's zone ----------------------------------------------------


class KickoffZoneTests(unittest.TestCase):
    def test_a_card_reads_in_eastern_time_with_its_label(self):
        from core.best_bet import _kickoff

        self.assertEqual(_kickoff("2026-10-25T01:00Z"), "Sat Oct 24 9:00 PM EDT")


_ = (os, timedelta)

if __name__ == "__main__":
    unittest.main()
