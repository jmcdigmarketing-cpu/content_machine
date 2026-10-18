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
            patch.object(spaced_queue, "_taken_slots", return_value=set()),  # #1285
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


# ---- 3: a scheduled video reaches Buffer when it goes live --------------------------------------


def _log_row(run_id, privacy, published_at):
    return SimpleNamespace(content_run_id=run_id, youtube_video_id=f"yt{run_id}",
                           privacy_status=privacy, published_at=published_at)  # fmt: skip


class ScheduledLiveTests(unittest.TestCase):
    def _pass(self, rows, changed):
        from jobs import worker

        repo = SimpleNamespace(list_uploaded_for_channel=lambda _c: rows)
        with (
            patch.object(worker, "_crosspost_channels", return_value=["tapin"]),
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=repo),
            patch(
                "analytics.privacy_sync.sync_privacy", return_value={"changed": changed}
            ) as sync,  # fmt: skip
            patch(
                "publishing.crosspost.step", return_value=["  run 159 TikTok: scheduled"]
            ) as step,
        ):
            worker._crosspost_scheduled_live(now=SAT_730_PM_EDT)
        return sync, step

    def test_a_slot_that_passed_is_read_back_and_sent(self):
        passed = SAT_730_PM_EDT - timedelta(minutes=20)
        sync, step = self._pass(
            [_log_row(159, "private", passed)],
            [{"run_id": 159, "was": "private", "now": "public"}],
        )
        sync.assert_called_once()
        step.assert_called_once_with("tapin")

    def test_nothing_due_asks_youtube_nothing(self):
        later = SAT_730_PM_EDT + timedelta(hours=3)
        sync, step = self._pass(
            [_log_row(159, "private", later), _log_row(126, "public", None)], []
        )
        sync.assert_not_called()
        step.assert_not_called()

    def test_still_private_on_youtube_sends_nothing(self):
        passed = SAT_730_PM_EDT - timedelta(minutes=5)
        _sync, step = self._pass([_log_row(159, "private", passed)], [])
        step.assert_not_called()


# ---- 4: a follow-up that is only a name ---------------------------------------------------------


class BareFollowUpTests(unittest.TestCase):
    def test_a_name_alone_is_not_a_follow_up(self):
        from core.topic_graph import arc_offer

        nickal = "Bo Nickal says scheduled UFC 335 bout with Joe Pyfer moved to main event"
        self.assertEqual(arc_offer(nickal, "ufc", 5), "")
        affleck = "Ben Affleck admits he gets into arguments with 12-year-olds in Fortnite"
        self.assertEqual(arc_offer(affleck, "fortnite", 1), "")
        self.assertEqual(arc_offer("All angles GTA 6 video", "gta", 2), "")

    def test_a_topic_with_its_subject_stays(self):
        from core.topic_graph import arc_offer

        self.assertEqual(arc_offer("GTA 6 leak week 1", "gta", 1), "GTA 6 leak")


# ---- 5: crosspost says why ----------------------------------------------------------------------


class CrosspostWhyTests(unittest.TestCase):
    def test_scheduled_videos_are_named_with_the_next_time(self):
        from publishing import crosspost

        # Wave 110 (#1299): the scheduled rows as the repository returns them - from
        # list_future_scheduled, logged with the privacy they go public with.
        rows = [_log_row(159, "public", datetime(2026, 10, 18, 2, 0, tzinfo=timezone.utc)),
                _log_row(153, "public", datetime(2026, 10, 18, 16, 0, tzinfo=timezone.utc))]  # fmt: skip
        from analytics.post_timing import _load_static_post_schedule

        repo = SimpleNamespace(
            list_uploaded_for_channel=lambda _c: [_log_row(126, "public", None)],
            list_future_scheduled=lambda _c: rows,
        )
        with (
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=repo),
            # The learned schedule reads the same log; the zone is the static schedule's.
            patch(
                "analytics.post_timing.get_post_schedule", side_effect=_load_static_post_schedule
            ),
        ):
            line = crosspost.waiting_line("tapin", now=SAT_730_PM_EDT)
        self.assertIn("2 scheduled", line)
        self.assertIn("Sat 10:00 PM EDT", line)

    def test_the_round_note_names_the_evening_slot(self):
        from publishing import crosspost

        with patch("publishing.platform_recommend.hour_choice",
                   return_value=(None, "TikTok uses YouTube's hour (0 samples, need 4)")):  # fmt: skip
            _due, note = crosspost._next_due("tapin", "topic", "tiktok", {}, SAT_730_PM_EDT)
        self.assertNotIn("YouTube's hour", note)
        self.assertIn("10 PM", note)


_ = (os, timedelta)

if __name__ == "__main__":
    unittest.main()
