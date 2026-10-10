"""#1060 — the post-time line names the samples that chose the hour.

Two NFL posts are not enough for a sport schedule (the floor is 3). The hour then
comes from the pooled posts. The line must not still say "nfl" when those posts
are UFC.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from analytics.post_timing import PostScheduleConfig, PostSlot, get_recommended_time

AFTER = datetime(2026, 10, 8, 0, 0, tzinfo=timezone.utc)  # Thursday
_STATIC = PostScheduleConfig(timezone="UTC", slots=(PostSlot(0, 12, 0),))


def _samples(ufc_weekday: int, ufc_hour: int) -> list[tuple[str, datetime, float]]:
    monday = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)  # Monday
    rows = [
        ("nfl", monday, 0.2),
        ("nfl", monday + timedelta(days=7), 0.2),
    ]
    # 2026-01-01 is a Thursday.
    start = datetime(2026, 1, 1, ufc_hour, 0, tzinfo=timezone.utc)
    start += timedelta(days=ufc_weekday - start.weekday())
    for week in range(6):
        rows.append(("ufc", start + timedelta(days=7 * week), 0.8))
    return rows


class PostTimeDomainTests(unittest.TestCase):
    def _recommend(self, samples):
        with (
            patch("analytics.post_timing._collect_timed_samples", return_value=samples),
            patch("analytics.post_timing._load_static_post_schedule", return_value=_STATIC),
            patch("analytics.upload_queue.get_reserved_publish_times", return_value=[]),
        ):
            return get_recommended_time("tapin", "NFL Sunday slate", after=AFTER)

    def test_moving_the_other_sport_moves_the_hour_and_the_label(self) -> None:
        on_thursday = self._recommend(_samples(3, 20))
        on_friday = self._recommend(_samples(4, 21))
        self.assertNotEqual(
            (on_thursday.when_utc.weekday(), on_thursday.when_utc.hour),
            (on_friday.when_utc.weekday(), on_friday.when_utc.hour),
        )
        for rec in (on_thursday, on_friday):
            self.assertIn("ufc", rec.rationale)
            self.assertNotIn("nfl", rec.rationale)
