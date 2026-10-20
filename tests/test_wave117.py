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


class ReminderDateTests(unittest.TestCase):
    """#1529: the day-5 reminder keeps the lapse date and names the publish page."""

    UTC_NOW = datetime(2026, 10, 20, 21, 30, tzinfo=timezone.utc)

    def setUp(self):
        import json
        import os
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.token = os.path.join(self.tmp.name, "token.json")
        self._json = json
        for p in (
            patch("youtube.oauth.token_path_for_channel", return_value=self.token),
            patch("youtube.oauth._now", return_value=self.UTC_NOW),
            patch.dict(os.environ, {"SIGN_IN_REMINDER_DAYS": "5"}),
        ):
            p.start()
            self.addCleanup(p.stop)

    def _reminder(self, signed_in_at):
        from youtube.oauth import sign_in_reminder

        with open(self.token, "w", encoding="utf-8") as handle:
            self._json.dump({"token": "t", "signed_in_at": signed_in_at}, handle)
        return sign_in_reminder("tapin")

    def test_day_five_says_when_and_what_to_do(self):
        line = self._reminder("2026-10-15T01:36:00+00:00")  # the live sign-in
        self.assertIn("lapses Wed 9:36 PM EDT (about a day left)", line)
        self.assertIn("ops check-youtube prints the page", line)
        self.assertNotIn("SIGN_IN_REMINDER_DAYS", line)
        self.assertNotIn("1 days", line)

    def test_past_seven_days_it_says_so(self):
        with patch("youtube.oauth.load_credentials", return_value=None):
            line = self._reminder("2026-10-12T01:36:00+00:00")
        self.assertIn("it is past that; sign in again", line)


class MailboxSlotTests(unittest.TestCase):
    """#1530: `ops agents` reads a slot that names no SHA from the commit that wrote it."""

    def test_blame_names_the_commit(self):
        from core.agent_comms import blame_sha

        sha = "28ae2fa" + "0" * 33
        self.assertEqual(blame_sha(f"{sha} 56 56 1\nauthor x\n"), "28ae2fa")
        self.assertEqual(blame_sha("0" * 40 + " 56 56 1\n"), "")  # not committed yet
        self.assertEqual(blame_sha(""), "")

    def test_a_slot_without_a_sha_is_read(self):
        import tempfile
        from pathlib import Path

        from core import agent_comms

        with tempfile.TemporaryDirectory() as tmp:
            mailbox = Path(tmp) / "docs" / "handoff.md"
            mailbox.parent.mkdir()
            mailbox.write_text(
                "# Handoff\n\n## Slot — Claude Code\n\n**Written:** 2026-10-19 night · **HEAD at "
                "write:** the wave 116 batch C+D commit (`git log -1`)\n\n## Slot — Cursor\n\n"
                "**Written:** 2026-10-17 · **HEAD at write:** `2f44d4e`\n",
                encoding="utf-8",
            )
            with (
                patch.object(agent_comms, "ROOT", Path(tmp)),
                patch.object(agent_comms, "MAILBOX", mailbox),
                patch.object(
                    agent_comms, "_git", return_value="28ae2fa" + "1" * 33 + " 5 5 1\n"
                ) as git,
            ):
                found = agent_comms.slots()
        self.assertEqual([s["sha"] for s in found], ["28ae2fa", "2f44d4e"])
        self.assertEqual(git.call_args.args[:5], ("blame", "--porcelain", "-L", "5,5", "--"))


class FollowUpTests(unittest.TestCase):
    """#1452 (the operator: in one of its draft slots): overnight follows up a video that brought
    2+ subscribers - run 162, the Pistons bench, on 10-20."""

    def _rows(self, days_ago=2, subs=2):
        from datetime import timedelta

        published = datetime.now(timezone.utc) - timedelta(days=days_ago)
        return [{"run_id": 162, "title": "Detroit Pistons bench outplays Boston Celtics reserves in ke",
                 "subs": subs, "published": published}]  # fmt: skip

    def _topic(self, rows, drafted=False):
        from types import SimpleNamespace

        from core import batch_generation

        run = SimpleNamespace(
            title="Detroit Pistons bench outplays Boston Celtics reserves in key stretch"
        )
        repo = SimpleNamespace(get=lambda rid: run)
        with (
            patch("analytics.growth._rows", return_value=rows),
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=repo
            ),
            patch.object(batch_generation, "series_drafted", return_value=drafted),
        ):
            return batch_generation.follow_up_topic("tapin")

    def test_the_topic(self):
        self.assertEqual(
            self._topic(self._rows()),
            'Follow-up to "Detroit Pistons bench outplays Boston Celtics reserves in key stretch": '
            "what has happened since",
        )

    def test_once_recent_and_two_or_more(self):
        self.assertEqual(self._topic(self._rows(), drafted=True), "")
        self.assertEqual(self._topic(self._rows(days_ago=20)), "")
        self.assertEqual(self._topic(self._rows(subs=1)), "")

    def test_it_takes_the_last_slot_and_its_pick(self):
        from types import SimpleNamespace

        from core import batch_generation

        ideas = [SimpleNamespace(topic="Idea A"), SimpleNamespace(topic="Idea B")]
        previews = [SimpleNamespace(topic="Preview A")]
        picks: dict = {}
        with (
            patch("core.best_bet.get_idea_menu", return_value=(ideas, previews)),
            patch("core.best_bet.pick_record", side_effect=lambda bets, rank, by: {"rank": rank}),
            patch.object(batch_generation, "_swap_holdouts", return_value=set()),
            patch.object(
                batch_generation,
                "follow_up_topic",
                return_value='Follow-up to "X": what has happened since',
            ),
        ):
            topics = batch_generation.collect_topics("tapin", count=3, picks=picks)
        self.assertEqual(
            topics, ["Idea A", "Preview A", 'Follow-up to "X": what has happened since']
        )
        self.assertNotIn("Idea B", picks)


class PublicToastTests(unittest.TestCase):
    """#1404: a toast with the watch link when a video goes public, once per video."""

    def test_the_toast(self):
        from jobs import worker

        with patch("core.win_notify.toast_daily") as toast:
            worker._toast_public([("prfFLBUOJKw", "Jalen Hurts out for season with blood clots")])
        key, _title, body = toast.call_args.args
        self.assertEqual(key, "public:prfFLBUOJKw")
        self.assertIn("https://youtu.be/prfFLBUOJKw", body)
        self.assertIn("Jalen Hurts", body)

    def test_an_upload_that_went_public_toasts(self):
        import json
        from types import SimpleNamespace

        from jobs import worker

        job = SimpleNamespace(id=1, content_run_id=9, channel_id="tapin", attempts=1,
                              payload_json=json.dumps({"privacy_status": "public", "title": "T"}))  # fmt: skip
        result = SimpleNamespace(status="uploaded", video_id="vid9", detail="", thumbnail_status="")
        with (
            patch.object(worker, "get_job_repository"),
            patch.object(worker, "get_content_run_repository"),
            patch.object(worker, "_crosspost_after_upload"),
            patch.object(worker, "_toast_public") as toast,
            patch("builtins.print"),
        ):
            worker._finalize_upload_job(job, result)
            self.assertEqual(toast.call_args.args[0], [("vid9", "T")])
            job.payload_json = json.dumps({"privacy_status": "unlisted", "title": "T"})
            toast.reset_mock()
            worker._finalize_upload_job(job, result)
            self.assertFalse(toast.called)  # an unlisted render is not public


class ReadBackTests(unittest.TestCase):
    """#1392: a scheduled time read back - run 161's first read on 10-19 returned the old one."""

    def _apply(self, reads):
        import os
        from types import SimpleNamespace

        from publishing import go_public

        record = SimpleNamespace(id=1645, content_run_id=161, youtube_video_id="YJYYdQLNTyU")
        repo = SimpleNamespace(update=lambda rid, data: True)
        service = SimpleNamespace(
            videos=lambda: SimpleNamespace(update=lambda **kw: SimpleNamespace(execute=lambda: {}))
        )
        when = datetime(2026, 10, 22, 16, 0, tzinfo=timezone.utc)
        with (
            patch.dict(os.environ, {"YOUTUBE_UPLOAD_ENABLED": "true"}),
            patch.object(go_public, "_log_rows", return_value=[record]),
            patch.object(go_public, "override_held", return_value=False),
            patch.object(go_public, "_run_title", return_value="Star Wars"),
            patch("publishing.snippet_update.manage_scope_problem", return_value=""),
            patch("youtube.oauth.get_youtube_service", return_value=service),
            patch("publishing.snippet_update.live_status", side_effect=reads),
            patch("publishing.go_public.record_call"),
            patch("time.sleep") as nap,
        ):
            return go_public.apply_schedule_public("YJYYdQLNTyU", when=when, repo=repo), nap

    def test_a_slow_read_is_read_again(self):
        before = {"privacyStatus": "private", "publishAt": "2026-10-20T16:00:00Z"}
        after = {"privacyStatus": "private", "publishAt": "2026-10-22T16:00:00Z"}
        result, nap = self._apply([before, before, after])
        self.assertEqual(result.status, "scheduled")
        self.assertIn("YouTube shows Thu 12:00 PM EDT", result.detail)
        self.assertTrue(nap.called)

    def test_a_time_that_did_not_take_is_said(self):
        before = {"privacyStatus": "private", "publishAt": "2026-10-20T16:00:00Z"}
        result, _nap = self._apply([before, before, before])
        self.assertIn("YouTube still shows Tue 12:00 PM EDT", result.detail)


class CadenceTests(unittest.TestCase):
    """#1435: health's cadence by its own rule - 7 a week green, under 5 yellow - with both counts."""

    def _sub(self, recent, upcoming=3):
        from core.cadence import CadenceStatus
        from core.channel_health import _cadence_sub

        status = CadenceStatus(recent=recent, upcoming=upcoming, cap=0, window_days=7)
        with patch("core.cadence.cadence_status", return_value=status):
            return _cadence_sub("tapin")

    def test_the_rule_and_the_words(self):
        sub = self._sub(15)
        self.assertEqual(sub.status, "green")
        self.assertEqual(sub.detail, "15 published in the last 7 days, 3 scheduled in the next 7")
        self.assertEqual(self._sub(4).status, "yellow")
        self.assertIn("under 5", self._sub(4).detail)
        self.assertEqual(self._sub(5).status, "green")


if __name__ == "__main__":
    unittest.main()
