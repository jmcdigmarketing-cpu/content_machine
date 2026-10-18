"""#1055: chapter Shorts are spread one a day, and the plan can be read before queueing.

Verified first: #757 already decides how many go (the cadence cap) and gives each the next
open slot. What it did not do: two open slots on one day (TapIn's Saturday has 11am and 7pm)
took two Shorts from the same video on the same day, and nothing showed the plan for Shorts
already cut - on 2026-10-10 five sat unpublished.
"""

from __future__ import annotations

import io
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
# Sat 11am, Sat 7pm, Sun noon, Sun 6pm, Thu 6pm - TapIn's own slots, in local time.
SLOTS = [
    datetime(2026, 10, 17, 11, 0, tzinfo=NY),
    datetime(2026, 10, 17, 19, 0, tzinfo=NY),
    datetime(2026, 10, 18, 12, 0, tzinfo=NY),
    datetime(2026, 10, 18, 18, 0, tzinfo=NY),
    datetime(2026, 10, 22, 18, 0, tzinfo=NY),
]


def _free_slots(channel_id, count, **_kw):
    # Wave 110 (#1298): the planner takes the free slots, not `planned_post_time`'s.
    return [s.astimezone(timezone.utc) for s in SLOTS][:count]


class OnePerDayTests(unittest.TestCase):
    def _plan(self, count, **kw):
        from core import spaced_queue
        from core.cadence import CadenceStatus

        with (
            patch.object(
                spaced_queue,
                "cadence_status",
                return_value=CadenceStatus(recent=0, upcoming=0, cap=5, window_days=7),
            ),
            patch.object(spaced_queue, "free_slots", side_effect=_free_slots),
            patch.object(spaced_queue, "_post_time_running", return_value=False),
            patch.object(spaced_queue, "_channel_tz", return_value=NY),
        ):
            items = [(200 + i, f"Short {i + 1}") for i in range(count)]
            return spaced_queue.plan_spaced_uploads(items, channel_id="tapin", **kw)

    def _days(self, slots):
        return [s.publish_at.astimezone(NY).date().isoformat() for s in slots if s.publish_at]

    def test_the_default_still_takes_every_open_slot(self):
        self.assertEqual(self._days(self._plan(3)), ["2026-10-17", "2026-10-17", "2026-10-18"])

    def test_one_per_day_skips_the_second_slot_of_a_day(self):
        days = self._days(self._plan(3, one_per_day=True))
        self.assertEqual(days, ["2026-10-17", "2026-10-18", "2026-10-22"])

    def test_the_long_videos_day_is_left_to_it(self):
        long_day = datetime(2026, 10, 17, 11, 0, tzinfo=NY).astimezone(timezone.utc)
        days = self._days(self._plan(2, one_per_day=True, not_on=long_day))
        self.assertEqual(days, ["2026-10-18", "2026-10-22"])

    def test_the_cap_still_decides_how_many(self):
        from core import spaced_queue
        from core.cadence import CadenceStatus

        with (
            patch.object(
                spaced_queue,
                "cadence_status",
                return_value=CadenceStatus(recent=3, upcoming=0, cap=5, window_days=7),
            ),
            patch.object(spaced_queue, "free_slots", side_effect=_free_slots),
            patch.object(spaced_queue, "_post_time_running", return_value=False),
            patch.object(spaced_queue, "_channel_tz", return_value=NY),
        ):
            plan = spaced_queue.plan_spaced_uploads(
                [(1, "a"), (2, "b"), (3, "c")], channel_id="tapin", one_per_day=True
            )
        self.assertEqual(len([s for s in plan if s.publish_at]), 2)
        self.assertIn("cadence", plan[-1].skipped)


class ShortsPlanTests(unittest.TestCase):
    def _runs(self):
        def run(i, features, mp4="x.mp4"):
            return SimpleNamespace(
                id=i, title=f"Short {i}", features_json=features, mp4_path=mp4, channel_id="tapin"
            )

        return [
            run(300, '{"parent_run_id": 119, "short_source": "chapter_cut"}'),
            run(301, '{"parent_run_id": 119, "short_source": "chapter_cut"}'),
            run(302, '{"parent_run_id": 120, "short_source": "chapter_cut"}'),
            run(119, '{"all_angles": true}'),
        ]

    def test_the_plan_lists_the_parents_unpublished_shorts(self):
        from core import chapter_shorts, spaced_queue

        repo = SimpleNamespace(
            list_for_channel=lambda cid, status=None: self._runs(),
            get=lambda rid: next(r for r in self._runs() if r.id == int(rid)),
        )
        planned = [
            spaced_queue.SpacedSlot(300, "Short 300", SLOTS[0].astimezone(timezone.utc)),
            spaced_queue.SpacedSlot(301, "Short 301", None, "cadence cap 5/7d reached"),
        ]
        with (
            patch.object(chapter_shorts, "get_content_run_repository", return_value=repo),
            patch.object(chapter_shorts, "_uploaded_run_ids", return_value={999}),
            patch.object(spaced_queue, "plan_spaced_uploads", return_value=planned) as plan,
        ):
            lines = chapter_shorts.shorts_plan_lines(119)
        self.assertEqual([i for i, _t in plan.call_args.args[0]], [300, 301])
        self.assertTrue(plan.call_args.kwargs["one_per_day"])
        text = "\n".join(lines)
        self.assertIn("Short 300", text)
        self.assertIn("Sat", text)
        self.assertIn("cadence cap", text)

    def test_a_published_short_is_not_planned_again(self):
        from core import chapter_shorts, spaced_queue

        repo = SimpleNamespace(
            list_for_channel=lambda cid, status=None: self._runs(),
            get=lambda rid: next(r for r in self._runs() if r.id == int(rid)),
        )
        with (
            patch.object(chapter_shorts, "get_content_run_repository", return_value=repo),
            patch.object(chapter_shorts, "_uploaded_run_ids", return_value={300}),
            patch.object(spaced_queue, "plan_spaced_uploads", return_value=[]) as plan,
        ):
            chapter_shorts.shorts_plan_lines(119)
        self.assertEqual([i for i, _t in plan.call_args.args[0]], [301])

    def test_the_command_prints_the_plan_after_the_chapters(self):
        from core import chapter_shorts
        from scripts.ops import COMMANDS

        with (
            patch.object(
                chapter_shorts, "chapter_report", return_value=["1. Intro  [model]  fits"]
            ),
            patch.object(chapter_shorts, "shorts_plan_lines", return_value=["[300] Short - Sat"]),
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                COMMANDS["chapters"][1](Namespace(run_id=119, channel="tapin"))
        self.assertIn("Shorts plan", buf.getvalue())
        self.assertIn("[300] Short - Sat", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
