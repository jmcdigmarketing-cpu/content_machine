"""Wave 110 (2026-10-18): the operator's day with it.

- "are drafts not posting or rendering?" - they rendered and uploaded, but batch-review planned
  them with the old `plan_spaced_uploads`: run 165 (the Chargers preview, kickoff 20:25Z) was
  scheduled public for Wednesday 10 PM, run 164 (the Perez knockout, two-day news) for Friday.
- go-public and schedule-public could not see a scheduled video: `list_uploaded_for_channel`
  leaves out rows whose `published_at` is still ahead, so YouTube changed and the log did not.
- "the menu will just not have a visual input anymore": `menu_line` wrote the prompt with
  `print(prompt, end="")` and never flushed it before blocking on a key.
- "ideas are small small boring stories/news": the headline pool was shuffled, not ranked.
- "predictions are still lazy": a preview was the matchup and the records, with no call.
- "ops all is slow": it ran the whole suite (259 s), and six tests read the real `data/`.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")

NOW = datetime(2026, 10, 18, 15, 30, tzinfo=timezone.utc)
WED_10PM = datetime(2026, 10, 22, 2, 0, tzinfo=timezone.utc)


def _scheduled(rid=40, run_id=165, video_id="52tS6g1fu_k", when=WED_10PM):
    return SimpleNamespace(
        id=rid,
        content_run_id=run_id,
        youtube_video_id=video_id,
        privacy_status="private",
        status="scheduled",
        published_at=when,
    )


class ScheduledRowTests(unittest.TestCase):
    """#1299: go-public on a video YouTube holds for a later publishAt."""

    def _repo(self, row):
        repo = MagicMock()
        repo.list_uploaded_for_channel.return_value = []
        repo.list_future_scheduled.return_value = [row]
        return repo

    def _send(self, call):
        from publishing import go_public

        with (
            patch.dict(os.environ, {"YOUTUBE_UPLOAD_ENABLED": "true"}),
            patch.object(go_public, "override_held", return_value=False),
            patch.object(go_public, "_run_title", return_value="Chargers at Chiefs"),
            patch.object(go_public, "_now", return_value=NOW, create=True),
            patch("publishing.snippet_update.manage_scope_problem", return_value=""),
            patch("youtube.oauth.get_youtube_service", return_value=MagicMock()),
            patch("publishing.crosspost.step", return_value=["sent"]),
        ):
            return call(go_public)

    def test_go_public_finds_the_scheduled_row_and_moves_it_to_now(self):
        repo = self._repo(_scheduled())
        result = self._send(lambda gp: gp.apply_go_public("52tS6g1fu_k", dry_run=False, repo=repo))
        self.assertEqual(result.status, "updated")
        self.assertEqual(result.run_id, 165)
        log_id, fields = repo.update.call_args.args
        self.assertEqual(log_id, 40)
        self.assertEqual(fields["privacy_status"], "public")
        # Left at Wednesday, the crosspost round would wait for Wednesday.
        self.assertEqual(fields["published_at"], NOW)

    def test_a_reschedule_updates_the_scheduled_row(self):
        repo = self._repo(_scheduled(rid=39, run_id=164, video_id="3nlkdFTjxe0"))
        six_pm = datetime(2026, 10, 18, 22, 0, tzinfo=timezone.utc)
        result = self._send(
            lambda gp: gp.apply_schedule_public("3nlkdFTjxe0", when=six_pm, repo=repo)
        )
        self.assertEqual(result.status, "scheduled")
        self.assertEqual(result.run_id, 164)
        log_id, fields = repo.update.call_args.args
        self.assertEqual(log_id, 39)
        self.assertEqual(fields["published_at"], six_pm)

    def test_a_reschedule_logs_the_privacy_it_goes_public_with(self):
        # The uploader logs a scheduled video as "public" (rows 1641-1646); a "private" row
        # is never in crosspost._public_runs, so it never reaches TikTok or Instagram.
        repo = self._repo(_scheduled(rid=39, run_id=164, video_id="3nlkdFTjxe0"))
        six_pm = datetime(2026, 10, 18, 22, 0, tzinfo=timezone.utc)
        self._send(lambda gp: gp.apply_schedule_public("3nlkdFTjxe0", when=six_pm, repo=repo))
        self.assertEqual(repo.update.call_args.args[1]["privacy_status"], "public")

    def test_the_waiting_line_reads_the_scheduled_rows(self):
        # Live 2026-10-18 with six videos scheduled it printed "": it read the live rows, which
        # leave a future published_at out, and looked for "private" where the log says "public".
        from publishing import crosspost

        rows = [
            _scheduled(rid=1, run_id=153, when=datetime(2026, 10, 18, 16, 0, tzinfo=timezone.utc)),
            _scheduled(rid=2, run_id=154, when=datetime(2026, 10, 19, 2, 0, tzinfo=timezone.utc)),
        ]
        for row in rows:
            row.privacy_status = "public"
        repo = MagicMock()
        repo.list_uploaded_for_channel.return_value = []
        repo.list_future_scheduled.return_value = rows
        with patch(
            "storage.repositories.publish_log.get_publish_log_repository", return_value=repo
        ):
            line = crosspost.waiting_line("tapin", now=NOW)
        self.assertIn("2 scheduled", line)

    def _live_pass(self, rows, posts):
        from jobs import worker

        repo = MagicMock()
        repo.list_uploaded_for_channel.return_value = rows
        with (
            patch.object(worker, "_crosspost_channels", return_value=["tapin"]),
            patch("storage.repositories.publish_log.get_publish_log_repository", return_value=repo),
            patch("publishing.crosspost._load", return_value={"posts": posts}),
            patch("analytics.privacy_sync.sync_privacy", return_value={"changed": []}) as sync,
            patch("publishing.crosspost.step", return_value=[]) as step,
        ):
            worker._crosspost_scheduled_live(now=NOW)
        return sync, step

    def test_a_passed_slot_logged_public_is_sent_without_a_read_back(self):
        # Run 153's noon slot, as the uploader logs it: privacy "public", status "scheduled".
        # The pass waited for "private", so Buffer waited for the morning sync.
        row = _scheduled(rid=1641, run_id=153, video_id="3lOeUCrcsHI",
                         when=datetime(2026, 10, 18, 15, 0, tzinfo=timezone.utc))  # fmt: skip
        row.privacy_status = "public"
        sync, step = self._live_pass([row], posts={})
        step.assert_called_once_with("tapin")
        sync.assert_not_called()

    def test_a_slot_already_sent_is_left_alone(self):
        row = _scheduled(rid=1641, run_id=159, video_id="yt159",
                         when=datetime(2026, 10, 18, 2, 0, tzinfo=timezone.utc))  # fmt: skip
        row.privacy_status = "public"
        _sync, step = self._live_pass(
            [row], posts={"159": {"tiktok": {"state": "sent"}, "instagram": {"state": "sent"}}}
        )
        step.assert_not_called()

    def test_find_still_prefers_the_newest_row(self):
        from publishing.go_public import _find

        old = _scheduled(rid=1)
        new = _scheduled(rid=5)
        self.assertIs(_find([old, new], "52tS6g1fu_k"), new)


MORNING = datetime(2026, 10, 18, 15, 0, tzinfo=timezone.utc)  # 10 AM CDT, batch-review
KICKOFF = datetime(2026, 10, 18, 20, 25, tzinfo=timezone.utc)  # Chargers at Chiefs
# The slots other uploads held that morning: runs 153, 154, 156, 158 and 161.
TAKEN = {
    datetime(2026, 10, 18, 16, 0, tzinfo=timezone.utc),
    datetime(2026, 10, 19, 2, 0, tzinfo=timezone.utc),
    datetime(2026, 10, 19, 16, 0, tzinfo=timezone.utc),
    datetime(2026, 10, 20, 2, 0, tzinfo=timezone.utc),
    datetime(2026, 10, 20, 16, 0, tzinfo=timezone.utc),
}
WINDOWS = {165: 7.0, 164: 2.0, 162: 7.0}


class OneSlotRuleTests(unittest.TestCase):
    """#1298 / #1295: batch-review planned with `planned_post_time` - run 165 (the Chargers
    preview) went out Wednesday 10 PM, three days after its game, and run 164 (two-day news)
    on Friday."""

    def _patches(self):
        from contextlib import ExitStack

        from core import spaced_queue

        stack = ExitStack()
        stack.enter_context(patch.object(spaced_queue, "_window_days",
                                         side_effect=lambda r, _c: WINDOWS.get(int(r), 7.0)))  # fmt: skip
        stack.enter_context(patch.object(spaced_queue, "_age_days", return_value=0.1))
        stack.enter_context(patch.object(spaced_queue, "_taken_slots", return_value=set(TAKEN)))
        stack.enter_context(
            patch.object(
                spaced_queue,
                "preview_event",
                side_effect=lambda _c, run_id, _t, rendered: KICKOFF if run_id == 165 else None,
            )
        )
        stack.enter_context(patch.object(spaced_queue, "_channel_tz",
                                         return_value=NY))  # fmt: skip
        return stack

    def test_a_game_with_no_slot_before_kickoff_goes_out_as_it_uploads(self):
        from core.spaced_queue import slot_for_run

        with self._patches():
            when, why = slot_for_run("tapin", 165, title="Chargers at Chiefs", now=MORNING)
        self.assertIsNotNone(when, why)
        self.assertLess(when, KICKOFF)
        self.assertGreaterEqual(when, MORNING)

    def test_the_morning_three_get_the_shelf_rules(self):
        from core import spaced_queue

        rows = [
            {"run_id": n, "title": f"run {n}", "state": "rendered, never uploaded"}
            for n in (162, 164, 165)
        ]
        with (
            self._patches(),
            patch("core.stale_renders.shelf_rows", return_value=rows),
        ):
            slots = spaced_queue.shelf_schedule("tapin", run_ids=[165, 164, 162], now=MORNING)
        got = {s.run_id: s.publish_at for s in slots}
        self.assertLess(got[165], KICKOFF)  # the game, before kickoff
        self.assertEqual(got[164], datetime(2026, 10, 18, 22, 0, tzinfo=timezone.utc))  # 6 PM
        self.assertEqual(got[162], datetime(2026, 10, 21, 2, 0, tzinfo=timezone.utc))  # free 10 PM

    def test_batch_review_plans_with_the_shelf(self):
        from core import batch_review, spaced_queue

        planned = [spaced_queue.SpacedSlot(run_id=165, title="a", publish_at=MORNING)]
        with patch.object(spaced_queue, "shelf_schedule", return_value=planned) as shelf:
            slots = batch_review.plan_review_slots("tapin", [(165, "a"), (170, "b")])
        shelf.assert_called_once()
        self.assertEqual(shelf.call_args.kwargs["run_ids"], [165, 170])
        by_run = {s.run_id: s for s in slots}
        self.assertEqual(by_run[165].publish_at, MORNING)
        self.assertIsNone(by_run[170].publish_at)  # not on the shelf: left on disk, said why
        self.assertTrue(by_run[170].skipped)

    def test_the_menu_slot_is_the_run_slot(self):
        from core.ui import prompt_upload_plan

        answers = iter(["4", "3"])
        with (
            patch("core.ui.display_upload_queue"),
            patch("core.spaced_queue.slot_for_run", return_value=(MORNING, "")) as slot,
            patch("analytics.post_timing.format_scheduled_local", return_value="Sun 11:00 AM"),
        ):
            plan = prompt_upload_plan(
                channel_id="tapin",
                topic="Chargers at Chiefs",
                run_id=165,
                print_fn=lambda *a, **k: None,
                input_fn=lambda *_: next(answers),
            )
        slot.assert_called()
        self.assertEqual(plan.youtube_publish_at, MORNING)

    def test_the_cut_shorts_take_free_noon_and_ten_pm_slots(self):
        from core import spaced_queue

        uncapped = SimpleNamespace(cap=0, total=13, window_days=7, capped=False)
        with (
            self._patches(),
            patch.object(spaced_queue, "cadence_status", return_value=uncapped),
            patch.object(spaced_queue, "_now", return_value=MORNING, create=True),
            patch.object(spaced_queue, "_post_time_running", return_value=False),
        ):
            plan = spaced_queue.plan_spaced_uploads(
                [(170, "a"), (171, "b")], channel_id="tapin", one_per_day=True
            )
        times = [s.publish_at for s in plan]
        self.assertTrue(all(t not in TAKEN for t in times), times)
        local = [t.astimezone(NY) for t in times]
        self.assertTrue(all(t.hour in (12, 22) for t in local), local)
        self.assertNotEqual(local[0].date(), local[1].date())


def _headline(topic, source, hours_ago=2):
    published = MORNING - timedelta(hours=hours_ago)
    return {"topic": topic, "domain": "ufc", "source": source, "published": published}


class BigStoriesTests(unittest.TestCase):
    """#1300: "ideas are small small boring stories/news" - four feeds, shuffled by date."""

    POOL = (
        _headline("Polygon picks the five best cozy games this fall", "Polygon", 1),
        _headline("Cristian Perez knocks out Kyle Nelson in 27 seconds", "MMA Fighting", 3),
        _headline(
            "Kyle Nelson finished by Cristian Perez in 27 seconds at UFC Edmonton", "MMA Weekly", 4
        ),
        _headline("Cristian Perez stuns Kyle Nelson with a 27-second knockout", "BBC Sport", 5),
        _headline("Dexerto ranks every Fortnite season", "Dexerto", 2),
    )

    def test_the_story_on_most_outlets_comes_first_once(self):
        from core.best_bet import rank_by_coverage

        ranked = rank_by_coverage([dict(c) for c in self.POOL], now=MORNING)
        self.assertIn("Perez", ranked[0]["topic"])
        self.assertEqual(len(ranked[0]["outlets"]), 3)
        # The other two Perez headlines are the same story, not two more ideas.
        self.assertEqual(sum("Perez" in c["topic"] for c in ranked), 1)

    def test_a_headline_with_one_subject_needs_its_whole_name(self):
        # Live 2026-10-18: "UFC Edmonton Post-Fight Press Conference" led on "6 outlets" - every
        # headline that said "UFC" counted, through the name's single-word markers.
        from core.best_bet import rank_by_coverage

        pool = [
            _headline("UFC Edmonton Post-Fight Press Conference", "MMA Weekly", 1),
            _headline("UFC 330 adds a lightweight bout", "MMA Fighting", 2),
            _headline("Dana White talks UFC Paramount deal", "Bloody Elbow", 3),
        ]
        ranked = rank_by_coverage([dict(c) for c in pool], now=MORNING)
        press = next(c for c in ranked if "Press Conference" in c["topic"])
        self.assertEqual(press["outlets"], ["MMA Weekly"])

    def test_the_rationale_names_the_coverage(self):
        from core.best_bet import coverage_note

        note = coverage_note({"source": "MMA Fighting",
                              "outlets": ["BBC Sport", "MMA Fighting", "MMA Weekly"]})  # fmt: skip
        self.assertTrue(note.startswith("on 3 outlets"), note)
        self.assertIn("MMA Weekly", note)
        self.assertEqual(coverage_note({"source": "Polygon", "outlets": ["Polygon"]}),
                         "trending on Polygon now")  # fmt: skip

    def test_the_pool_reads_every_feed_for_the_channels_domains(self):
        from core.best_bet import idea_feeds

        with patch(
            "config.data_sources.rss_feeds_for_channel",
            return_value=[
                {"name": "MMA Fighting", "url": "https://www.mmafighting.com/rss/index.xml"}
            ],
        ):
            names = {f["name"] for f in idea_feeds("tapin", {"ufc", "gaming"})}
        self.assertIn("MMA Weekly", names)  # a ufc feed beyond the channel's four
        self.assertIn("Kotaku", names)  # a gaming one
        self.assertEqual(sum(1 for n in names if n == "MMA Fighting"), 1)


GAME = "Dallas Cowboys at Green Bay Packers"
BOARD_EVENT = {
    "name": GAME,
    "date": "2026-10-19T00:20Z",
    "competitions": [
        {
            "competitors": [
                {"homeAway": "home", "team": {"shortDisplayName": "Packers"},
                 "records": [{"summary": "4-1"}]},
                {"homeAway": "away", "team": {"shortDisplayName": "Cowboys"},
                 "records": [{"summary": "3-3"}]},
            ],
            "broadcasts": [{"names": ["NBC"]}],
            "odds": [{"details": "GB -3.5", "overUnder": 47.5}],
        }
    ],
}  # fmt: skip
HEADLINES = [
    "Packers' Jordan Love throws for 300 yards in third straight win",
    "Cowboys secondary allows most deep completions in the NFL",
    "Fortnite comes to Linux",
]


class PredictionTests(unittest.TestCase):
    """#1301: "predictions are still lazy" - a preview was the matchup and the records."""

    def test_the_board_line_is_read(self):
        from core.seasonal_calendar import game_detail

        detail = game_detail("nfl", BOARD_EVENT)
        self.assertEqual(detail["line"], "GB -3.5")
        self.assertEqual(detail["total"], "47.5")

    def _bet(self):
        from core.best_bet import BestBetResult

        return BestBetResult(topic=GAME, domain="nfl", avg_engaged_rate=0.0, source="schedule",
                             supporting_runs=0, rationale="Sun 8:20 PM · NBC · Cowboys 3-3 at Packers 4-1")  # fmt: skip

    def test_a_preview_gets_a_call_and_the_why(self):
        from core.predictions import calls

        sent: list[str] = []

        def model(messages, **_kw):
            sent.append(messages if isinstance(messages, str) else str(messages))
            return {"call": "Packers win", "why": "Dallas allows the most deep completions"}

        with (
            patch.dict(os.environ, {"PREVIEW_CALLS": "true"}),
            patch("core.llm_router.complete_json", side_effect=model),
            patch("core.seasonal_calendar.game_details", return_value={"line": "GB -3.5"}),
        ):
            got = calls.preview_calls([self._bet()], headlines=HEADLINES)
        call = got[GAME]
        self.assertEqual(call["call"], "Packers win")
        self.assertEqual(call["line"], "GB -3.5")
        self.assertIn("Cowboys secondary", sent[0])  # a headline naming a side
        self.assertNotIn("Fortnite", sent[0])  # one naming neither is left out
        self.assertIn("GB -3.5", calls.call_line(call))

    def test_a_why_with_a_number_nobody_supplied_is_dropped(self):
        from core.predictions import calls

        with (
            patch.dict(os.environ, {"PREVIEW_CALLS": "true"}),
            patch(
                "core.llm_router.complete_json",
                return_value={"call": "Packers win", "why": "Love has 14 touchdowns"},
            ),  # fmt: skip
            patch("core.seasonal_calendar.game_details", return_value={}),
        ):
            got = calls.preview_calls([self._bet()], headlines=HEADLINES)
        self.assertEqual(got[GAME]["call"], "Packers win")
        self.assertEqual(got[GAME]["why"], "")

    def test_no_model_leaves_the_preview_as_it_was(self):
        from core.predictions import calls

        with (
            patch.dict(os.environ, {"PREVIEW_CALLS": "true"}),
            patch("core.llm_router.complete_json", side_effect=RuntimeError("down")),
            patch("core.seasonal_calendar.game_details", return_value={}),
        ):
            self.assertEqual(calls.preview_calls([self._bet()], headlines=HEADLINES), {})

    def test_the_call_reaches_the_menu_and_the_brief(self):
        from core import best_bet
        from core.facts.event_dates import preview_brief

        made = {GAME: {"call": "Packers win", "why": "Dallas allows deep balls", "line": "GB -3.5"}}
        bets = best_bet.with_calls([self._bet()], made)
        self.assertIn("Call: Packers win", bets[0].rationale)
        self.assertEqual(bets[0].call, "Packers win - Dallas allows deep balls")
        record = best_bet.pick_record(bets, 1)
        self.assertEqual(record["offered"][0]["call"], "Packers win - Dallas allows deep balls")
        brief = preview_brief("2026-10-19T00:20Z", call="Packers win - Dallas allows deep balls")
        self.assertIn("Make this call and argue it", brief)
        self.assertIn("Packers win", brief)

    def test_a_picked_preview_is_written_as_a_preview(self):
        # main.py gave a picked preview no preview brief at all; overnight did.
        from core.batch_generation import draft_brief

        offered = {"offered": [{"topic": GAME, "source": "schedule", "call": "Packers win - x"}],
                   "picked": 1}  # fmt: skip
        with patch("core.seasonal_calendar.event_start", return_value="2099-10-19T00:20Z"):
            brief = draft_brief(GAME, offered)
        self.assertIn("has not been played", brief)
        self.assertIn("Packers win", brief)


class CrosspostVerbTests(unittest.TestCase):
    """#1298: "no damn way am i posting these manually" - bare `ops crosspost` packed five
    folders for hand posting while the Buffer round was set up and working."""

    def _run(self, target="", *, set_up=True):
        from argparse import Namespace

        from publishing import buffer_api, crosspost
        from scripts import ops

        args = Namespace(target=target, channel="tapin", apply=False, run_id=0)
        with (
            patch.object(crosspost, "auto_enabled", return_value=set_up),
            patch.object(buffer_api, "configured", return_value=set_up),
            patch.object(
                crosspost,
                "buffer_channel_ids",
                return_value={"tiktok": "t", "instagram": "i"} if set_up else {},
            ),  # fmt: skip
            patch.object(crosspost, "step", return_value=["  run 164 TikTok: scheduled"]) as step,
            patch.object(crosspost, "pack_new", return_value=[]) as pack,
            patch.object(crosspost, "status_lines", return_value=[]),
            patch.object(crosspost, "waiting_line", return_value=""),
            patch.object(crosspost, "waiting_lines", return_value=[]),
            patch("builtins.print"),
        ):
            code = ops.cmd_crosspost(args)
        return code, step, pack

    def test_with_buffer_set_up_the_bare_verb_runs_the_round(self):
        code, step, pack = self._run()
        self.assertEqual(code, 0)
        step.assert_called_once_with("tapin")
        pack.assert_not_called()

    def test_pack_is_its_own_verb(self):
        _code, step, pack = self._run("pack")
        pack.assert_called_once()
        step.assert_not_called()

    def test_without_buffer_the_bare_verb_still_packs(self):
        _code, _step, pack = self._run(set_up=False)
        pack.assert_called_once()

    def test_a_pack_takes_only_videos_public_on_youtube(self):
        # 2026-10-18 it packed runs 162 (unlisted), 156 and 155 (scheduled) beside 165.
        from publishing import crosspost

        runs = [SimpleNamespace(id=n, mp4_path=f"v{n}.mp4", title=f"run {n}") for n in (165, 162)]
        with (
            patch.object(crosspost, "_load", return_value={}),
            patch.object(crosspost, "_save"),
            patch.object(crosspost, "_rendered_runs", return_value=runs),
            patch.object(crosspost, "_public_runs", return_value=[(165, "52tS6g1fu_k")]),
            patch("os.path.isfile", return_value=True),
            patch.object(
                crosspost,
                "pack_run",
                side_effect=lambda _c, run: SimpleNamespace(
                    run_id=run.id, folder="f", reel_ok=True
                ),
            ),  # fmt: skip
        ):
            packed = crosspost.pack_new("tapin")
        self.assertEqual([p.run_id for p in packed], [165])


class OpsAllTests(unittest.TestCase):
    """#1302: "ops all is slow" - it ran the whole suite (259 s) on every morning batch."""

    def test_ops_all_leaves_the_suite_to_ci(self):
        from scripts import ops

        self.assertNotIn("test", ops.batch_leaves("all"))
        self.assertIn("test", ops.batch_leaves("all-checks"))
        for step in ("validate", "feeds", "sync-metrics", "batch-review"):
            self.assertIn(step, ops.batch_leaves("all"))


class SuiteEnvTests(unittest.TestCase):
    """#1302: six tests failed in `ops all` on the operator's PC and nowhere else - `ops` had
    loaded `.env`, and the suite it started inherited the operator's settings."""

    def test_the_suite_runs_without_the_dotenv_values(self):
        import tempfile

        from core.suite_hygiene import without_dotenv

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("W110_FROM_FILE=file\nW110_CHANGED=file\n")
            env = {"W110_FROM_FILE": "file", "W110_CHANGED": "shell", "W110_SHELL": "shell"}
            with patch.dict(os.environ, env):
                with without_dotenv(path):
                    self.assertNotIn("W110_FROM_FILE", os.environ)  # .env's own value
                    self.assertEqual(os.environ["W110_CHANGED"], "shell")  # the shell's
                    self.assertEqual(os.environ["W110_SHELL"], "shell")
                self.assertEqual(os.environ["W110_FROM_FILE"], "file")  # back for later steps


class VisiblePromptTests(unittest.TestCase):
    """#1297: "the menu will just not have a visual input anymore"."""

    def test_the_prompt_is_flushed_before_the_key_is_read(self):
        from core import console_input

        events: list[str] = []

        class Out:
            def write(self, text):
                events.append(f"write:{text}")

            def flush(self):
                events.append("flush")

            def isatty(self):
                return False

        def fake_print(*parts, end="\n"):
            events.append(f"print:{''.join(map(str, parts))}{end}")

        def key():
            events.append("key")
            return "2"

        with patch.object(console_input.sys, "stdout", Out()):
            got = console_input.menu_line(
                "  Select 1-7 [1]: ", read_char=key, print_fn=fake_print, after_key=lambda: None
            )
        self.assertEqual(got, "2")
        before_key = events[: events.index("key")]
        self.assertIn("print:  Select 1-7 [1]: ", before_key)
        # The console shows a line without a newline only once it is flushed.
        self.assertEqual(before_key[-1], "flush")


if __name__ == "__main__":
    unittest.main()
