"""Wave 116 (2026-10-19 evening): the next ten.

Measured first: job 74 (run 173) was held by the quota and `ops status` called it overdue with
"nothing is sending uploads - py -m scripts.ops worker"; the worker's log said "No pending jobs."
and gave a requeue command. The morning's queue printed job times in UTC and YouTube's in EDT, and
listed runs 162, 164 and 165 - public since 10-18 - at their finished jobs' old slots, so the next
free slot was Sat 10-24 noon.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from tests.test_buffer_crosspost import CrosspostCase

NOW = datetime(2026, 10, 19, 23, 30, tzinfo=timezone.utc)


def _job(job_id, run_id, slot, status="completed"):
    return SimpleNamespace(
        id=job_id,
        content_run_id=run_id,
        status=status,
        job_type="upload",
        channel_id="tapin",
        last_error="",
        scheduled_at=None,
        payload_json=json.dumps({"youtube_publish_at": slot.isoformat(), "title": f"run {run_id}"}),
    )


def _row(row_id, run_id, when, video="vid"):
    return SimpleNamespace(
        id=row_id,
        content_run_id=run_id,
        published_at=when,
        status="scheduled",
        youtube_video_id=f"{video}{run_id}",
        title=f"run {run_id}",
    )


class QueueTruthTests(unittest.TestCase):
    """#1527: a run YouTube has is listed at the publish log's time, not its job's old slot."""

    def _patched(self, jobs, uploaded, future):
        jobs_repo = MagicMock()
        jobs_repo.list_upload_jobs.return_value = jobs
        log_repo = MagicMock()
        log_repo.list_uploaded_for_channel.return_value = uploaded
        log_repo.list_future_scheduled.return_value = future
        return (
            patch("storage.repositories.jobs.get_job_repository", return_value=jobs_repo),
            patch(
                "storage.repositories.publish_log.get_publish_log_repository",
                return_value=log_repo,
            ),
        )

    def _world(self):
        now = datetime.now(timezone.utc)
        moved_from, moved_to = now + timedelta(hours=20), now + timedelta(hours=68)
        stale = now + timedelta(days=3)
        jobs = [
            _job(66, 161, moved_from),  # moved on YouTube: the log says moved_to
            _job(69, 164, stale),  # public since 10-18: the log's time has passed
            _job(74, 173, now + timedelta(hours=22), status="pending"),  # not on YouTube yet
        ]
        uploaded = [_row(1648, 164, now - timedelta(days=1))]
        future = [_row(1645, 161, moved_to)]
        return jobs, uploaded, future, moved_to

    def test_each_video_once_at_youtubes_time(self):
        from analytics.upload_queue import list_queue_entries

        jobs, uploaded, future, moved_to = self._world()
        a, b = self._patched(jobs, uploaded, future)
        with a, b:
            entries = list_queue_entries("tapin")
        self.assertEqual([e.content_run_id for e in entries], [173, 161])
        self.assertEqual(entries[1].publish_at, moved_to)

    def test_a_finished_jobs_old_slot_is_not_reserved(self):
        from analytics.upload_queue import get_reserved_publish_times

        jobs, uploaded, future, moved_to = self._world()
        a, b = self._patched(jobs, uploaded, future)
        with a, b:
            reserved = get_reserved_publish_times("tapin")
        self.assertEqual(len(reserved), 2)
        self.assertEqual(max(reserved), moved_to)


class QueueLinesTests(unittest.TestCase):
    """#1527 and #1429: one zone with its label, a clash named, and the next two weeks."""

    def _entry(self, run_id, when, status="scheduled"):
        from analytics.upload_queue import QueueEntry

        return QueueEntry("youtube", run_id, f"run {run_id}", when, status, run_id, True)

    def test_every_time_in_the_channels_zone(self):
        from analytics.upload_queue import queue_lines

        entries = [
            self._entry(156, datetime(2026, 10, 20, 16, 0, tzinfo=timezone.utc)),
            self._entry(173, datetime(2026, 10, 20, 22, 0, tzinfo=timezone.utc), "awaiting_upload"),
        ]
        lines = queue_lines(entries, "tapin")
        self.assertIn("Tue 10-20 12:00 PM EDT", lines[0])
        self.assertIn("Tue 10-20 6:00 PM EDT", lines[1])

    def test_two_at_one_minute_are_named(self):
        from analytics.upload_queue import queue_lines

        noon = datetime(2026, 10, 20, 16, 0, tzinfo=timezone.utc)
        lines = queue_lines([self._entry(156, noon), self._entry(161, noon)], "tapin")
        self.assertIn("the same minute as run 156", lines[1])
        self.assertNotIn("same minute", lines[0].split("run 156")[-1])

    def test_the_next_fourteen_days(self):
        from analytics.upload_queue import two_week_line

        now = datetime(2026, 10, 19, 23, 30, tzinfo=timezone.utc)  # Mon 7:30 PM EDT
        times = [
            datetime(2026, 10, 20, 2, 0, tzinfo=timezone.utc),  # Mon 10 PM
            datetime(2026, 10, 20, 16, 0, tzinfo=timezone.utc),  # Tue
            datetime(2026, 10, 20, 22, 0, tzinfo=timezone.utc),  # Tue
            datetime(2026, 10, 22, 16, 0, tzinfo=timezone.utc),  # Thu
        ]
        line = two_week_line([self._entry(i, t) for i, t in enumerate(times)], "tapin", now=now)
        self.assertEqual(
            line,
            "Next 14 days: 4 scheduled on 3 of 14 days - first empty day Wed 10-21, "
            "nothing after Thu 10-22",
        )
        self.assertEqual(
            two_week_line([], "tapin", now=now), "Next 14 days: nothing scheduled on YouTube"
        )


class QuotaWaitTests(unittest.TestCase):
    """#1526: an upload held by the quota waits for the reset; it is not overdue."""

    def setUp(self):
        reset = datetime(2026, 10, 20, 7, 0, tzinfo=timezone.utc)  # midnight Pacific
        self._patches = [
            patch("apis.youtube_quota.has_quota_for_upload", return_value=False),
            patch("apis.youtube_quota.next_quota_retry_at", return_value=reset),
            patch("core.job_queue._signed_out", return_value=False),
        ]
        for p in self._patches:
            p.start()
        self.job = _job(74, 173, NOW, status="pending")
        self.job.scheduled_at = (NOW - timedelta(hours=1)).isoformat()

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def test_the_status_lines_name_the_reset(self):
        from core.job_queue import overdue_lines, overdue_short

        lines = overdue_lines([self.job], "tapin")
        self.assertEqual(len(lines), 1)
        self.assertIn("waits for the quota reset at Tue 3:00 AM EDT", lines[0])
        self.assertNotIn("ops worker", lines[0])
        self.assertEqual(overdue_short([self.job], "tapin"), "1 upload waits for the quota reset")

    def test_with_quota_it_is_overdue_as_before(self):
        from core.job_queue import overdue_lines

        with patch("apis.youtube_quota.has_quota_for_upload", return_value=True):
            lines = overdue_lines([self.job], "tapin")
        self.assertIn("nothing is sending uploads", lines[0])

    def test_the_shelf_line_asks_for_nothing(self):
        from core import stale_renders

        with patch.object(stale_renders, "_signed_out", return_value=False):
            lines = stale_renders.shelf_lines("tapin", {"renders": 1, "queued": 1})
        joined = " ".join(lines)
        self.assertIn("1 queued, waits for the quota reset at Tue 3:00 AM EDT", joined)
        self.assertNotIn("ops worker", joined)

    def test_the_worker_pass_says_what_it_holds(self):
        from jobs import worker

        repo = MagicMock()
        repo.list_active_jobs.return_value = [self.job]
        with (
            patch.object(worker, "drain_due", return_value=0),
            patch.object(worker, "_sync_metrics"),
            patch.object(worker, "_overnight_watch"),
            patch.object(worker, "_sign_in_watch"),
            patch.object(worker, "get_job_repository", return_value=repo),
            patch("sys.argv", ["worker"]),
            patch("builtins.print") as out,
        ):
            worker.main()
        printed = " ".join(str(c.args[0]) for c in out.call_args_list)
        self.assertIn(
            "1 upload waits for the quota reset (run 173) - it goes after Tue 3:00 AM EDT", printed
        )
        self.assertNotIn("No pending jobs", printed)
        self.assertNotIn("requeue_upload", printed)

    def test_the_morning_still_reads_it_as_the_quota(self):
        from jobs.worker_log import summarize_pass

        line = "1 upload waits for the quota reset (run 173) - it goes after Tue 3:00 AM EDT"
        self.assertEqual(summarize_pass([line]), "uploads blocked by quota until the reset")


class SignInHoldTests(unittest.TestCase):
    """#1439 (the operator: the next free slot): an ended sign-in holds an upload, not fails it."""

    def test_an_ended_sign_in_holds_the_job(self):
        from jobs import worker

        repo = MagicMock()
        job = _job(74, 173, NOW, status="running")
        job.attempts = 1
        result = SimpleNamespace(status="auth_error", detail="OAuth token invalid or expired")
        with (
            patch.object(worker, "get_job_repository", return_value=repo),
            patch("core.win_notify.toast_daily") as toast,
            patch("builtins.print"),
        ):
            worker._finalize_upload_job(job, result)
        fields = repo.update.call_args.args[1]
        self.assertEqual(fields["status"], "pending")
        self.assertEqual(fields["attempts"], 0)
        self.assertIn(worker.SIGN_IN_HOLD, fields["last_error"])
        self.assertIn("oauth_setup --channel tapin", fields["last_error"])
        self.assertEqual(toast.call_args.args[0], "signin:tapin")

    def _sent_request(self, last_error, slot):
        from jobs import worker

        job = _job(74, 173, slot, status="running")
        job.last_error = last_error
        payload = json.loads(job.payload_json)
        payload["file_path"] = "v.mp4"
        job.payload_json = json.dumps(payload)
        publisher = MagicMock()
        publisher.publish.return_value = SimpleNamespace(status="scheduled")
        free = datetime.now(timezone.utc) + timedelta(hours=20)
        with (
            patch("core.rpm_cost_gate.rpm_cost_gate_reason", return_value=None),
            patch.object(worker, "get_publisher", return_value=publisher),
            patch.object(worker, "get_job_repository", return_value=MagicMock()),
            patch.object(worker, "_finalize_upload_job"),
            patch("core.spaced_queue.free_slots", return_value=[free]),
        ):
            worker._process_upload(job)
        return publisher.publish.call_args.args[0], free

    def test_after_the_sign_in_a_passed_slot_takes_the_next_free_one(self):
        from jobs import worker

        passed = datetime.now(timezone.utc) - timedelta(hours=3)
        request, free = self._sent_request(f"{worker.SIGN_IN_HOLD}: sign in again", passed)
        self.assertEqual(request.publish_at, free)

    def test_a_job_held_by_the_quota_keeps_todays_rule(self):
        passed = datetime.now(timezone.utc) - timedelta(hours=3)
        request, _free = self._sent_request("Upload quota exhausted", passed)
        self.assertEqual(request.publish_at, passed.replace(microsecond=passed.microsecond))

    def test_the_morning_says_it(self):
        from jobs import worker
        from jobs.worker_log import summarize_pass

        line = f"Upload job 74 (run 173) {worker.SIGN_IN_HOLD} - it goes on the first pass after you sign in again"
        self.assertEqual(summarize_pass([line]), "uploads held - the YouTube sign-in has ended")


class SignInSoonTests(unittest.TestCase):
    """#1438: a toast from 24 hours before a Testing-mode sign-in lapses."""

    def _watch(self, hours_left, env=None):
        from jobs import worker

        expiry = NOW + timedelta(hours=hours_left)
        with (
            patch("config.channels.active_channel_ids", return_value=["tapin"]),
            patch("os.path.isfile", return_value=True),
            patch("youtube.oauth.sign_in_expiry", return_value=expiry),
            patch(
                "youtube.oauth.sign_in_expiry_line",
                return_value=""
                if (env or {}).get("off")
                else "lapses Wed 9:36 PM EDT unless the app is published",
            ),
            patch("core.win_notify.toast_daily") as toast,
        ):
            worker._sign_in_watch(now=NOW)
        return toast

    def test_inside_a_day_it_toasts_once_a_day(self):
        toast = self._watch(20)
        self.assertEqual(toast.call_args.args[0], "signin-soon:tapin")
        self.assertIn("ops check-youtube", toast.call_args.args[2])

    def test_earlier_or_switched_off_it_is_quiet(self):
        self.assertFalse(self._watch(30).called)
        self.assertFalse(self._watch(20, {"off": True}).called)


class SignInModeTests(unittest.TestCase):
    """#1443 and #1445: Testing or In production by the sign-in's age; the page for the click."""

    def setUp(self):
        import os
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.token = os.path.join(self.tmp.name, "token.json")
        self.secrets = os.path.join(self.tmp.name, "client_secrets.json")
        with open(self.secrets, "w", encoding="utf-8") as handle:
            json.dump({"installed": {"project_id": "proj-123", "client_id": "x"}}, handle)
        for p in (
            patch("youtube.oauth.token_path_for_channel", return_value=self.token),
            patch("youtube.oauth._client_secrets_path", return_value=self.secrets),
            patch("youtube.oauth._now", return_value=NOW),
            patch.dict(os.environ, {"SIGN_IN_REMINDER_DAYS": "5"}),
        ):
            p.start()
            self.addCleanup(p.stop)

    def _signed(self, days_ago):
        with open(self.token, "w", encoding="utf-8") as handle:
            json.dump(
                {"token": "t", "signed_in_at": (NOW - timedelta(days=days_ago)).isoformat()}, handle
            )

    def test_the_mode_by_age(self):
        from youtube import oauth

        self._signed(3)
        self.assertEqual(oauth.sign_in_mode("tapin"), "testing")
        self._signed(9)
        with patch.object(oauth, "load_credentials", return_value=object()):
            self.assertEqual(oauth.sign_in_mode("tapin"), "production")
            self.assertEqual(oauth.sign_in_reminder("tapin"), "")
            self.assertIn("In production", oauth.sign_in_mode_line("tapin"))
        with patch.object(oauth, "load_credentials", return_value=None):
            self.assertEqual(oauth.sign_in_mode("tapin"), "lapsed")
            self.assertIn("past that", oauth.sign_in_reminder("tapin"))

    def test_the_page_for_the_publish_click(self):
        import os

        from youtube import oauth

        self._signed(4)
        hint = oauth.publish_app_hint("tapin")
        self.assertIn("https://console.cloud.google.com/auth/audience?project=proj-123", hint)
        self.assertIn("sign in once more", hint)
        with patch.dict(os.environ, {"SIGN_IN_REMINDER_DAYS": "0"}):
            self.assertEqual(oauth.publish_app_hint("tapin"), "")

    def test_check_youtube_prints_it(self):
        from youtube import check_setup

        with (
            patch.object(check_setup, "publish_app_hint", return_value="Publish the app: URL"),
            patch.object(check_setup, "sign_in_mode_line", return_value="Testing - lapses Wed"),
            patch.object(check_setup, "load_credentials", return_value=object()),
        ):
            report = check_setup.check_channel_setup("tapin")
        self.assertIn("Publish the app: URL", report.hints)
        self.assertIn("Sign-in: Testing - lapses Wed", report.hints)


RUN_136_END = (
    "The Texans have a best-case scenario against the Titans on Sunday. I expect Houston's pass "
    "rush to exploit a shaky Titans offensive line and for the Texans to emerge victorious in "
    "convincing fashion on tennessee. Tap in for more."
)
RUN_150_OPENER = (
    "Justin Herbert threw for only 17 second-half points last game The Chargers' Super Bowl path "
    "is insane, but it's real. The defense has to hold."
)


class ScriptEndingTests(unittest.TestCase):
    """#1334: the last line complete - a stop, and no place written in lowercase (run 136)."""

    def test_run_136s_garbled_ending(self):
        from core.script_craft import unfinished_ending

        self.assertEqual(
            unfinished_ending(RUN_136_END), ['a place written in lowercase ("tennessee")']
        )

    def test_a_cut_off_last_line(self):
        from core.script_craft import unfinished_ending

        problems = unfinished_ending(
            "Houston wins this one. The real question is whether the line holds up"
        )
        self.assertEqual(len(problems), 1)
        self.assertIn("no stop", problems[0])

    def test_short_whole_endings_and_names_pass(self):
        from core.script_craft import unfinished_ending

        self.assertEqual(unfinished_ending("Pereira is out. Neither does Silva."), [])
        self.assertEqual(
            unfinished_ending("Kansas City visits Denver. That's where this game gets decided."), []
        )
        self.assertEqual(
            unfinished_ending("The city got 62 bucks back. Watch the magic happen."), []
        )


class RunOnTests(unittest.TestCase):
    """#1352: a sentence that runs into the next fails the script check (run 150's opener)."""

    def test_run_150s_opener(self):
        from core.script_craft import run_on_sentences

        self.assertEqual(len(run_on_sentences(RUN_150_OPENER)), 1)

    def test_a_title_mid_sentence_is_not_a_run_on(self):
        from core.script_craft import run_on_sentences

        self.assertEqual(
            run_on_sentences("Uncharted's magic came from the same guy who led The Lost Legacy."),
            [],
        )
        self.assertEqual(
            run_on_sentences("Fans spent the weekend deep in The Last of Us remake trailer again."),
            [],
        )

    def test_the_script_check_holds_both(self):
        from core.script_craft import script_check

        check = script_check(script=RUN_150_OPENER + " " + RUN_136_END)
        self.assertFalse(check["ok"])
        joined = " ".join(check["why"])
        self.assertIn("runs into the next", joined)
        self.assertIn("lowercase", joined)


class BufferRetryTests(CrosspostCase):
    """#1400: a send Buffer reports failed is sent once more; a second failure stays failed."""

    def setUp(self):
        super().setUp()
        self._first_then((113, "yt113"))  # post1 TikTok, post2 Instagram

    def _sync(self, posts):
        from publishing.crosspost import sync_status

        with patch("publishing.buffer_api.get_post", side_effect=lambda pid: posts[pid]):
            return sync_status("tapin")

    def _fail_tiktok(self, post_id="post1"):
        return self._sync({
            post_id: {"id": post_id, "status": "error", "error": {"message": "TikTok upload failed"}},
            "post2": {"id": "post2", "status": "scheduled"},
        })  # fmt: skip

    def test_a_failed_send_is_tried_again_once(self):
        from publishing.crosspost import send_due

        lines = self._fail_tiktok()
        tiktok = self._store()["posts"]["113"]["tiktok"]
        self.assertEqual((tiktok["state"], tiktok["retried"]), ("retry", 1))
        self.assertIn("sent again", " ".join(lines))
        self.assertTrue(any(ln.strip().startswith("!") for ln in lines))  # the #1399 toast
        self.remove.assert_not_called()
        made = self.made
        send_due("tapin")
        self.assertEqual(self.made, made + 1)
        tiktok = self._store()["posts"]["113"]["tiktok"]
        self.assertEqual((tiktok["state"], tiktok["retried"]), ("scheduled", 1))

    def test_a_second_failure_stays_failed(self):
        from publishing.crosspost import send_due

        self._fail_tiktok()
        send_due("tapin")
        resent = self._store()["posts"]["113"]["tiktok"]["post_id"]
        lines = self._fail_tiktok(resent)
        self.assertEqual(self._store()["posts"]["113"]["tiktok"]["state"], "error")
        self.assertNotIn("sent again", " ".join(lines))


if __name__ == "__main__":
    unittest.main()
