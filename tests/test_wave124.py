"""Wave 124 (2026-10-23 evening): the next ten.

Measured first, on Fri 10-23 at 17:50 CDT: the PC had been shut down Thu at 9:51 PM, so overnight
ran at 5:52 PM when it came on. The sign-in had been lapsed since 10-21, holding three uploads, and
one of them was run 181, a Cavaliers-76ers preview whose game tipped off Thu at 7 PM EDT - nothing
in the worker, the shelf or go-public checked that. Run 176, the UFC 333 preview for Saturday, read
"3 days old, past its window", and batch-review's Enter would have set it aside. Over 22 videos the
hook score ran against the share who stayed (r = -0.48, past p<0.05) while it was 28% of the grade
and chose which draft overnight rendered first.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, ClassVar
from unittest.mock import MagicMock, patch

NOW = datetime(2026, 10, 23, 22, 52, tzinfo=timezone.utc)  # Fri 6:52 PM EDT
TIP = datetime(2026, 10, 22, 23, 0, tzinfo=timezone.utc)  # Cavaliers at 76ers, Thu 7 PM EDT
UFC333 = datetime(2026, 10, 24, 17, 0, tzinfo=timezone.utc)
RUN181 = "Cleveland Cavaliers vs 76ers: Opening Tip Preview | Oct 22 Hoops"


def _job(**extra):
    payload = {"file_path": "v.mp4", "title": RUN181, "privacy_status": "unlisted"}
    return SimpleNamespace(
        id=77,
        content_run_id=181,
        channel_id="tapin",
        job_type="upload",
        status="running",
        attempts=0,
        last_error="held - the YouTube sign-in has ended: sign in again",
        payload_json=json.dumps(payload),
        **extra,
    )


class AfterItsGameTests(unittest.TestCase):
    """#1547: nothing uploads, schedules or publishes a preview after its game."""

    def _upload(self, event):
        from jobs import worker

        repo = MagicMock()
        runs = MagicMock()
        runs.get.return_value = SimpleNamespace(id=181, title=RUN181, mp4_path="")
        publisher = MagicMock()
        publisher.publish.return_value = SimpleNamespace(status="auth_error", detail="x")
        with (
            patch("core.rpm_cost_gate.rpm_cost_gate_reason", return_value=None),
            patch.object(worker, "get_publisher", return_value=publisher),
            patch.object(worker, "get_job_repository", return_value=repo),
            patch.object(worker, "get_content_run_repository", return_value=runs),
            patch.object(worker, "_finalize_upload_job"),
            patch("core.spaced_queue.preview_event", return_value=event),
            patch("core.stale_renders._now", return_value=NOW),
            patch("builtins.print") as said,
        ):
            worker._process_upload(_job())
        return repo, publisher, said

    def test_the_worker_takes_run_181_off_the_queue(self):
        repo, publisher, said = self._upload(TIP)
        publisher.publish.assert_not_called()
        fields = repo.update.call_args.args[1]
        self.assertEqual(fields["status"], "failed")
        self.assertIn("its game started Thu Oct 22 7:00 PM EDT", fields["last_error"])
        self.assertIn("nothing uploads it (the file stays)", fields["last_error"])
        self.assertIn("run 181", said.call_args.args[0])

    def test_the_morning_says_it(self):
        from jobs.worker_log import summarize_pass

        line = ("Upload job 77 (run 181) taken off the queue: its game started Thu Oct 22 7:00 PM "
                "EDT - nothing uploads it (the file stays)")  # fmt: skip
        self.assertEqual(
            summarize_pass([line]), "a preview after its game taken off the queue (ops shelf)"
        )

    def test_a_preview_before_its_game_still_uploads(self):
        _repo, publisher, _said = self._upload(UFC333)
        publisher.publish.assert_called_once()

    def test_a_video_with_no_event_uploads(self):
        _repo, publisher, _said = self._upload(None)
        publisher.publish.assert_called_once()

    def _shelf(self, event, *, age=1.0):
        from core import stale_renders

        run = SimpleNamespace(id=181, title=RUN181)
        job = SimpleNamespace(content_run_id=181)
        with (
            patch("scripts.requeue_upload.list_recyclable", return_value=[run]),
            patch.object(stale_renders, "render_age_days", return_value=age),
            patch.object(stale_renders, "_queued_runs", return_value={181: job}),
            patch.object(stale_renders, "_signed_out", return_value=True),
            patch.object(stale_renders, "_news_window", return_value=2.0),
            patch.object(stale_renders, "_now", return_value=NOW),
            patch("publishing.go_public.unlisted_holds", return_value=[]),
            patch("publishing.go_public.override_held", return_value=False),
            patch("core.spaced_queue.preview_event", return_value=event),
        ):
            return stale_renders.shelf_rows("tapin"), stale_renders.shelf("tapin")

    def test_the_shelf_says_a_queued_preview_is_over(self):
        rows, counts = self._shelf(TIP)
        self.assertIn("its game has started", rows[0]["state"])
        self.assertTrue(rows[0]["stale"])  # it no longer holds one of overnight's three places
        self.assertEqual(counts.get("past_window"), 1)
        self.assertEqual(counts["queued"], 0)

    def test_a_queued_preview_before_its_game_waits_on_the_sign_in(self):
        rows, counts = self._shelf(UFC333)
        self.assertEqual(rows[0]["state"], "queued - the YouTube sign-in has expired")
        self.assertEqual(counts["queued"], 1)

    def test_a_rendered_preview_is_current_until_its_game(self):
        # The sibling of #1548 on the shelf: 5 days old on a 2-day window, its game tomorrow.
        from core import stale_renders

        with patch.object(stale_renders, "_queued_runs", return_value={}):
            run = SimpleNamespace(id=180, title="Coach Conversation: Volkanovski vs Evloev Preview")
            with (
                patch("scripts.requeue_upload.list_recyclable", return_value=[run]),
                patch.object(stale_renders, "render_age_days", return_value=5.0),
                patch.object(stale_renders, "_news_window", return_value=2.0),
                patch.object(stale_renders, "_now", return_value=NOW),
                patch("publishing.go_public.unlisted_holds", return_value=[]),
                patch("core.spaced_queue.preview_event", return_value=UFC333),
            ):
                rows = stale_renders.shelf_rows("tapin")
        self.assertEqual(rows[0]["state"], "rendered, never uploaded")

    def test_an_unlisted_preview_after_its_game_is_not_offered(self):
        from core import stale_renders

        hold = SimpleNamespace(content_run_id=181, youtube_video_id="cav76")
        runs = MagicMock()
        runs.get.return_value = SimpleNamespace(id=181, title=RUN181, mp4_path="")
        with (
            patch("scripts.requeue_upload.list_recyclable", return_value=[]),
            patch.object(stale_renders, "_queued_runs", return_value={}),
            patch.object(stale_renders, "_now", return_value=NOW),
            patch.object(stale_renders, "_upload_title", return_value=RUN181),
            patch("publishing.go_public.unlisted_holds", return_value=[hold]),
            patch("publishing.go_public.override_held", return_value=False),
            patch(
                "storage.repositories.content_runs.get_content_run_repository", return_value=runs
            ),
            patch("core.spaced_queue.preview_event", return_value=TIP),
        ):
            rows = stale_renders.shelf_rows("tapin")
        self.assertIn("its game has started", rows[0]["state"])
        self.assertNotIn("go-public", rows[0]["command"])
        self.assertTrue(rows[0]["stale"])

    def test_one_ladder_decides_the_state(self):
        from core.stale_renders import shelf_state

        kw = {"signed_out": True, "reset": "", "age": 1.0, "days": 30, "window": 2.0}
        self.assertEqual(shelf_state(queued=True, started=True, ahead=False, **kw), "started")
        self.assertEqual(shelf_state(queued=True, started=False, ahead=True, **kw), "signed_out")
        kw["age"] = 5.0
        self.assertEqual(shelf_state(queued=False, started=False, ahead=True, **kw), "rendered")
        self.assertEqual(shelf_state(queued=False, started=False, ahead=False, **kw), "past_window")

    def _go_public(self, fn, **kw):
        from publishing import go_public
        from storage.repositories.publish_log import PublishLogRecord

        row = PublishLogRecord(
            id=9,
            content_run_id=181,
            channel_id="tapin",
            youtube_video_id="cav76",
            privacy_status="unlisted",
            status="uploaded",
        )
        repo = MagicMock()
        repo.list_uploaded_for_channel.return_value = [row]
        run = SimpleNamespace(id=181, title=RUN181, mp4_path="")
        with (
            patch("publishing.go_public.load_features", return_value={}),
            patch.object(go_public, "_run_for_hold", return_value=run),
            patch.object(go_public, "_run_title", return_value=RUN181),
            patch("core.spaced_queue.preview_event", return_value=TIP),
            patch("core.stale_renders._now", return_value=NOW),
            patch("youtube.oauth.get_youtube_service") as svc,
        ):
            result = getattr(go_public, fn)("cav76", channel_id="tapin", repo=repo, **kw)
        svc.assert_not_called()
        return result

    def test_go_public_refuses_it(self):
        result = self._go_public("apply_go_public", dry_run=False)
        self.assertEqual(result.status, "refused")
        self.assertIn("its game started Thu Oct 22 7:00 PM EDT", result.detail)

    def test_the_dry_run_says_so_too(self):
        self.assertEqual(self._go_public("apply_go_public").status, "refused")

    def test_scheduling_it_public_is_refused(self):
        result = self._go_public("apply_schedule_public", when=NOW + timedelta(hours=3))
        self.assertEqual(result.status, "refused")


def _draft_meta(
    days_old,
    *,
    event=None,
    title="Volkanovski's Experience vs Evloev's Momentum in UFC 333 Preview",
):
    made = datetime.now() - timedelta(days=days_old)
    meta = {"run_id": 176, "created_at": made.isoformat(), "topic": title, "title": title}
    if event is not None:
        meta["event_at"] = event.strftime("%Y-%m-%dT%H:%MZ")
    return meta


class CurrentUntilItsEventTests(unittest.TestCase):
    """#1548: a preview is current until its event, not for its 2-day news window."""

    AHEAD = datetime.now(timezone.utc) + timedelta(days=1)

    def test_run_176_is_not_past_its_window(self):
        from core.batch_review import dead_reason

        self.assertEqual(dead_reason(_draft_meta(3, event=self.AHEAD)), "")

    def test_news_without_an_event_still_ages(self):
        from core.batch_review import dead_reason

        self.assertIn("past its window", dead_reason(_draft_meta(3)))

    def test_after_its_event_it_is_dead(self):
        from core.batch_review import dead_reason

        gone = datetime.now(timezone.utc) - timedelta(hours=2)
        self.assertTrue(dead_reason(_draft_meta(3, event=gone)).startswith("its game has started"))

    def test_overnight_does_not_set_it_aside(self):
        from core.batch_review import expire_old_drafts

        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        for name, meta in (
            ("176", _draft_meta(5, event=self.AHEAD)),
            ("177", dict(_draft_meta(5, title="Petr Yan's coach on UFC news"), run_id=177)),
        ):
            folder = os.path.join(root, name)
            os.makedirs(folder)
            with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as f:
                json.dump(meta, f)
            with open(os.path.join(folder, "draft.md"), "w", encoding="utf-8") as f:
                f.write("## Script\nUFC 333 is Saturday.\n")
        gone = expire_old_drafts("tapin", root=root, apply=False)
        self.assertEqual([d.run_id for d in gone], [177])


class HookScoreOutTests(unittest.TestCase):
    """#1499 (the operator, 2026-10-23: out of the grade and the order) - decision 70."""

    QUALITY: ClassVar[dict[str, Any]] = {"authenticity_score": 80, "ungrounded_count": 0}

    def test_the_rubric_is_v6(self):
        from core.video_grade import GRADE_VERSION

        self.assertEqual(GRADE_VERSION, "v6")

    def test_the_hook_score_no_longer_moves_the_grade(self):
        from core.video_grade import grade_from_parts

        low = grade_from_parts(quality={**self.QUALITY, "hook_score": 10})
        high = grade_from_parts(quality={**self.QUALITY, "hook_score": 95})
        self.assertEqual(low.score, high.score)
        hook = next(c for c in high.components if c.name == "hook")
        self.assertEqual(hook.weight, 0.0)
        self.assertIn("not counted", hook.note)

    def test_overnight_renders_a_game_then_the_newest(self):
        from core import batch_review
        from core.batch_review import PendingDraft

        now = datetime.now()
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        drafts = [
            PendingDraft("a", {"run_id": 1, "hook_score": 95, "created_at": (now - timedelta(days=2)).isoformat()}, "s"),
            PendingDraft("b", {"run_id": 2, "hook_score": 40, "created_at": (now - timedelta(hours=1)).isoformat()}, "s"),
            PendingDraft("c", {"run_id": 3, "hook_score": 10, "created_at": (now - timedelta(days=1)).isoformat(),
                               "event_at": tomorrow.strftime("%Y-%m-%dT%H:%MZ")}, "s"),
        ]  # fmt: skip
        with (
            patch.object(batch_review, "pending_drafts", return_value=drafts),
            patch.object(batch_review, "unattended_block_reason", return_value=""),
        ):
            eligible, _skipped = batch_review.unattended_candidates("tapin")
        self.assertEqual([d.run_id for d in eligible], [3, 2, 1])


SHUT = ("shut down", datetime(2026, 10, 22, 21, 51))


class PowerOnTests(unittest.TestCase):
    """Decision 69 (the operator, 2026-10-23: power-on is fine): no "leave it asleep" ask."""

    def test_a_late_run_reads_as_a_fact(self):
        from core.nightly_task import late_short

        times = {"last": datetime(2026, 10, 23, 17, 52), "start": (5, 0)}
        line = late_short(times, now=datetime(2026, 10, 23, 18, 0), off=SHUT)
        self.assertEqual(
            line, "ran Fri 5:52 PM, when the PC came on - the PC was shut down Thu 9:51 PM"
        )

    def test_a_run_not_yet_made_says_when_it_will_be(self):
        from core.nightly_task import late_short

        times = {"last": datetime(2026, 10, 22, 16, 52), "start": (5, 0)}
        line = late_short(times, now=datetime(2026, 10, 23, 17, 0), off=SHUT)
        self.assertEqual(
            line,
            "did not run at 5:00 AM Fri - the PC was shut down Thu 9:51 PM; it runs when the PC "
            "comes on",
        )

    def test_overnight_last_says_it_too(self):
        from core.nightly_task import missed_line

        times = {"last": datetime(2026, 10, 23, 17, 52), "start": (5, 0)}
        line = missed_line(times, now=datetime(2026, 10, 23, 18, 0), wakes=True, off=SHUT)
        self.assertIn("it runs when the PC comes on", line)
        self.assertNotIn("Sleep", line)

    def test_tonight_asks_nothing(self):
        from core.nightly_task import tonight_text

        line = tonight_text(3, 2, (5, 0))
        self.assertEqual(
            line, "Tonight at 5:00 AM (or when the PC is next on): drafts 3, renders up to 2"
        )
        paused = tonight_text(
            3, 2, (5, 0), paused="3 finished videos are waiting (overnight stops at 3)"
        )
        self.assertNotIn("asleep", paused)

    def test_the_doctor_names_the_shutdown_without_advice(self):
        from core import nightly_task

        with (
            patch.object(nightly_task, "task_wakes", return_value=True),
            patch.object(nightly_task, "wake_timers", return_value={"ac": "on"}),
            patch.object(nightly_task, "_queried_times", return_value={"start": (5, 0)}),
            patch.object(nightly_task, "_last_off", return_value=SHUT),
        ):
            ok, line = nightly_task.wake_doctor(now=datetime(2026, 10, 23, 18, 0))
        self.assertTrue(ok)
        self.assertIn("shut down Thu 9:51 PM", line)
        self.assertNotIn("use Sleep", line)


def _hook_row(hook, stayed, *, first3=None, tiktok=None):
    from analytics.hook_learning import traits_of

    return {"run_id": 1, "hook": hook, "score": 50.0, "traits": traits_of(hook), "stayed": stayed,
            "words": len(hook.split()), "first3": first3, "tiktok_s": tiktok}  # fmt: skip


class HookTableTests(unittest.TestCase):
    """#1500 #1501 #1505 #1506: each opener trait against who stayed, the 3-second share and
    TikTok's watch time; the opener's length against who stayed."""

    ROWS: ClassVar[list[dict[str, Any]]] = [
        _hook_row("Is Jalen Hurts the best?", 0.45, first3=0.80, tiktok=2.4),
        _hook_row("Can Detroit really win it all this year?", 0.42, first3=0.75, tiktok=2.1),
        _hook_row("Why does Volkanovski keep winning?", 0.40, first3=0.70, tiktok=2.0),
        _hook_row("UFC 333 has 3 title fights and one of them is a mismatch for sure", 0.30, first3=0.60, tiktok=1.2),
        _hook_row("The Pistons scored 23 straight points against Boston's bench on Sunday", 0.20, first3=0.55, tiktok=1.0),
        _hook_row("GTA 6 sold 10 million copies in its first day on sale", 0.18, first3=0.50, tiktok=0.9),
    ]  # fmt: skip

    def test_every_trait_with_and_without(self):
        from analytics.hook_learning import hook_table

        table = hook_table(self.ROWS)
        question = next(t for t in table["traits"] if t["trait"] == "a question")
        self.assertEqual(question["stayed"]["n_with"], 3)
        self.assertAlmostEqual(question["stayed"]["with"], 0.42)
        self.assertAlmostEqual(question["stayed"]["without"], 0.20)
        self.assertAlmostEqual(question["first3"]["with"], 0.75)  # #1501
        self.assertAlmostEqual(question["tiktok"]["without"], 1.0)  # #1506

    def test_a_call_is_one_of_the_traits(self):
        from analytics.hook_learning import hook_table

        self.assertIn("a call", {t["trait"] for t in hook_table(self.ROWS)["traits"]})

    def test_a_thin_side_has_no_median(self):
        from analytics.hook_learning import hook_table

        rows = self.ROWS[:4]
        number = next(t for t in hook_table(rows)["traits"] if t["trait"] == "a number")
        self.assertIsNone(number["stayed"]["with"])  # one opener with a number

    def test_length_in_bins(self):
        from analytics.hook_learning import hook_table

        table = hook_table(self.ROWS)
        bins = {b["bin"]: b for b in table["length"]}
        self.assertEqual(bins["8 words or fewer"]["n"], 3)
        self.assertEqual(bins["9-12 words"]["n"], 2)
        self.assertEqual(bins["13-16 words"]["n"], 1)
        self.assertLess(table["length_r"], 0)  # longer held fewer here

    def test_the_lines(self):
        from analytics import hook_learning

        with patch.object(hook_learning, "_rows", return_value=self.ROWS):
            lines = hook_learning.hook_table_lines("tapin")
            length = hook_learning.length_line("tapin")
        text = "\n".join(lines)
        self.assertIn("a question", text)
        self.assertIn("3 s", text)
        self.assertIn("TikTok", text)
        self.assertIn("8 words or fewer", length)
        self.assertIn("r=", length)

    def test_the_detail_of_one_video(self):
        from analytics.hook_learning import detail_of

        curve = [[0.0, 1.0], [0.1, 0.8], [0.2, 0.6], [1.0, 0.2]]
        got = detail_of(
            "Is Jalen Hurts the best?",
            {"retention_curve": curve},
            {"tiktok": {"measured": True, "avg_watch_s": 2.4}},
            30.0,
        )
        self.assertAlmostEqual(got["first3"], 0.8)
        self.assertEqual(got["tiktok_s"], 2.4)
        self.assertEqual(got["words"], 5)
        replayed = detail_of(
            "x", {"retention_curve": [[0.0, 1.4], [0.1, 1.2], [1.0, 0.3]]}, {}, 30.0
        )
        self.assertIsNone(replayed["first3"])  # over 100%: replays, not a share
        self.assertIsNone(replayed["tiktok_s"])

    def test_share_at(self):
        from core.retention import share_at

        self.assertAlmostEqual(share_at([(0.0, 1.0), (0.1, 0.8), (1.0, 0.2)], 30.0), 0.8)
        self.assertIsNone(share_at([], 30.0))
        self.assertIsNone(share_at([(0.0, 1.0)], 2.0))

    def test_ops_hooks_is_registered(self):
        from scripts.ops import COMMANDS

        self.assertIn("hooks", COMMANDS)


class CurveStateTests(unittest.TestCase):
    """#1546: why a video has no retention curve is recorded, and the audit names it."""

    def _service(self, answer):
        service = MagicMock()

        def query(**kw):
            out = MagicMock()
            if kw.get("metrics") == "audienceWatchRatio":
                if isinstance(answer, Exception):
                    out.execute.side_effect = answer
                else:
                    out.execute.return_value = answer
            else:
                out.execute.return_value = {"rows": []}
            return out

        service.reports.return_value.query.side_effect = query
        return service

    def test_no_rows_is_recorded(self):
        from analytics.youtube_metrics import _curve_with_state

        curve, state = _curve_with_state(
            "v", self._service({"rows": []}), "2026-09-25", "2026-10-23"
        )
        self.assertIsNone(curve)
        self.assertEqual(state, {"asked": "2026-10-23", "rows": 0})

    def test_an_error_is_recorded(self):
        from analytics.youtube_metrics import _curve_with_state

        _curve, state = _curve_with_state(
            "v", self._service(RuntimeError("403 forbidden")), "a", "2026-10-23"
        )
        self.assertEqual(state["asked"], "2026-10-23")
        self.assertIn("403", state["error"])

    def test_a_curve_is_recorded(self):
        from analytics.youtube_metrics import _curve_with_state

        curve, state = _curve_with_state(
            "v", self._service({"rows": [[0.0, 1.0], [1.0, 0.3]]}), "a", "b"
        )
        self.assertEqual(curve, [[0.0, 1.0], [1.0, 0.3]])
        self.assertEqual(state["rows"], 2)

    def test_the_sync_stores_it(self):
        from analytics import youtube_metrics

        report = {"columnHeaders": [{"name": "video"}, {"name": "views"}], "rows": [["v", 60]]}
        service = self._service({"rows": []})
        headline = MagicMock()
        headline.execute.return_value = report
        query = service.reports.return_value.query.side_effect

        def routed(**kw):
            return headline if kw.get("dimensions") == "video" else query(**kw)

        service.reports.return_value.query.side_effect = routed
        with (
            patch.object(youtube_metrics, "_analytics_enabled", return_value=True),
            patch.object(youtube_metrics, "get_youtube_analytics_service", return_value=service),
        ):
            got = youtube_metrics.fetch_video_metrics("v", channel_id="tapin")
        self.assertEqual(got["retention_curve_state"]["rows"], 0)

    def _row(self, run_id, published, metrics, privacy="public"):
        return SimpleNamespace(
            content_run_id=run_id,
            published_at=published,
            privacy_status=privacy,
            metrics_json=json.dumps(metrics) if metrics is not None else None,
        )

    def test_the_audit_says_why(self):
        from analytics.field_audit import audit_lines

        day = timedelta(days=1)
        rows = [
            self._row(1, NOW - 10 * day, {"views": 60, "retention_curve": [[0, 1]], "views_until": "2026-10-22"}),
            self._row(2, NOW - 10 * day, {"views": 60, "views_until": "2026-10-14"}),  # its first days
            self._row(3, NOW - 10 * day, {"views": 60, "views_until": "2026-10-22",
                                          "retention_curve_state": {"asked": "2026-10-22", "rows": 0}}),
            self._row(4, NOW - 10 * day, {"views": 60, "views_until": "2026-10-22",
                                          "retention_curve_state": {"asked": "2026-10-22", "error": "403"}}),
            self._row(5, NOW - 6 * day, None),  # never synced
            self._row(6, NOW - 5 * day, {"lifetime_views": 40}),  # the Data API's count is no sync
        ]  # fmt: skip
        text = "\n".join(audit_lines([], rows, now=NOW))
        self.assertIn("retention_curve missing on 3 of 4", text)
        self.assertIn("1 synced only in its first 3 days", text)
        self.assertIn("1 YouTube gave no curve", text)
        self.assertIn("1 failed", text)
        self.assertIn("2 public videos under 28 days never synced (runs 5, 6)", text)
        self.assertNotIn("views on", text)  # the four synced all carry views


class GpuDriverTests(unittest.TestCase):
    """#1470: the GPU and its driver in `ops doctor`."""

    def test_the_driver_is_read(self):
        from core import cuda_probe

        done = SimpleNamespace(stdout="NVIDIA GeForce RTX 4070 Ti, 616.92\n", returncode=0)
        with (
            patch("shutil.which", return_value="nvidia-smi"),
            patch("subprocess.run", return_value=done) as run,
        ):
            self.assertEqual(cuda_probe.gpu_driver(), ("NVIDIA GeForce RTX 4070 Ti", "616.92"))
        self.assertIn("--query-gpu=name,driver_version", run.call_args.args[0])

    def test_no_nvidia_smi(self):
        from core import cuda_probe

        with patch("shutil.which", return_value=None):
            self.assertIsNone(cuda_probe.gpu_driver())

    def test_the_doctor_row(self):
        from core.cuda_probe import driver_check

        ok, line = driver_check(
            {"gpu_name": "NVIDIA GeForce RTX 4070 Ti", "driver_version": "616.92"}
        )
        self.assertTrue(ok)
        self.assertEqual(line, "NVIDIA GeForce RTX 4070 Ti, driver 616.92")
        old, why = driver_check({"gpu_name": "GTX 1080", "driver_version": "512.15"})
        self.assertFalse(old)
        self.assertIn("update the NVIDIA driver", why)
        self.assertTrue(driver_check({})[0])

    def test_the_doctor_prints_it(self):
        from core.ops_doctor import gpu_rows

        data = {"nvidia_smi": True, "cuda_available": True, "nvenc_capable": True,
                "gpu_name": "NVIDIA GeForce RTX 4070 Ti", "driver_version": "616.92"}  # fmt: skip
        rows = {name: (ok, detail) for name, ok, detail in gpu_rows(data)}
        self.assertEqual(rows["gpu"], (True, "NVIDIA GeForce RTX 4070 Ti, driver 616.92"))
        self.assertEqual(rows["nvenc"], (True, "h264_nvenc yes"))
        self.assertIn("cuda", rows)


class ShortfallIndexTests(unittest.TestCase):
    """#1510: `roadmap-index` counts open items per shortfall."""

    LINES: ClassVar[list[str]] = [
        "- [ ] 1500. **Each hook feature** *(S21.2, filed 2026-10-18)* `[S]`",
        "- [x] 1499. **Done one** *(S21.1, filed 2026-10-18)* `[M]`",
        "- [ ] 1470. **The GPU driver** *(S17.10, filed 2026-10-18)* `[S]`",
        "- [ ] 1505. **Hook length** *(S21.7, filed 2026-10-18)* `[S]`",
        "- [ ] 999. **Untagged** `[S]`",
    ]

    def test_the_counts(self):
        from core.roadmap_index import shortfall_counts

        self.assertEqual(shortfall_counts(self.LINES), {"S17": 1, "S21": 2})

    def test_the_names(self):
        from core.roadmap_index import shortfall_names

        names = shortfall_names(["### S21 The hook score is backwards (Oct 18)", "## Other"])
        self.assertEqual(names, {"S21": "The hook score is backwards (Oct 18)"})

    def test_the_live_index(self):
        from core.roadmap_index import counts, render

        data = counts()
        self.assertGreater(sum(data["by_shortfall"].values()), 0)
        self.assertIn("by shortfall", render(data))
        table = render(data, by_shortfall=True)
        self.assertIn("S21 The hook score is backwards", table)


if __name__ == "__main__":
    unittest.main()
