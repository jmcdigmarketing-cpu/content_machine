"""Wave 107 (the operator, 2026-10-17: "mext 5"; the start screen's focus: "better script
generation and more recency while maintaining accuracy").

1. #1286 run 160, "Analyzing UFC Edmonton odds: Why two outlets picked Mike Malott to KO
   Buckley", came from a headline, so its draft never learned the card's time - the shelf
   would have scheduled it after the fight. A headline that names an event's sides now gets
   that event's start.
2. #1271 health went RED on engagement (25.8% against 32.2%) and said nothing about why.
3. #1270 menu 7 had no way to schedule a video for its slot (the operator: the next free
   noon/10 PM slot).
4. #1272 overnight drafts nothing while 8 or more drafts wait, and nothing said how many to
   decide.
5. #257 facts could not be dropped onto the booth.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

RUN160 = "Analyzing UFC Edmonton odds: Why two outlets picked Mike Malott to KO Buckley"
EVENTS = {
    "UFC Fight Night: Buckley vs. Malott": "2026-10-17T21:00Z",
    "Dallas Cowboys at Green Bay Packers": "2026-10-19T00:20Z",
}
SAT_730_PM_EDT = datetime(2026, 10, 17, 23, 30, tzinfo=timezone.utc)
SUN_NOON = datetime(2026, 10, 18, 16, 0, tzinfo=timezone.utc)


# ---- 1. #1286: a headline knows its event --------------------------------------------------------


class EventForTests(unittest.TestCase):
    def test_a_headline_naming_both_fighters_is_that_card(self):
        from core.seasonal_calendar import event_for

        self.assertEqual(
            event_for(RUN160, events=EVENTS),
            ("UFC Fight Night: Buckley vs. Malott", "2026-10-17T21:00Z"),
        )

    def test_one_team_is_not_the_game(self):
        from core.seasonal_calendar import event_for

        self.assertEqual(event_for("Packers sign a new kicker", events=EVENTS), ("", ""))

    def test_the_week_keeps_started_games_and_recent_cards(self):
        from core.seasonal_calendar import events_from_boards

        board = {"events": [{"name": "Dallas Cowboys at Green Bay Packers",
                             "date": "2026-10-19T00:20Z",
                             "status": {"type": {"completed": False}}},
                            {"name": "Tennessee Titans at Indianapolis Colts",
                             "date": "2026-10-16T17:00Z",
                             "status": {"type": {"completed": True}}}]}  # fmt: skip
        ufc = {"leagues": [{"calendar": [
            {"label": "UFC Fight Night: Buckley vs. Malott", "startDate": "2026-10-17T21:00Z"},
            {"label": "UFC 300: Long Ago", "startDate": "2026-04-14T01:00Z"}]}]}  # fmt: skip
        events = events_from_boards({"nfl": board}, ufc, now=SAT_730_PM_EDT)
        self.assertIn("Tennessee Titans at Indianapolis Colts", events)  # played, still known
        self.assertIn("UFC Fight Night: Buckley vs. Malott", events)  # started tonight
        self.assertNotIn("UFC 300: Long Ago", events)

    def test_the_shelf_leaves_run_160_out(self):
        from core import spaced_queue

        rows = [{"run_id": 160, "title": RUN160, "state": "rendered, never uploaded"}]
        with (
            patch("core.stale_renders.shelf_rows", return_value=rows),
            patch("core.batch_review.draft_meta_for_run", return_value={}),
            patch.object(spaced_queue, "_window_days", return_value=2.0),
            patch.object(spaced_queue, "_age_days", return_value=0.3),
            patch.object(spaced_queue, "_taken_slots", return_value=set()),
            patch("core.seasonal_calendar._EVENTS", dict(EVENTS)),
        ):
            plan = spaced_queue.shelf_schedule("tapin", now=SAT_730_PM_EDT)
        self.assertIsNone(plan[0].publish_at)
        self.assertIn("started", plan[0].skipped)

    def test_the_shelf_line_for_a_started_card_retires_it(self):
        # Live, 2026-10-17: `ops shelf` still offered run 160 `shelf --schedule ... --apply`.
        from core import spaced_queue, stale_renders

        run = SimpleNamespace(id=160, title=RUN160)
        with (
            patch("scripts.requeue_upload.list_recyclable", return_value=[run]),
            patch.object(stale_renders, "render_age_days", return_value=0.4),
            patch.object(stale_renders, "_queued_runs", return_value={}),
            patch.object(stale_renders, "_news_window", return_value=2.0),
            patch.object(stale_renders, "_now", return_value=SAT_730_PM_EDT),
            patch("publishing.go_public.unlisted_holds", return_value=[]),
            patch("publishing.go_public.override_held", return_value=False),
            patch("core.batch_review.draft_meta_for_run", return_value={}),
            patch("core.seasonal_calendar._EVENTS", dict(EVENTS)),
        ):
            rows = stale_renders.shelf_rows("tapin")
            counts = stale_renders.shelf("tapin")
            with (
                patch.object(spaced_queue, "_window_days", return_value=2.0),
                patch.object(spaced_queue, "_age_days", return_value=0.4),
                patch.object(spaced_queue, "_taken_slots", return_value=set()),
            ):
                plan = spaced_queue.shelf_schedule("tapin", run_ids=[160], now=SAT_730_PM_EDT)
        self.assertIn("its game has started", rows[0]["state"])
        self.assertIn("retire-renders --channel tapin --run-id 160 --apply", rows[0]["command"])
        self.assertTrue(rows[0]["stale"])  # it no longer holds one of overnight's three places
        self.assertEqual(counts.get("past_window"), 1)
        # requeue_upload --queue reads the plan: listed and skipped, so it queues nothing.
        self.assertEqual([(p.run_id, p.skipped) for p in plan], [(160, "its game has started")])

    def test_a_draft_written_from_a_headline_records_the_start(self):
        from core.batch_generation import _named_event_start

        drafted = datetime(2026, 10, 17, 13, 9, tzinfo=timezone.utc)
        with patch("core.seasonal_calendar._EVENTS", dict(EVENTS)):
            self.assertEqual(_named_event_start(f"UFC Edmonton predictions {RUN160}", now=drafted),
                             "2026-10-17T21:00Z")  # fmt: skip
            # A recap of a card already fought has no window to miss.
            after = datetime(2026, 10, 18, 3, 0, tzinfo=timezone.utc)
            self.assertEqual(_named_event_start(RUN160, now=after), "")

    def test_crosspost_reads_it_from_the_title(self):
        from publishing import crosspost

        made = datetime(2026, 10, 17, 13, 9, tzinfo=timezone.utc)  # before the card: a preview
        run = SimpleNamespace(title=RUN160, input_topic="UFC Edmonton predictions", created_at=made)
        with (
            patch("core.batch_review.draft_meta_for_run", return_value={}),
            patch.object(crosspost, "_content_run", return_value=run),
            patch("core.seasonal_calendar._EVENTS", dict(EVENTS)),
        ):
            kickoff = crosspost._kickoff_for("tapin", 160)
        self.assertEqual(kickoff, datetime(2026, 10, 17, 21, 0, tzinfo=timezone.utc))


# ---- 2. #1271: why engagement fell ----------------------------------------------------------------


class EngagementWhyTests(unittest.TestCase):
    def _info(self):
        info = {}
        for run in range(1, 11):  # the baseline: short videos, 35%
            info[run] = {"domain": "gaming", "seconds": 45.0, "hook": 80, "footage": "gameplay"}
        for run in range(11, 16):  # the last five: long ones, 20%
            info[run] = {"domain": "gaming", "seconds": 85.0, "hook": 80, "footage": "gameplay"}
        rates = {run: (0.35 if run <= 10 else 0.20) for run in info}
        return rates, info

    def test_the_pattern_names_what_the_last_five_share(self):
        from core.channel_health import engagement_why

        rates, info = self._info()
        lines = engagement_why(rates, info)
        self.assertTrue(lines)
        self.assertIn("5 of the last 5", lines[0])
        self.assertIn("over 75 s", lines[0])
        self.assertIn("20%", lines[0])
        self.assertIn("35%", lines[0])

    def test_with_no_shared_trait_it_names_the_weakest_of_the_five(self):
        # Live, 2026-10-17: the long videos did better, not worse - but run 120, a 406 s NBA
        # video with a hook of 63, sat at 12%.
        from core.channel_health import engagement_why

        rates = dict.fromkeys(range(1, 11), 0.32)
        info = {run: {"domain": "gaming", "seconds": 60.0, "hook": 78} for run in range(1, 11)}
        rates.update({11: 0.30, 12: 0.12, 13: 0.33, 14: 0.31, 15: 0.29})
        info.update({11: {"domain": "gaming", "seconds": 60.0, "hook": 78},
                     12: {"domain": "nba", "seconds": 406.0, "hook": 63},
                     13: {"domain": "ufc", "seconds": 50.0, "hook": 80},
                     14: {"domain": "nfl", "seconds": 62.0, "hook": 78},
                     15: {"domain": "gaming", "seconds": 58.0, "hook": 78}})  # fmt: skip
        lines = engagement_why(rates, info)
        self.assertIn("weakest", lines[0])
        self.assertIn("run 12", lines[0])
        self.assertIn("406 s", lines[0])
        self.assertIn("12%", lines[0])

    def test_health_shows_it_under_engagement(self):
        from core.channel_health import HealthReport, HealthSub, render_health

        sub = HealthSub("engagement", "red", "declining", why=["5 of the last 5 run over 75 s"])
        text = render_health(HealthReport("tapin", "red", [sub]))
        self.assertIn("why: 5 of the last 5 run over 75 s", text)


# ---- 3. #1270: menu 7 schedules a video for its slot -----------------------------------------------


class ScheduleFromWatchTests(unittest.TestCase):
    def test_s_schedules_it_at_the_next_free_slot(self):
        from publishing import go_public

        row = SimpleNamespace(id=1, content_run_id=170, youtube_video_id="vid170",
                              privacy_status="unlisted", channel_id="tapin")  # fmt: skip
        sched = MagicMock(
            return_value=SimpleNamespace(status="scheduled", detail="Sun 12:00 PM EDT")
        )
        with (
            patch.object(go_public, "unlisted_holds", return_value=[row]),
            patch.object(go_public, "_run_for_hold", return_value=None),
            patch.object(go_public, "load_features", return_value={}),
            patch("core.spaced_queue.slot_for_run", return_value=(SUN_NOON, "")),
            patch.object(go_public, "apply_schedule_public", sched),
            patch.object(go_public, "apply_go_public") as now,
        ):
            decisions = go_public.watch_and_publish("tapin", ask=lambda _p: "s",
                                                    print_fn=lambda *_a: None)  # fmt: skip
        self.assertEqual(decisions, ["slot"])
        now.assert_not_called()
        self.assertEqual(sched.call_args.kwargs["when"], SUN_NOON)

    def test_the_update_sets_publish_at_and_the_log_says_scheduled(self):
        from publishing import go_public

        record = SimpleNamespace(id=7, content_run_id=170, youtube_video_id="vid170",
                                 privacy_status="unlisted")  # fmt: skip
        repo = MagicMock()
        repo.list_uploaded_for_channel.return_value = [record]
        service = MagicMock()
        with (
            patch.dict(os.environ, {"YOUTUBE_UPLOAD_ENABLED": "true"}),
            patch.object(go_public, "override_held", return_value=False),
            patch("publishing.snippet_update.manage_scope_problem", return_value=""),
            patch("youtube.oauth.get_youtube_service", return_value=service),
            patch.object(go_public, "_run_title", return_value="A video"),
        ):
            result = go_public.apply_schedule_public(
                "vid170", channel_id="tapin", when=SUN_NOON, repo=repo
            )
        body = service.videos.return_value.update.call_args.kwargs["body"]
        self.assertEqual(body["status"]["privacyStatus"], "private")
        self.assertEqual(body["status"]["publishAt"], "2026-10-18T16:00:00.000Z")
        self.assertEqual(result.status, "scheduled")
        fields = repo.update.call_args.args[1]
        self.assertEqual(fields["status"], "scheduled")
        self.assertEqual(fields["published_at"], SUN_NOON)

    def test_a_held_claim_is_refused(self):
        from publishing import go_public

        record = SimpleNamespace(id=7, content_run_id=170, youtube_video_id="vid170",
                                 privacy_status="unlisted")  # fmt: skip
        repo = MagicMock()
        repo.list_uploaded_for_channel.return_value = [record]
        with patch.object(go_public, "override_held", return_value=True):
            result = go_public.apply_schedule_public(
                "vid170", channel_id="tapin", when=SUN_NOON, repo=repo
            )
        self.assertEqual(result.status, "refused")

    def test_the_slot_is_the_next_free_one(self):
        from core import spaced_queue

        with (
            patch.object(spaced_queue, "_window_days", return_value=7.0),
            patch.object(spaced_queue, "_age_days", return_value=0.1),
            patch.object(
                spaced_queue,
                "_taken_slots",
                return_value={datetime(2026, 10, 18, 2, 0, tzinfo=timezone.utc)},
            ),  # fmt: skip
            patch("core.batch_review.draft_meta_for_run", return_value={}),
        ):
            when, why = spaced_queue.slot_for_run("tapin", 170, title="A video",
                                                  now=SAT_730_PM_EDT)  # fmt: skip
        self.assertEqual((when, why), (SUN_NOON, ""))

    def test_with_no_title_given_it_reads_the_runs_own(self):
        # Live, 2026-10-17: slot_for_run(160) with no title gave the started Malott card a slot.
        from core import spaced_queue

        run = SimpleNamespace(title=RUN160)
        events = dict(EVENTS)
        with (
            patch.object(spaced_queue, "_window_days", return_value=7.0),
            patch.object(spaced_queue, "_age_days", return_value=1.0),
            patch.object(spaced_queue, "_taken_slots", return_value=set()),
            patch("core.batch_review.draft_meta_for_run", return_value={}),
            patch("storage.repositories.content_runs.get_content_run_repository") as repo,
            patch("core.seasonal_calendar._EVENTS", events),
        ):
            repo.return_value.get.return_value = run
            when, why = spaced_queue.slot_for_run(
                "tapin", 160, now=SAT_730_PM_EDT + timedelta(hours=3)
            )
        self.assertEqual((when, why), (None, "its game has started"))

    def test_the_menu_offers_it(self):
        from core.ui import prompt_startup_mode

        said: list[str] = []
        with patch("core.intelligence_report.intelligence_mode_enabled", return_value=False):
            prompt_startup_mode(print_fn=lambda *a: said.append(" ".join(map(str, a))),
                                input_fn=lambda _p: "1")  # fmt: skip
        self.assertTrue(any("7)" in line and "slot" in line for line in said))


# ---- 4. #1272: how many drafts to decide --------------------------------------------------------


class DraftsLineTests(unittest.TestCase):
    def _line(self, waiting):
        from core import batch_review

        drafts = [SimpleNamespace(run_id=i) for i in range(waiting)]
        with (
            patch.object(
                batch_review,
                "unattended_candidates",
                return_value=([], [(d, "needs you") for d in drafts]),
            ),  # fmt: skip
            patch.object(batch_review, "pending_drafts", return_value=drafts),
            patch.object(batch_review, "unattended_limit", return_value=0),
        ):
            return batch_review.drafts_line("tapin")

    def test_over_the_cap_it_says_how_many(self):
        self.assertIn("overnight drafts again once 2 are decided", self._line(9))

    def test_under_the_cap_it_says_nothing_of_it(self):
        self.assertNotIn("overnight drafts again", self._line(5))


# ---- 5. #257: facts dropped onto the booth ---------------------------------------------------------


class BoothFactsTests(unittest.TestCase):
    def test_the_form_is_read(self):
        from core.review_booth import parse_booth_facts_post

        body = b"run_id=160&facts=Malott+is+11-2.%0AThe+card+is+in+Edmonton."
        self.assertEqual(parse_booth_facts_post(body, expected_run_id=160),
                         (160, "Malott is 11-2.\nThe card is in Edmonton."))  # fmt: skip

    def test_another_run_is_refused(self):
        from core.review_booth import parse_booth_facts_post

        with self.assertRaises(ValueError):
            parse_booth_facts_post(b"run_id=99&facts=x", expected_run_id=160)

    def test_the_facts_go_to_the_vault_as_the_operators(self):
        from core import review_booth

        capture = MagicMock(return_value="note.md")
        with (
            patch(
                "core.facts.claim_confirm._run_subject",
                return_value=("tapin", "UFC Edmonton predictions"),
            ),  # fmt: skip
            patch("core.operator_facts.capture_facts_to_vault", capture),
        ):
            saved = review_booth.apply_booth_facts(160, "Malott is 11-2.\nThe card is in Edmonton.")
        self.assertEqual(saved, 2)
        args, kwargs = capture.call_args
        self.assertEqual(args[:2], ("tapin", "UFC Edmonton predictions"))
        self.assertEqual(kwargs["tier"], "operator")

    def test_the_booth_has_a_drop_zone(self):
        from core.review_booth import booth_html

        html = booth_html(run_id=160)
        self.assertIn("/save-facts", html)
        self.assertIn("drop", html.lower())


if __name__ == "__main__":
    unittest.main()
