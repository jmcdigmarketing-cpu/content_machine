"""Wave 135 (2026-10-30) - the countdown a day ahead, then the look list and the scoreboard's rest.

D1 (the operator: "A day ahead"): countdown days 21 and 20 were missed. The PC was off at 5 AM on
10-29, and on 10-30 overnight ran at 5:44 PM, drafted day 20 and gave its one render to a game. Now
each night also drafts tomorrow's countdown, renders countdowns outside the night's limit, and
uploads them scheduled for their own noon, so YouTube publishes them with the PC off.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
ROW = {"id": "gta6-countdown", "kind": "countdown", "subject": "GTA 6", "names": ["GTA 6"],
       "title": "GTA 6: {n} days to launch", "from": "2026-10-29", "until": "2026-11-19",
       "domain": "gaming", "playlist": "GTA"}  # fmt: skip
POWER_ON = datetime(2026, 10, 30, 22, 44, tzinfo=timezone.utc)  # 5:44 PM CDT, 10-30


def _idea(now, ahead=0):
    from core.series import countdown

    with (
        patch.dict(os.environ, {"SERIES_COUNTDOWN": "true"}),
        patch.object(countdown, "series_rows", return_value=[ROW]),
        patch.object(countdown, "channel_zone", return_value=EASTERN),
        patch("core.batch_generation.series_drafted", return_value=False),
    ):
        return countdown.countdown_idea("tapin", now=now, headlines=lambda *_a: [], ahead=ahead)


class CountdownAheadTests(unittest.TestCase):
    def test_a_countdown_goes_public_at_its_own_noon(self):
        idea = _idea(POWER_ON)
        self.assertEqual(idea.topic, "GTA 6: 20 days to launch")
        self.assertEqual(idea.publish_at, "2026-10-30T16:00:00+00:00")  # noon EDT
        ahead = _idea(POWER_ON, ahead=1)
        self.assertEqual(ahead.topic, "GTA 6: 19 days to launch")
        self.assertEqual(ahead.publish_at, "2026-10-31T16:00:00+00:00")
        self.assertEqual(ahead.deadline, "2026-11-01T04:00:00+00:00")

    def test_overnight_drafts_tomorrows_too(self):
        from core import batch_generation as bg
        from core.best_bet import BestBetResult

        def bet(topic, source="trending", **extra):
            return BestBetResult(topic=topic, domain="gaming", avg_engaged_rate=0.0,
                                 source=source, supporting_runs=0, rationale="",
                                 outlets=4, **extra)  # fmt: skip

        today = bet("GTA 6: 20 days to launch", "countdown")
        tomorrow = bet(
            "GTA 6: 19 days to launch", "countdown", publish_at="2026-10-31T16:00:00+00:00"
        )
        picks: dict = {}
        with (
            patch("core.best_bet.get_idea_menu", return_value=([today, bet("idea 0")], [])),
            patch("core.series.countdown.countdown_idea", return_value=tomorrow),
        ):
            topics = bg.collect_topics("tapin", count=1, picks=picks)
        self.assertEqual(topics, [today.topic, tomorrow.topic, "idea 0"])
        self.assertEqual(picks[tomorrow.topic]["publish_at"], "2026-10-31T16:00:00+00:00")

    def test_a_full_queue_drafts_both_once(self):
        from core import batch_generation as bg
        from core.best_bet import BestBetResult

        same = BestBetResult(topic="GTA 6: 20 days to launch", domain="gaming",
                             avg_engaged_rate=0.0, source="countdown", supporting_runs=0,
                             rationale="")  # fmt: skip
        with patch("core.series.countdown.countdown_idea", return_value=same):
            self.assertEqual(bg.collect_topics("tapin", count=0), [same.topic])

    def test_day_one_has_no_tomorrow(self):
        self.assertIsNone(_idea(datetime(2026, 11, 19, 15, tzinfo=timezone.utc)))


def _draft(run_id, *, series=""):
    from core.batch_review import PendingDraft

    meta = {"run_id": run_id, "topic": f"t{run_id}", "title": f"title {run_id}"}
    if series:
        meta["series"] = series
    return PendingDraft(folder=f"f{run_id}", meta=meta, script="One. Two.")


class CountdownRenderTests(unittest.TestCase):
    """10-30: one render a night, and the Lakers preview (sooner event) took it from day 20."""

    def _night(self, limit, pause=""):
        from core import batch_review as br

        game, countdown = _draft(218), _draft(216, series="countdown")
        rendered, queued, scheduled = [], [], []
        with (
            patch.object(br, "unattended_candidates", return_value=([game, countdown], [])),
            patch.object(br, "shelf_max", return_value=0),
            patch.object(br, "shelf_pause", return_value=pause),
            patch.object(br, "second_read", return_value=""),
            patch.object(br, "_smoke_failure", return_value=""),
            patch.object(br, "_memory_short", return_value=""),
            patch.object(br, "_disk_short", return_value=""),
            patch.object(br, "_write_review"),
            patch("core.nightly_task.beat_step"),
            patch.object(br, "_queue_scheduled", side_effect=lambda r, c: scheduled.append(r) or 1),
        ):
            br.render_unattended("tapin", limit,
                                 render=lambda d, _o: rendered.append(d.run_id) or True,
                                 queue=lambda r, c: queued.append(r) or 1)  # fmt: skip
        return rendered, queued, scheduled

    def test_a_countdown_renders_first_and_outside_the_limit(self):
        rendered, queued, scheduled = self._night(1)
        self.assertEqual(rendered, [216, 218])
        self.assertEqual(scheduled, [216])  # its own noon, not unlisted
        self.assertEqual(queued, [218])

    def test_a_full_shelf_still_renders_the_countdown(self):
        rendered, _queued, scheduled = self._night(1, pause="3 finished videos wait")
        self.assertEqual((rendered, scheduled), ([216], [216]))

    def test_no_limit_still_renders_the_countdown(self):
        rendered, _queued, scheduled = self._night(0)
        self.assertEqual((rendered, scheduled), ([216], [216]))

    def test_the_scheduled_upload_uses_its_slot(self):
        from core import batch_review as br

        when = datetime(2026, 10, 31, 16, tzinfo=timezone.utc)
        with (
            patch("core.spaced_queue.slot_for_run", return_value=(when, "")),
            patch("analytics.queue_manager.requeue_content_run", return_value=7) as requeue,
        ):
            br._queue_scheduled(216, "tapin")
        kwargs = requeue.call_args.kwargs
        self.assertEqual(kwargs["youtube_publish_at"], when)
        self.assertEqual(kwargs["privacy_status"], "private")  # YouTube's scheduled publish

    def test_a_countdown_says_its_day_ends(self):
        from core.batch_review import event_word

        self.assertEqual(event_word({"series": "countdown"}), "its day ends")
        self.assertEqual(event_word({}), "kicks off")


if __name__ == "__main__":
    unittest.main()
