"""Wave 117 (2026-10-20): the next ten.

Measured first: the PC was shut down at Mon 10-19 8:49 PM (Kernel-Power 42, TargetState 6), so
the 5:00 overnight could not wake it and started at 16:22 when the PC came on. `ops
overnight-last` guessed "it was shut down, or wake timers are off" with wake timers on, and the
morning said only "Overnight: last started Tue 16:24". On day 5 the sign-in reminder replaced the
lapse date, and `ops agents` read both mailbox slots as "never written".
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

TIMES = {
    "last": datetime(2026, 10, 20, 16, 22),
    "start": (5, 0),
    "next": None,
    "result": 0,
    "count": 3,
    "channel": "tapin",
}
NOW = datetime(2026, 10, 20, 16, 30)
SHUT = ("shut down", datetime(2026, 10, 19, 20, 49))


def _event(utc: str, state: int) -> str:
    return (
        "<Event xmlns='http://schemas.microsoft.com/win/2004/08/events/event'><System>"
        "<Provider Name='Microsoft-Windows-Kernel-Power'/><EventID>42</EventID>"
        f"<TimeCreated SystemTime='{utc}'/></System><EventData>"
        f"<Data Name='TargetState'>{state}</Data><Data Name='Reason'>4</Data>"
        "</EventData></Event>"
    )


def _local(utc: str) -> datetime:
    when = datetime.strptime(utc[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    return when.astimezone().replace(tzinfo=None)


class PowerOffTests(unittest.TestCase):
    """#1528: how the PC went off before a missed 5:00, from the System event log."""

    XML = _event("2026-10-20T01:49:26.1703686Z", 6) + _event("2026-10-19T11:11:28.2347199Z", 4)

    def test_the_events_are_read(self):
        from core.nightly_task import parse_power_events

        events = parse_power_events(self.XML)
        self.assertEqual(
            sorted(events),
            [(_local("2026-10-19T11:11:28Z"), 4), (_local("2026-10-20T01:49:26Z"), 6)],
        )

    def test_the_last_one_before_the_start(self):
        from core.nightly_task import parse_power_events, power_off_before

        events = parse_power_events(self.XML)
        due = _local("2026-10-20T10:00:00Z")
        self.assertEqual(
            power_off_before(due, events), ("shut down", _local("2026-10-20T01:49:26Z"))
        )
        self.assertIsNone(power_off_before(_local("2026-10-19T05:00:00Z"), events))

    def test_the_suite_never_reads_the_log(self):
        from core.nightly_task import power_events

        with patch("subprocess.run") as run:
            self.assertEqual(power_events(), [])
        run.assert_not_called()


class LateOvernightTests(unittest.TestCase):
    """#1528 and #1380: the late run says why, in `ops overnight-last` and in the morning."""

    def test_a_shutdown_is_named_not_guessed(self):
        from core.nightly_task import missed_line

        line = missed_line(TIMES, now=NOW, wakes=True, off=SHUT)
        self.assertIn("the PC was shut down at Mon 8:49 PM", line)
        self.assertIn("cannot wake", line)
        self.assertNotIn("wake timers are off", line)

    def test_without_the_log_it_says_what_it_said(self):
        from core.nightly_task import missed_line

        self.assertIn(
            "it was shut down, or wake timers are off", missed_line(TIMES, now=NOW, wakes=True)
        )

    def test_the_morning_line(self):
        from core.nightly_task import late_short

        self.assertEqual(
            late_short(TIMES, now=NOW, off=SHUT),
            "started Tue 4:22 PM, 11 h after 5:00 AM - the PC was shut down Mon 8:49 PM "
            "(Sleep keeps the 5:00 AM start)",
        )
        on_time = dict(TIMES, last=datetime(2026, 10, 20, 5, 0, 2))
        self.assertEqual(late_short(on_time, now=NOW, off=SHUT), "")

    def test_status_shows_it(self):
        from core import status_summary

        with (
            patch("core.nightly_task.overdue_line", return_value=""),
            patch(
                "core.nightly_task.overnight_late_short",
                return_value="started Tue 4:22 PM, 11 h after 5:00 AM",
            ),
        ):
            self.assertEqual(
                status_summary._overnight("tapin"),
                "Overnight: started Tue 4:22 PM, 11 h after 5:00 AM",
            )


class WakeDoctorTests(unittest.TestCase):
    """#1371: `ops doctor` checks the wake - the task, the power plan, and last night."""

    def _doctor(self, wakes, timers, off):
        from core import nightly_task

        with (
            patch.object(nightly_task, "task_wakes", return_value=wakes),
            patch.object(nightly_task, "wake_timers", return_value=timers),
            patch.object(nightly_task, "_queried_times", return_value=TIMES),
            patch.object(nightly_task, "power_events", return_value=[]),
            patch.object(nightly_task, "power_off_before", return_value=off),
        ):
            return nightly_task.wake_doctor(now=NOW)

    def test_a_shutdown_is_named(self):
        ok, line = self._doctor(True, {"ac": "on"}, SHUT)
        self.assertTrue(ok)
        self.assertIn("shut down Mon 8:49 PM", line)

    def test_the_uploads_check_names_the_gap(self):
        from core.nightly_task import worker_gap_text

        last = datetime(2026, 10, 19, 20, 37)
        self.assertEqual(
            worker_gap_text(last, SHUT),
            "last ran Mon 8:37 PM; the PC was shut down Mon 8:49 PM and it runs only while the "
            "PC is on",
        )
        self.assertEqual(worker_gap_text(last, ("asleep", datetime(2026, 10, 19, 22, 0))), "")
        self.assertEqual(worker_gap_text(last, ("shut down", datetime(2026, 10, 19, 20, 0))), "")

    def test_a_task_that_cannot_wake_fails(self):
        ok, line = self._doctor(False, {"ac": "on"}, None)
        self.assertFalse(ok)
        self.assertIn("schedule-drafts --wake", line)
        ok, line = self._doctor(True, {"ac": "off"}, None)
        self.assertFalse(ok)
        self.assertIn("wake timers", line)


class TonightTests(unittest.TestCase):
    """#1337 and the operator's 8 PM toast: what overnight will do, and to leave the PC asleep."""

    def test_the_line(self):
        from core.nightly_task import tonight_text

        self.assertEqual(
            tonight_text(3, 3, (5, 0)),
            "Tonight at 5:00 AM: drafts 3, renders up to 3 - leave the PC asleep, not shut down",
        )
        self.assertEqual(tonight_text(0, 0, (5, 0)), "")

    def test_the_evening_toast(self):
        from jobs import worker

        line = "Tonight at 5:00 AM: drafts 3, renders up to 3 - leave the PC asleep, not shut down"
        with (
            patch("core.nightly_task.tonight_line", return_value=line),
            patch("core.win_notify.toast_daily") as toast,
        ):
            worker._tonight_watch(now=datetime(2026, 10, 20, 19, 59))
            self.assertFalse(toast.called)
            worker._tonight_watch(now=datetime(2026, 10, 20, 20, 0))
        self.assertEqual(toast.call_args.args[0], "overnight-tonight")
        self.assertEqual(toast.call_args.args[2], line)


if __name__ == "__main__":
    unittest.main()
