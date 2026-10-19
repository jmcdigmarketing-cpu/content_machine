"""Wave 115 (2026-10-19): the next ten.

Measured first: uploads stopped at 4 on 10-19 - 8,629 of 10,000 units, 1,200 of them three
caption files at 400 each; the unattended sync tried the "default" channel again, whose sign-in
file exists without the analytics permission; the first weekly compilation was scheduled public
without the AI disclosure, which the pre-publish check only warned about.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

NOW = datetime(2026, 10, 19, 22, 30, tzinfo=timezone.utc)
ANALYTICS = "https://www.googleapis.com/auth/yt-analytics.readonly"
UPLOAD = "https://www.googleapis.com/auth/youtube.upload"


class SyncScopeTests(unittest.TestCase):
    """#1523: the daily sync only for a channel signed in with the analytics permission."""

    def test_a_sign_in_without_analytics_is_skipped(self):
        from jobs import worker

        with tempfile.TemporaryDirectory() as tmp:
            paths = {}
            for cid, scopes in (("tapin", [UPLOAD, ANALYTICS]), ("default", [UPLOAD])):
                paths[cid] = os.path.join(tmp, f"{cid}.json")
                with open(paths[cid], "w", encoding="utf-8") as handle:
                    json.dump({"scopes": scopes}, handle)
            with (
                patch("config.channels.active_channel_ids", return_value=["tapin", "default"]),
                patch(
                    "youtube.oauth.token_path_for_channel", side_effect=lambda cid=None: paths[cid]
                ),
                patch("analytics.sync_metrics.maybe_sync") as sync,
            ):
                worker._sync_metrics()
        sync.assert_called_once_with("tapin")


class DisclosureAtUploadTests(unittest.TestCase):
    """#1524 (the operator: append it): an upload without the AI line gets it, not a warning."""

    def _request(self, description):
        from publishing.base import PublishRequest

        return PublishRequest(file_path="v.mp4", title="Week in Review", description=description)

    def test_a_missing_line_is_appended(self):
        from publishing import prepublish

        line = "Made with AI-assisted narration and editing."
        with patch.object(prepublish, "_disclosure_line", return_value=line):
            fixed, added = prepublish.with_disclosure(
                self._request("Every Short.\n\n0:00 One"), "tapin"
            )
            same, again = prepublish.with_disclosure(self._request(f"Body.\n\n{line}"), "tapin")
        self.assertTrue(added)
        self.assertTrue(fixed.description.endswith(line))
        self.assertIn("0:00 One", fixed.description)
        self.assertFalse(again)
        self.assertEqual(same.description, f"Body.\n\n{line}")

    def test_no_line_set_changes_nothing(self):
        from publishing import prepublish

        with patch.object(prepublish, "_disclosure_line", return_value=""):
            request, added = prepublish.with_disclosure(self._request("Body."), "tapin")
        self.assertFalse(added)
        self.assertEqual(request.description, "Body.")

    def test_the_publisher_appends_before_the_checklist(self):
        import inspect

        from publishing import youtube_publisher

        source = inspect.getsource(youtube_publisher)
        self.assertLess(source.index("with_disclosure("), source.index("prepublish.checklist("))


class CaptionQuotaTests(unittest.TestCase):
    """#1525 (the operator: only when quota allows): a caption file is 400 units."""

    def _upload(self, remaining):
        from youtube import captions

        service = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            track = os.path.join(tmp, "v.vtt")
            with open(track, "w", encoding="utf-8") as handle:
                handle.write("WEBVTT\n")
            with (
                patch(
                    "apis.youtube_quota.get_usage_summary", return_value={"remaining": remaining}
                ),
                patch("apis.youtube_quota.record_usage"),
                patch.object(captions, "MediaFileUpload", MagicMock()),
            ):
                result = captions.maybe_upload_captions(service, video_id="abc", caption_path=track)
        return result, service

    def test_it_keeps_an_uploads_units(self):
        result, service = self._upload(1_371)
        self.assertEqual(result.status, "skipped")
        self.assertIn("upload", result.detail)
        service.captions.assert_not_called()

    def test_with_room_it_goes_up(self):
        result, service = self._upload(6_000)
        self.assertEqual(result.status, "set")
        service.captions.return_value.insert.assert_called_once()

    def test_the_rule_itself(self):
        from youtube.captions import caption_quota_ok

        self.assertTrue(caption_quota_ok(2_000))
        self.assertFalse(caption_quota_ok(1_999))


class SignInDateTests(unittest.TestCase):
    """#1437: the sign-in's lapse date every day, not only from day 5."""

    def _token(self, tmp, stamp):
        path = os.path.join(tmp, "t.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"signed_in_at": stamp} if stamp else {}, handle)
        return path

    def test_the_date_is_seven_days_on(self):
        from youtube import oauth

        with tempfile.TemporaryDirectory() as tmp:
            path = self._token(tmp, "2026-10-15T01:36:30+00:00")
            with patch.object(oauth, "token_path_for_channel", return_value=path):
                when = oauth.sign_in_expiry("tapin")
                with patch(
                    "analytics.post_timing.format_scheduled_local", return_value="Wed 9:36 PM EDT"
                ):
                    line = oauth.sign_in_expiry_line("tapin", now=NOW)
        self.assertEqual(when, datetime(2026, 10, 22, 1, 36, 30, tzinfo=timezone.utc))
        self.assertEqual(line, "lapses Wed 9:36 PM EDT unless the app is published")

    def test_quiet_when_published_or_unknown(self):
        from youtube import oauth

        with tempfile.TemporaryDirectory() as tmp:
            path = self._token(tmp, "2026-10-15T01:36:30+00:00")
            with (
                patch.object(oauth, "token_path_for_channel", return_value=path),
                patch.dict(os.environ, {"SIGN_IN_REMINDER_DAYS": "0"}),
            ):
                self.assertEqual(oauth.sign_in_expiry_line("tapin", now=NOW), "")
            bare = self._token(tmp, "")
            with patch.object(oauth, "token_path_for_channel", return_value=bare):
                self.assertEqual(oauth.sign_in_expiry_line("tapin", now=NOW), "")

    def test_the_status_line_carries_it(self):
        from core import status_summary

        with (
            patch("youtube.oauth.sign_in_status", return_value=""),
            patch("youtube.oauth.sign_in_reminder", return_value=""),
            patch(
                "youtube.oauth.sign_in_expiry_line",
                return_value="lapses Wed 9:36 PM EDT unless the app is published",
            ),
        ):
            line = status_summary._sign_in("tapin")
        self.assertEqual(
            line, "Sign-in: ok (tapin) - lapses Wed 9:36 PM EDT unless the app is published"
        )


WORKER_LOG = """--- 2026-10-19T17:07:01 worker pass
Job 73 scheduled -> https://youtu.be/2dsGGwnpPSA
--- 2026-10-19T17:22:01 worker pass
YouTube upload blocked today - ~1,371 units remaining today (8,629/10,000 used)
"""


class WorkerPassTests(unittest.TestCase):
    """#1402: the upload worker's last pass, in the morning."""

    def test_the_last_pass_and_what_it_did(self):
        from jobs.worker_log import last_pass_line

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "worker_task.log")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(WORKER_LOG)
            line = last_pass_line(path, now=datetime(2026, 10, 19, 17, 30))
            stale = last_pass_line(path, now=datetime(2026, 10, 19, 23, 30))
            missing = last_pass_line(
                os.path.join(tmp, "none.log"), now=datetime(2026, 10, 19, 17, 30)
            )
        self.assertEqual(line, "last pass 17:22 - uploads blocked by quota until the reset")
        self.assertIn("6 h ago", stale)
        self.assertEqual(missing, "")

    def test_sent_and_nothing(self):
        from jobs.worker_log import summarize_pass

        self.assertEqual(summarize_pass(["Job 70 uploaded -> x", "Job 72 scheduled -> y", "Sent 3 due job(s)"]),
                         "2 sent")  # fmt: skip
        self.assertEqual(summarize_pass(["No pending jobs."]), "nothing waiting")


class SubscriberFlagTests(unittest.TestCase):
    """#1325: a video that brings 2+ subscribers is named, with a follow-up suggested."""

    def test_it_names_the_video(self):
        from analytics.growth import subscriber_flags

        rows = [{"title": "Vanguard meta", "subs": 1, "run_id": 1}, {"title": "GTA box", "subs": 3, "run_id": 2},
                {"title": "Topuria", "subs": 2, "run_id": 3}]  # fmt: skip
        self.assertEqual([r["title"] for r in subscriber_flags(rows)], ["GTA box", "Topuria"])
        from analytics.growth import subscriber_flag_line

        line = subscriber_flag_line(rows)
        self.assertTrue(line.startswith("Brought 2+ subscribers: GTA box (3), Topuria (2)"), line)
        self.assertEqual(subscriber_flag_line(rows[:1]), "")


class ToastTests(unittest.TestCase):
    """C: #1399 a failed Buffer send, #1372 a missed overnight - told once a day, not found."""

    def test_a_toast_once_a_day_across_processes(self):
        from core import win_notify

        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(win_notify, "TOAST_DAYS_FILE", os.path.join(tmp, "days.json")),
                patch.object(win_notify, "toast", return_value=True) as shown,
            ):
                first = win_notify.toast_daily(
                    "buffer:tapin", "t", "b", now=datetime(2026, 10, 19, 9)
                )
                again = win_notify.toast_daily(
                    "buffer:tapin", "t", "b", now=datetime(2026, 10, 19, 18)
                )
                next_day = win_notify.toast_daily(
                    "buffer:tapin", "t", "b", now=datetime(2026, 10, 20, 9)
                )
        self.assertEqual((first, again, next_day), (True, False, True))
        self.assertEqual(shown.call_count, 2)

    def test_a_toast_that_did_not_show_is_not_stamped(self):
        from core import win_notify

        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(win_notify, "TOAST_DAYS_FILE", os.path.join(tmp, "days.json")),
                patch.object(win_notify, "toast", side_effect=[False, True]) as shown,
            ):
                win_notify.toast_daily("k", "t", "b", now=datetime(2026, 10, 19, 9))
                self.assertTrue(
                    win_notify.toast_daily("k", "t", "b", now=datetime(2026, 10, 19, 10))
                )
        self.assertEqual(shown.call_count, 2)

    def test_a_failed_buffer_send_toasts(self):
        from publishing import crosspost

        with (
            patch.object(crosspost, "auto_enabled", return_value=True),
            patch("publishing.buffer_api.configured", return_value=True),
            patch.object(crosspost, "setup_missing", return_value=[]),
            patch("publishing.platform_metrics.refresh"),
            patch.object(crosspost, "sync_status", return_value=[]),
            patch.object(
                crosspost,
                "send_due",
                return_value=["  ! run 173 TikTok: Buffer refused it - bad video"],
            ),
            patch("core.win_notify.toast_daily") as toast,
        ):
            crosspost.step("tapin")
        toast.assert_called_once()
        self.assertIn("run 173 TikTok: Buffer refused it", toast.call_args.args[2])

    def test_overnight_overdue_after_26_hours(self):
        from core import nightly_task

        with patch.object(
            nightly_task, "_recorded_start", return_value=datetime(2026, 10, 19, 5, 0, 2)
        ):
            self.assertEqual(nightly_task.overdue_line(now=datetime(2026, 10, 20, 6, 0)), "")
            line = nightly_task.overdue_line(now=datetime(2026, 10, 20, 8, 0))
        self.assertTrue(
            line.startswith("Overnight has not run for 27 hours (last started Mon 05:00)"), line
        )

    def test_the_worker_watches_it(self):
        from jobs import worker

        with (
            patch(
                "core.nightly_task.overdue_line", return_value="Overnight has not run for 27 hours"
            ),
            patch("core.win_notify.toast_daily") as toast,
        ):
            worker._overnight_watch()
        toast.assert_called_once()
        self.assertEqual(toast.call_args.args[0], "overnight-missed")


class CompilationLinkTests(unittest.TestCase):
    """D: #1317 (the operator: new uploads only) - a Short links the week's compilation."""

    def _request(self, description="A Short."):
        from publishing.base import PublishRequest

        return PublishRequest(file_path="v.mp4", title="A Short", description=description)

    def test_a_short_gets_the_link_once_a_compilation_is_public(self):
        from publishing import prepublish

        with (
            patch("video.week_compile.latest_public_compilation", return_value="xpPz3ewlNJ8"),
            patch.object(prepublish, "_is_compilation", return_value=False),
        ):
            got, added = prepublish.with_compilation_link(self._request(), "tapin", 175)
            again, twice = prepublish.with_compilation_link(got, "tapin", 175)
        self.assertTrue(added)
        self.assertIn("Full week: https://youtu.be/xpPz3ewlNJ8", got.description)
        self.assertFalse(twice)
        self.assertEqual(again.description, got.description)

    def test_none_public_or_the_compilation_itself_adds_nothing(self):
        from publishing import prepublish

        with patch("video.week_compile.latest_public_compilation", return_value=""):
            self.assertFalse(prepublish.with_compilation_link(self._request(), "tapin", 175)[1])
        with (
            patch("video.week_compile.latest_public_compilation", return_value="xpPz3ewlNJ8"),
            patch.object(prepublish, "_is_compilation", return_value=True),
        ):
            self.assertFalse(prepublish.with_compilation_link(self._request(), "tapin", 172)[1])

    def test_the_latest_public_compilation(self):
        from video import week_compile

        rows = [SimpleNamespace(content_run_id=172, youtube_video_id="xpPz3ewlNJ8", privacy_status="public",
                                published_at=datetime(2026, 10, 21, 16, tzinfo=timezone.utc)),
                SimpleNamespace(content_run_id=150, youtube_video_id="short", privacy_status="public",
                                published_at=datetime(2026, 10, 20, 16, tzinfo=timezone.utc))]  # fmt: skip
        runs = {172: SimpleNamespace(features_json=json.dumps({"compilation": {"week": "2026-10-19"}})),
                150: SimpleNamespace(features_json="{}")}  # fmt: skip
        with (
            patch("storage.repositories.publish_log.get_publish_log_repository",
                  return_value=SimpleNamespace(list_uploaded_for_channel=lambda c: rows)),
            patch("storage.repositories.content_runs.get_content_run_repository",
                  return_value=SimpleNamespace(get=lambda rid: runs.get(rid))),
        ):  # fmt: skip
            self.assertEqual(week_compile.latest_public_compilation("tapin"), "xpPz3ewlNJ8")


if __name__ == "__main__":
    unittest.main()
