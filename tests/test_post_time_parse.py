"""parse_local_time_input — operator time strings → UTC, read in the channel tz.

Upload Option 3 lets the operator name a clock time instead of "minutes from now".
The parser is timezone-correct (channel tz → UTC), rolls a past clock time to the next
day, honors today/tomorrow, and returns None on anything it can't parse so the caller
falls back. tz is pinned to America/New_York (EDT, UTC-4 in July) via a patched schedule.
"""

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from analytics.post_timing import PostScheduleConfig, parse_local_time_input

_ET = PostScheduleConfig(timezone="America/New_York")


def _parse(raw, after):
    with patch("analytics.post_timing.get_post_schedule", return_value=_ET):
        return parse_local_time_input(raw, "tapin", after=after)


class TestParseLocalTimeInput(unittest.TestCase):
    # Monday 2026-07-20 10:00 EDT == 14:00 UTC
    MON_AM = datetime(2026, 7, 20, 14, 0, tzinfo=timezone.utc)
    # Monday 2026-07-20 19:00 EDT == 23:00 UTC
    MON_PM = datetime(2026, 7, 20, 23, 0, tzinfo=timezone.utc)

    def test_clock_time_later_today(self):
        # 9:30pm EDT today → 01:30 UTC next calendar day.
        self.assertEqual(
            _parse("9:30pm", self.MON_AM),
            datetime(2026, 7, 21, 1, 30, tzinfo=timezone.utc),
        )

    def test_clock_time_with_space(self):
        self.assertEqual(
            _parse("9:30 pm", self.MON_AM),
            datetime(2026, 7, 21, 1, 30, tzinfo=timezone.utc),
        )

    def test_24h_clock(self):
        self.assertEqual(
            _parse("21:30", self.MON_AM),
            datetime(2026, 7, 21, 1, 30, tzinfo=timezone.utc),
        )

    def test_hour_only_ampm(self):
        # 9pm EDT → 01:00 UTC next day.
        self.assertEqual(
            _parse("9pm", self.MON_AM),
            datetime(2026, 7, 21, 1, 0, tzinfo=timezone.utc),
        )

    def test_past_clock_time_rolls_to_tomorrow(self):
        # 9am already passed at 19:00 EDT → tomorrow 09:00 EDT == 13:00 UTC.
        self.assertEqual(
            _parse("9am", self.MON_PM),
            datetime(2026, 7, 21, 13, 0, tzinfo=timezone.utc),
        )

    def test_tomorrow_prefix(self):
        # tomorrow 6pm EDT == 22:00 UTC on 2026-07-21.
        self.assertEqual(
            _parse("tomorrow 6pm", self.MON_AM),
            datetime(2026, 7, 21, 22, 0, tzinfo=timezone.utc),
        )

    def test_today_prefix_keeps_today_even_if_past(self):
        # "today 9am" at 19:00 EDT stays today (explicit day-word, no roll).
        self.assertEqual(
            _parse("today 9am", self.MON_PM),
            datetime(2026, 7, 20, 13, 0, tzinfo=timezone.utc),
        )

    def test_explicit_iso_datetime(self):
        self.assertEqual(
            _parse("2026-07-25 18:00", self.MON_AM),
            datetime(2026, 7, 25, 22, 0, tzinfo=timezone.utc),
        )

    def test_explicit_date_with_ampm(self):
        self.assertEqual(
            _parse("2026-07-25 6:00pm", self.MON_AM),
            datetime(2026, 7, 25, 22, 0, tzinfo=timezone.utc),
        )

    def test_bare_number_is_not_a_time(self):
        # "30" (minutes) is not a clock time → None, so the caller uses minutes-from-now.
        self.assertIsNone(_parse("30", self.MON_AM))

    def test_garbage_returns_none(self):
        self.assertIsNone(_parse("whenever", self.MON_AM))

    def test_empty_returns_none(self):
        self.assertIsNone(_parse("", self.MON_AM))
        self.assertIsNone(_parse("   ", self.MON_AM))


if __name__ == "__main__":
    unittest.main()
