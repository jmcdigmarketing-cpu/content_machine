"""Wave 113 (2026-10-18): the six most pressing of the 22 shortfalls.

Measured first: Buffer measured five TikTok posts and every one read "not measured yet" - TikTok
calls the metric "Video Views" - and those viewers watched 1.24-1.68 s, inside the 2.15 s intro;
`ops status` told the operator to mark Buffer's sends by hand; metrics synced only when
`ops morning` ran; the YouTube quota ledger kept a daily total and nothing said what spent
9,485 units; a waiting draft was titled "Hot Dads & Horny Art"; week_compile cut 2.15 s from
every Short, including one rendered without the intro.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

NOW = datetime(2026, 10, 18, 23, 0, tzinfo=timezone.utc)

TIKTOK_NODE = {
    "id": "p1",
    "metricsUpdatedAt": "2026-10-18T20:00:00Z",
    "metrics": [
        {"name": "Reactions", "value": 3},
        {"name": "Comments", "value": 0},
        {"name": "Video Views", "value": 79},
        {"name": "Shares", "value": 1},
        {"name": "Reach", "value": 70},
        {"name": "Watch Time (min)", "value": 1.67},
        {"name": "Avg. Watch Time (sec)", "value": 1.24},
    ],
}
INSTAGRAM_NODE = {
    "id": "p2",
    "metricsUpdatedAt": "2026-10-18T20:00:00Z",
    "metrics": [
        {"name": "Reactions", "value": 2},
        {"name": "Views", "value": 129},
        {"name": "Reach", "value": 117},
        {"name": "Follows", "value": 1},
        {"name": "Saves", "value": 0},
    ],
}


class BufferMetricTests(unittest.TestCase):
    """B1 (#1418, #1329): what Buffer measured is read under every name it uses."""

    def test_tiktok_video_views_are_views(self):
        from publishing.buffer_api import parse_metrics_node

        row = parse_metrics_node(TIKTOK_NODE)
        self.assertEqual(row["views"], 79)
        self.assertEqual(row["likes"], 3)
        self.assertEqual(row["avg_watch_s"], 1.24)
        self.assertEqual(row["reach"], 70)

    def test_instagram_follows_and_likes(self):
        from publishing.buffer_api import parse_metrics_node

        row = parse_metrics_node(INSTAGRAM_NODE)
        self.assertEqual((row["views"], row["likes"], row["follows"]), (129, 2, 1))

    def test_a_stored_row_is_read_again_from_its_raw_metrics(self):
        from publishing import platform_metrics

        stored = {"rows": {"157": {"tiktok": {
            "measured": True, "views": None, "likes": None,
            "buffer": {"Video Views": 79, "Reactions": 0, "Avg. Watch Time (sec)": 1.24},
        }}}}  # fmt: skip
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "platform_metrics_{channel}.json")
            with open(path.format(channel="tapin"), "w", encoding="utf-8") as handle:
                json.dump(stored, handle)
            with patch.object(platform_metrics, "METRICS_TEMPLATE", path):
                row = platform_metrics.get_row("tapin", "157", "tiktok")
        self.assertEqual((row["views"], row["avg_watch_s"]), (79, 1.24))

    def test_the_feed_line_says_how_long_tiktok_viewers_watch(self):
        from publishing import platform_recommend

        rows = {"157": {"tiktok": {"measured": True, "views": 79, "avg_watch_s": 1.24}},
                "155": {"tiktok": {"measured": True, "views": 76, "avg_watch_s": 1.4}}}  # fmt: skip
        with (
            patch("publishing.platform_metrics.load", return_value={"rows": rows}),
            patch("publishing.crosspost._load", return_value={"posts": {}}),
            patch.object(platform_recommend, "learning_line", return_value=""),
            patch.object(platform_recommend, "_intro_seconds", return_value=2.15),
        ):
            lines = platform_recommend.feed_lines("tapin")
        line = next(ln for ln in lines if ln.startswith("TikTok"))
        self.assertIn("155 views", line)
        self.assertIn("1.3 s", line)
        self.assertIn("intro", line)


class BufferWeekLineTests(unittest.TestCase):
    """B1 (#1398): the status line counts Buffer's sends and asks for nothing by hand."""

    def test_the_line_counts_sends_and_asks_nothing(self):
        from publishing.crosspost import week_line

        store = {
            "runs": {"150": {"packed": (NOW - timedelta(days=1)).isoformat(), "posted": ""}},
            "posts": {
                "157": {"tiktok": {"state": "sent", "post_id": "a", "at": (NOW - timedelta(days=2)).isoformat(),
                                   "sent_at": (NOW - timedelta(days=2)).isoformat()},
                        "instagram": {"state": "sent", "post_id": "b", "at": (NOW - timedelta(days=2)).isoformat(),
                                      "sent_at": (NOW - timedelta(days=2)).isoformat()}},
                "164": {"tiktok": {"state": "scheduled", "post_id": "c", "at": (NOW - timedelta(hours=3)).isoformat()}},
            },
        }  # fmt: skip
        with patch("publishing.crosspost._load", return_value=store):
            line = week_line("tapin", now=NOW)
        self.assertNotIn("crosspost done", line)
        self.assertNotIn("packed", line)
        self.assertIn("1 posted", line)
        self.assertIn("1 scheduled", line)


class UnattendedSyncTests(unittest.TestCase):
    """B2 (#1489, #1490): the metrics sync runs once a day without the operator."""

    def _stamp(self, tmp, when):
        path = os.path.join(tmp, "metrics_synced.json")
        if when is not None:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"tapin": when.isoformat()}, handle)
        return path

    def test_a_stale_or_missing_stamp_syncs(self):
        from analytics import sync_metrics

        for age in (None, timedelta(hours=21)):
            with tempfile.TemporaryDirectory() as tmp:
                path = self._stamp(tmp, None if age is None else NOW - age)
                with (
                    patch.object(sync_metrics, "SYNC_STAMP_FILE", path),
                    patch.object(sync_metrics, "sync_channel", return_value=0) as sync,
                ):
                    ran = sync_metrics.maybe_sync("tapin", now=NOW)
            self.assertTrue(ran, age)
            sync.assert_called_once()

    def test_a_fresh_stamp_does_not(self):
        from analytics import sync_metrics

        with tempfile.TemporaryDirectory() as tmp:
            path = self._stamp(tmp, NOW - timedelta(hours=3))
            with (
                patch.object(sync_metrics, "SYNC_STAMP_FILE", path),
                patch.object(sync_metrics, "sync_channel", return_value=0) as sync,
            ):
                ran = sync_metrics.maybe_sync("tapin", now=NOW)
        self.assertFalse(ran)
        sync.assert_not_called()

    def test_a_finished_sync_stamps_itself(self):
        from analytics import sync_metrics

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "metrics_synced.json")
            with patch.object(sync_metrics, "SYNC_STAMP_FILE", path):
                sync_metrics.mark_synced("tapin", now=NOW)
                self.assertEqual(sync_metrics.last_synced("tapin"), NOW)

    def test_health_says_when_it_synced_and_that_youtube_lags(self):
        from analytics import sync_metrics

        with tempfile.TemporaryDirectory() as tmp:
            path = self._stamp(tmp, NOW - timedelta(hours=13))
            with patch.object(sync_metrics, "SYNC_STAMP_FILE", path):
                note = sync_metrics.sync_note("tapin", now=NOW)
        self.assertIn("13 h ago", note)
        self.assertIn("2-3 days", note)

    def test_a_failed_sync_is_not_retried_every_pass(self):
        from analytics import sync_metrics

        with tempfile.TemporaryDirectory() as tmp:
            path = self._stamp(tmp, None)
            with (
                patch.object(sync_metrics, "SYNC_STAMP_FILE", path),
                patch.object(sync_metrics, "sync_channel", return_value=1) as sync,
            ):
                first = sync_metrics.maybe_sync("tapin", now=NOW)
                again = sync_metrics.maybe_sync("tapin", now=NOW + timedelta(minutes=15))
                later = sync_metrics.maybe_sync("tapin", now=NOW + timedelta(hours=3))
        self.assertEqual((first, again, later), (True, False, True))
        self.assertEqual(sync.call_count, 2)

    def test_overnight_and_the_worker_call_it(self):
        import inspect

        from core import overnight
        from jobs import worker

        self.assertIn("maybe_sync", inspect.getsource(overnight.run_overnight))
        self.assertIn("_sync_metrics()", inspect.getsource(worker.main))
        # Wave 114 (#1518): a channel needs a sign-in file; CI has none, so give it one.
        with (
            tempfile.NamedTemporaryFile(suffix=".json", delete=False) as token,
            patch("youtube.oauth.token_path_for_channel", return_value=token.name),
            patch("analytics.sync_metrics.maybe_sync") as sync,
        ):
            worker._sync_metrics()
        os.unlink(token.name)
        sync.assert_called_with("tapin")


class AdSafeTests(unittest.TestCase):
    """B5 (#1319, the operator: an overnight draft waits, py main.py warns)."""

    def test_draft_166s_title_is_flagged_and_sports_violence_is_not(self):
        from core.authenticity import ad_unfriendly_words

        self.assertEqual(
            ad_unfriendly_words("Hot Dads & Horny Art: Why Belmont's Curse Works"), ["horny"]
        )
        for clean in ("Pereira's brutal KO ends it in round one", "Sussex fans react",
                      "The method behind the Chiefs' defense", "Kill streaks in Warzone"):  # fmt: skip
            self.assertEqual(ad_unfriendly_words(clean), [], clean)

    def test_the_first_sentence_counts_the_rest_does_not(self):
        from core.authenticity import ad_limit_reason

        self.assertIn(
            "would limit ads", ad_limit_reason("Fine title", "This is sexy football. More.")
        )
        self.assertEqual(ad_limit_reason("Fine title", "Clean opener. Then a shit line later."), "")

    def test_an_overnight_draft_with_one_waits(self):
        from core import batch_review

        draft = batch_review.PendingDraft(
            folder="x", meta={"run_id": 166, "title": "Hot Dads & Horny Art: Why Belmont's Curse Works"},
            script="Belmont's curse is the best art this year. Here's why.",
        )  # fmt: skip
        with (
            patch.object(batch_review, "dead_reason", return_value=""),
            patch.object(batch_review, "_blocking_claims", return_value=[]),
            patch.object(batch_review, "authenticity_now", return_value=("ok", "")),
            patch.object(batch_review, "game_block_reason", return_value=""),
            patch.object(batch_review, "arc_counter_reason", return_value=""),
        ):
            why = batch_review.unattended_block_reason(draft)
        self.assertEqual(why, 'its title or first line would limit ads ("horny")')

    def test_the_backlog_gate_says_it_too(self):
        from publishing import backlog

        draft = type("D", (), {"meta": {"run_id": 166}, "run_id": 166, "script": "Fine.",
                               "title": "Hot Dads & Horny Art"})()  # fmt: skip
        with (
            patch("core.video_grade.grade_run", return_value=type("G", (), {"letter": "A"})()),
            patch("core.batch_review.draft_age_days", return_value=0),
            patch("core.batch_review.freshness_window_days", return_value=7),
        ):
            reasons = backlog.backlog_gate(draft)
        self.assertIn('its title or first line would limit ads ("horny")', reasons)


class QuotaByCallerTests(unittest.TestCase):
    """B6 (#1427, the operator: a breakdown and an upload reserve)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        path = os.path.join(self.tmp.name, "youtube_quota.json")
        from apis import youtube_quota

        self.patches = [
            patch.object(youtube_quota, "_quota_path", return_value=path),
            patch.object(youtube_quota, "quota_day", return_value="2026-10-18"),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_each_caller_is_booked_under_its_name(self):
        from apis import youtube_quota

        youtube_quota.record_usage(units=101)
        youtube_quota.record_upload_usage()
        youtube_quota.record_call("captions.insert")
        youtube_quota.record_call("videos.update")
        self.assertEqual(youtube_quota.usage_by_caller(),
                         {"search": 101, "upload": 1600, "captions.insert": 400, "videos.update": 50})  # fmt: skip
        split = youtube_quota.format_usage_split()
        self.assertTrue(split.startswith("upload 1,600, captions.insert 400"), split)

    def test_a_day_before_the_breakdown_says_so(self):
        from apis import youtube_quota

        youtube_quota._save({"2026-10-18": {"used": 6032, "updated": 0}})
        self.assertIn("not broken down", youtube_quota.format_usage_split())

    def test_searches_leave_one_upload(self):
        from apis import youtube_quota

        youtube_quota._save({"2026-10-18": {"used": 10000 - 1650, "updated": 0}})
        with patch.dict(os.environ, {"YOUTUBE_UPLOAD_RESERVE": ""}):
            self.assertFalse(youtube_quota.has_quota_for_search())
            self.assertTrue(youtube_quota.has_quota_for_upload())
        youtube_quota._save({"2026-10-18": {"used": 10000 - 1750, "updated": 0}})
        self.assertTrue(youtube_quota.has_quota_for_search())
        youtube_quota._save({"2026-10-18": {"used": 10000 - 150, "updated": 0}})
        with patch.dict(os.environ, {"YOUTUBE_UPLOAD_RESERVE": "0"}):
            self.assertTrue(youtube_quota.has_quota_for_search())

    def test_a_ledger_write_never_breaks_the_call(self):
        from apis import youtube_quota

        with patch.object(youtube_quota, "record_usage", side_effect=OSError("disk")):
            youtube_quota.record_call("videos.update")  # no raise

    def test_every_data_api_call_site_books_itself(self):
        # Wave 113: captions.insert (400), videos.update (50) and the list calls booked nothing.
        import inspect

        from core import playlists
        from publishing import (
            backlog,
            description_fix,
            go_public,
            recategorize,
            rollback,
            snippet_update,
        )
        from youtube import captions, channel_uploads, pin_comment, studio_deleted

        for module in (playlists, backlog, description_fix, go_public, recategorize, rollback,
                       snippet_update, captions, channel_uploads, pin_comment, studio_deleted):  # fmt: skip
            source = inspect.getsource(module)
            calls = source.count(".execute()")
            self.assertGreaterEqual(source.count("record_call("), 1, module.__name__)
            self.assertLessEqual(source.count("record_call("), calls, module.__name__)


class FollowLineTests(unittest.TestCase):
    """B4 (#1322, the operator: previews with a call): 2 of 64 subscribers came from videos."""

    def test_a_preview_with_a_call_ends_on_why_to_follow(self):
        from core.facts.event_dates import preview_brief

        brief = preview_brief("2026-10-19T00:20Z", call="Packers win - Dallas allows deep balls")
        self.assertIn("follow to see if I was right", brief)
        self.assertIn("graded after the game", brief)

    def test_a_preview_without_a_call_does_not(self):
        from core.facts.event_dates import preview_brief

        self.assertNotIn("follow", preview_brief("2026-10-19T00:20Z").lower())

    def test_the_line_is_not_taken_for_a_generic_cta(self):
        from core.script_craft import strip_pre_cta_summary

        script = ("Packers win this one.\n\nIn summary, Dallas cannot cover the deep ball.\n\n"
                  "I grade this call after the game - follow to see if I was right.")  # fmt: skip
        self.assertEqual(strip_pre_cta_summary(script)[0], script)


class HookCopyTests(unittest.TestCase):
    """B3 (#1417, #1419): TikTok's viewers left inside the 2.15 s intro; the copy starts at the hook."""

    def test_the_offset_is_the_runs_own_intro(self):
        from video.hook_copy import hook_offset

        with patch("video.intro_offset.intro_offset_seconds", return_value=2.15):
            self.assertEqual(hook_offset({"intro": True, "intro_seconds": 2.15}, "tapin"), 2.15)
            self.assertEqual(hook_offset({"intro": False, "intro_seconds": 0.0}, "tapin"), 0.0)
            self.assertEqual(hook_offset({}, "tapin"), 2.15)  # before #988 recorded it: all had one

    def test_the_cut_seeks_before_the_input(self):
        from video.hook_copy import hook_copy_argv

        argv = hook_copy_argv("in.mp4", "in.hook.mp4", offset=2.15)
        self.assertLess(argv.index("-ss"), argv.index("-i"))
        self.assertEqual(argv[argv.index("-ss") + 1], "2.15")
        self.assertEqual(argv[-1], "in.hook.mp4")

    def test_a_copy_is_made_once_and_any_failure_sends_the_original(self):
        from video import hook_copy

        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "v.mp4")
            with open(src, "wb") as handle:
                handle.write(b"x" * 10)

            def made(argv, **_kw):
                with open(argv[-1], "wb") as out:
                    out.write(b"y" * 10)
                return type("Done", (), {"returncode": 0})()

            feats = {"intro": True, "intro_seconds": 2.15}
            self.assertEqual(
                hook_copy.ensure_hook_copy(src, {"intro": False}, "tapin", run=made), src
            )
            got = hook_copy.ensure_hook_copy(src, feats, "tapin", run=made)
            self.assertEqual(got, os.path.join(tmp, "v.hook.mp4"))
            failing = type("Done", (), {"returncode": 1})()
            os.remove(got)
            self.assertEqual(
                hook_copy.ensure_hook_copy(src, feats, "tapin", run=lambda *a, **k: failing), src
            )

    def test_the_opening_is_read_from_the_runs_quality(self):
        # Live 2026-10-18: the first version read the run's features, where nothing records the
        # intro - run 164 fell back to the channel's 2.15 s. The render keeps it in the quality.
        from video.hook_copy import run_opening

        run = type(
            "R",
            (),
            {"quality_json": json.dumps({"opening": {"intro": False, "intro_seconds": 0.0}})},
        )()
        self.assertEqual(run_opening(run), {"intro": False, "intro_seconds": 0.0})
        self.assertEqual(run_opening(type("R", (), {"quality_json": ""})()), {})

    def test_buffer_is_sent_the_hook_copy(self):
        import inspect

        from publishing import crosspost

        run = type(
            "R",
            (),
            {"quality_json": json.dumps({"opening": {"intro": True, "intro_seconds": 2.15}})},
        )()
        with (
            patch.object(crosspost, "_content_run", return_value=run),
            patch("video.hook_copy.ensure_hook_copy", return_value="v.hook.mp4") as copy,
        ):
            self.assertEqual(crosspost._sent_file(157, "v.mp4", "tapin"), "v.hook.mp4")
        self.assertEqual(copy.call_args.args[1], {"intro": True, "intro_seconds": 2.15})
        self.assertIn("_sent_file(", inspect.getsource(crosspost.send_due))

    def test_the_compilation_keeps_a_no_intro_shorts_hook(self):
        from video import week_compile

        when = datetime(2026, 10, 15, tzinfo=timezone.utc)
        shorts = [{"run_id": i, "title": f"t{i}", "path": f"p{i}.mp4", "published_at": when + timedelta(hours=i),
                   "offset": 0.0 if i == 1 else 2.15} for i in range(1, 6)]  # fmt: skip
        with (
            patch.object(week_compile, "week_shorts", return_value=shorts),
            patch.object(week_compile, "_duration", return_value=40.0),
        ):
            plan = week_compile.plan_week("tapin", now=NOW)
        seconds = {item["run_id"]: item["seconds"] for item in plan.items}
        self.assertEqual(seconds[1], 40.0)
        self.assertAlmostEqual(seconds[2], 37.85)


if __name__ == "__main__":
    unittest.main()
