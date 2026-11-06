"""Wave 146 (2026-11-03) - the next five, S01 (long-form hours) the shortfall it takes.

#1978 a countdown's opener is read against its countdown, not its long title (run 231 was held);
#1976 the 16:9 cut ends on the channel's end card; #1977 a promoted video's paid views to date
are asked once its record cannot explain its views (run 170: 37,602 views, 0 recorded paid);
#1743 last month's best Shorts as one long video on the 1st; #1740 a Short past 1,000 organic
views in its first 5 days gets a long video on its topic.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Imported before any patch below: a module first imported under a patch of a name it imports
# binds the mock for the rest of the process (wave 145's reversed-suite failure).
import analytics.growth
import analytics.youtube_metrics
import core.batch_generation
import core.batch_review
import core.best_bet
import core.overnight
import core.series.countdown
import core.series.dated
import core.ypp_readiness
import video.channel_outro
import video.render_profiles
import video.render_video
import video.week_compile

UTC = timezone.utc
NOW = datetime(2026, 11, 3, 15, 0, tzinfo=UTC)
COUNTDOWN_ROW = {"id": "gta6-countdown", "kind": "countdown", "subject": "GTA 6",
                 "names": ["GTA 6", "GTA VI"], "title": "GTA 6: {n} days to launch",
                 "from": "2026-10-29", "until": "2026-11-19", "domain": "gaming"}  # fmt: skip
RUN231_TOPIC = "GTA 6: 16 days to launch - GTA 6 Launch: What to Expect"
RUN231_SCRIPT = (
    "Your boss already knows why you want Nov. 19 off. Rockstar's launch is sixteen days out, "
    "and the preload date just leaked."
)


# ---- #1978: a countdown's opener against its countdown --------------------------------------------


def _draft(topic: str, script: str, *, series: str = "countdown") -> core.batch_review.PendingDraft:
    meta = {"topic": topic, "title": topic, "series": series, "channel_id": "tapin", "run_id": 231}
    return core.batch_review.PendingDraft(folder="", meta=meta, script=script)


class CountdownOpenerTests(unittest.TestCase):
    def test_run231s_launch_day_opener_is_on_its_story(self):
        from core.batch_review import countdown_opener_on_subject

        self.assertTrue(
            countdown_opener_on_subject(RUN231_TOPIC, RUN231_SCRIPT, launch="2026-11-19")
        )

    def test_an_opener_naming_the_subject_is_on_its_story(self):
        from core.batch_review import countdown_opener_on_subject

        script = "Sixteen days out from GTA VI, and Rockstar went quiet. Here's why."
        self.assertTrue(
            countdown_opener_on_subject(RUN231_TOPIC, script, names=["GTA 6", "GTA VI"])
        )

    def test_an_unrelated_opener_or_another_day_is_not(self):
        from core.batch_review import countdown_opener_on_subject

        self.assertFalse(countdown_opener_on_subject(
            RUN231_TOPIC, "The Knicks lost again tonight. Here's the box score.",
            launch="2026-11-19"))  # fmt: skip
        self.assertFalse(countdown_opener_on_subject(
            RUN231_TOPIC, "Your boss knows why you want Nov. 18 off. More soon.",
            launch="2026-11-19"))  # fmt: skip

    def test_an_on_subject_countdown_skips_the_second_read(self):
        with (
            patch.object(core.batch_review, "_countdown_row", return_value=COUNTDOWN_ROW),
            patch.object(core.batch_review, "second_read", side_effect=AssertionError) as read,
        ):
            self.assertEqual(
                core.batch_review._second_read_for(_draft(RUN231_TOPIC, RUN231_SCRIPT)), ""
            )
        read.assert_not_called()

    def test_an_off_subject_countdown_is_read_knowing_it_is_one(self):
        draft = _draft(RUN231_TOPIC, "The Knicks lost again tonight. Then this happened.")
        with (
            patch.object(core.batch_review, "_countdown_row", return_value=COUNTDOWN_ROW),
            patch.object(core.batch_review, "second_read", return_value="unrelated") as read,
        ):
            self.assertEqual(core.batch_review._second_read_for(draft), "unrelated")
        self.assertIn("daily countdown to GTA 6", read.call_args.kwargs["context"])

    def test_any_other_draft_is_read_as_before(self):
        draft = _draft("Knicks beat the Heat", "The Knicks won.", series="")
        with patch.object(core.batch_review, "second_read", return_value="") as read:
            core.batch_review._second_read_for(draft)
        read.assert_called_once_with("Knicks beat the Heat", "The Knicks won.")

    def test_the_context_reaches_the_model(self):
        seen: list[str] = []

        def call(_system: str, user: str) -> dict:
            seen.append(user)
            return {"ok": True}

        core.batch_review.second_read("T", "First. Second.", call=call, context="A daily countdown")
        self.assertIn("\nCONTEXT: A daily countdown", seen[0])

    def test_the_row_is_found_by_its_title_stem(self):
        with patch("core.series.countdown.series_rows", return_value=[COUNTDOWN_ROW]):
            self.assertEqual(core.batch_review._countdown_row(RUN231_TOPIC)["until"], "2026-11-19")
            self.assertEqual(core.batch_review._countdown_row("Knicks beat the Heat"), {})


# ---- #1976: the 16:9 cut's end card ---------------------------------------------------------------

CARD = {"enabled": True, "duration": 3.0, "text": "Follow TapIn", "bg": "#000000", "fg": "#FFFFFF"}


class LandscapeEndCardTests(unittest.TestCase):
    def test_a_landscape_card_is_its_own_frame_with_the_copy_centred(self):
        cmd = video.channel_outro.build_outro_concat_command(
            body_path="b.mp4", output_path="o.mp4", card=CARD, width=1920, height=1080
        )
        joined = " ".join(cmd)
        self.assertIn("s=1920x1080", joined)
        self.assertIn("scale=1920:1080", joined)
        self.assertIn("y=(h-text_h)/2,", joined)

    def test_the_vertical_card_is_unchanged(self):
        joined = " ".join(video.channel_outro.build_outro_concat_command(
            body_path="b.mp4", output_path="o.mp4", card=CARD))  # fmt: skip
        self.assertIn("s=1080x1920", joined)
        self.assertNotIn("y=(h-text_h)/2,", joined)

    def test_the_extra_cut_gets_the_card_at_its_size(self):
        landscape = video.render_profiles.RenderProfile("landscape", 1920, 1080, "_16x9")
        with tempfile.TemporaryDirectory() as tmp:
            primary = os.path.join(tmp, "run.mp4")
            open(os.path.join(tmp, "run_16x9.mp4"), "wb").close()
            with (
                patch("video.render_profiles.extra_profiles", return_value=[landscape]),
                patch("video.render_profiles.landscape_ass_file", return_value=None),
                patch.object(video.render_video, "build_render_ffmpeg_command", return_value=["ff"]),
                patch.object(video.render_video, "_ffmpeg_run",
                             return_value=SimpleNamespace(returncode=0, stderr="")),
                patch("video.channel_outro.resolve_end_card", return_value=CARD),
                patch("video.channel_outro.append_channel_outro") as append,
            ):  # fmt: skip
                written = video.render_video._render_extra_formats(
                    background_path="bg.mp4", mp3_path="v.mp3", primary_output=primary,
                    subtitle_path="s.ass", duration=540.0, stage=lambda _m: None,
                    channel_id="tapin",  # #1622 (wave 152): a long video's cut - a Short's has none
                )  # fmt: skip
        self.assertEqual(len(written), 1)
        append.assert_called_once()
        self.assertEqual((append.call_args.kwargs["width"], append.call_args.kwargs["height"]),
                         (1920, 1080))  # fmt: skip

    def test_a_failed_card_keeps_the_cut(self):
        landscape = video.render_profiles.RenderProfile("landscape", 1920, 1080, "_16x9")
        with (
            patch("video.channel_outro.resolve_end_card", return_value=CARD),
            patch("video.channel_outro.append_channel_outro", side_effect=RuntimeError("ffmpeg")),
            self.assertLogs("content_machine.video.render", level="WARNING"),
        ):
            video.render_video._end_card_on_cut("cut.mp4", landscape, "tapin")


# ---- #1977: paid views after the synced window ----------------------------------------------------

# Run 170 as the store held it on 11-03: promoted for $14.55, 325 views from its first days.
RUN170 = {"views": 325, "paid_views": 0, "lifetime_views": 37602}


class PaidToDateTests(unittest.TestCase):
    def test_the_most_any_record_holds(self):
        from analytics.youtube_metrics import recorded_paid

        self.assertEqual(
            recorded_paid({"paid_views": 40, "daily_paid_views": [["d", 30], ["e", 30]]}), 60
        )
        self.assertEqual(recorded_paid({"paid_views": 40, "lifetime_paid_views": 37000}), 37000)
        self.assertEqual(recorded_paid({}), 0)

    def test_run170_is_due_and_not_organic_until_asked(self):
        from analytics.youtube_metrics import organic_lifetime, paid_check_due

        self.assertTrue(paid_check_due(RUN170, now=NOW))
        self.assertIsNone(organic_lifetime(RUN170))
        asked = {**RUN170, "lifetime_paid_views": 37100, "lifetime_paid_at": NOW.isoformat(),
                 "lifetime_paid_checked": 37602}  # fmt: skip
        self.assertEqual(organic_lifetime(asked), 502)
        self.assertFalse(paid_check_due(asked, now=NOW + timedelta(days=1)))

    def test_asked_again_after_a_week_of_growth(self):
        from analytics.youtube_metrics import paid_check_due

        asked = {"views": 325, "lifetime_views": 37800, "lifetime_paid_views": 37100,
                 "lifetime_paid_at": NOW.isoformat(), "lifetime_paid_checked": 37602}  # fmt: skip
        self.assertTrue(paid_check_due(asked, now=NOW + timedelta(days=8)))
        self.assertFalse(paid_check_due(asked, now=NOW + timedelta(days=3)))

    def test_a_video_whose_record_explains_its_views_is_not_asked(self):
        from analytics.youtube_metrics import organic_lifetime, paid_check_due

        young = {"views": 980, "paid_views": 0, "lifetime_views": 1010}
        self.assertFalse(paid_check_due(young, now=NOW))
        self.assertEqual(organic_lifetime(young), 1010)
        self.assertIsNone(organic_lifetime({"views": 50}))

    def test_the_due_videos_are_asked_from_their_publish_day(self):
        rows = [
            SimpleNamespace(id=1, youtube_video_id="v170", metrics_json=json.dumps(RUN170),
                            published_at=datetime(2026, 10, 19, tzinfo=UTC)),
            SimpleNamespace(id=2, youtube_video_id="vok", published_at=NOW,
                            metrics_json=json.dumps({"views": 90, "lifetime_views": 95})),
        ]  # fmt: skip
        asks: list[tuple] = []

        def fetch(video, *, channel_id, start, end):
            asks.append((video, start, end))
            return [["2026-10-20", 30000], ["2026-10-21", 7100]]

        repo = MagicMock()
        with patch.object(
            analytics.youtube_metrics, "get_publish_log_repository", return_value=repo
        ):
            asked = analytics.youtube_metrics.store_lifetime_paid(
                rows, {"v170": 37602, "vok": 95}, channel_id="tapin", now=NOW, fetch=fetch
            )
        self.assertEqual(asked, 1)
        self.assertEqual(asks, [("v170", "2026-10-19", "2026-11-03")])
        row_id, change = repo.update.call_args.args
        stored = json.loads(change["metrics_json"])
        self.assertEqual((row_id, stored["lifetime_paid_views"], stored["lifetime_paid_checked"]),
                         (1, 37100, 37602))  # fmt: skip

    def test_an_unanswered_ask_writes_nothing(self):
        row = SimpleNamespace(id=1, youtube_video_id="v170", metrics_json=json.dumps(RUN170),
                              published_at=datetime(2026, 10, 19, tzinfo=UTC))  # fmt: skip
        repo = MagicMock()
        with patch.object(
            analytics.youtube_metrics, "get_publish_log_repository", return_value=repo
        ):
            self.assertEqual(analytics.youtube_metrics.store_lifetime_paid(
                [row], {}, now=NOW, fetch=lambda *_a, **_k: None), 0)  # fmt: skip
        repo.update.assert_not_called()

    def test_the_growth_report_counts_them_and_organic_is_unchanged(self):
        metrics = {**RUN170, "lifetime_paid_views": 37100, "lifetime_paid_at": NOW.isoformat()}
        row = SimpleNamespace(
            youtube_video_id="v170",
            metrics_json=json.dumps(metrics),
            published_at=datetime(2026, 10, 19, tzinfo=UTC),
            content_run_id=170,
        )
        with (
            patch.object(
                analytics.growth,
                "_repo",
                return_value=SimpleNamespace(list_uploaded_for_channel=lambda _c: [row]),
            ),
            patch("storage.repositories.publish_log.video_title", return_value="Modern Warfare 4"),
        ):
            rows = analytics.growth._rows("tapin")
        self.assertEqual((rows[0]["paid_to_date"], rows[0]["paid"]), (37100, 0))
        # the menu's domain order reads views less the window's paid: still 325, not 0
        with patch.object(analytics.growth, "_kind", return_value=("gaming", "Shorts")):
            self.assertEqual(analytics.growth.organic_views_by_domain(rows)["gaming"]["views"], 325)
        # the paid total counts every paid view on record (`ops growth`'s paid line)
        with (
            patch.object(analytics.growth, "_rows", return_value=rows),
            patch.object(analytics.growth, "_channel_paid", return_value=None),
        ):
            self.assertEqual(analytics.growth.report("tapin")["paid"]["views"], 37100)


# ---- #1743: the month's best Shorts ---------------------------------------------------------------


def _short(i: int, views: int) -> dict:
    return {"run_id": 300 + i, "title": f"Short {i} about GTA 6", "words": "", "path": f"s{i}.mp4",
            "published_at": datetime(2026, 10, 1 + i, 12, tzinfo=UTC), "offset": 0.0,
            "names": ["GTA 6"], "views": views}  # fmt: skip


class MonthCompileTests(unittest.TestCase):
    def setUp(self):
        self.patches = [
            patch.object(video.week_compile, "_duration", return_value=60.0),
            patch.object(video.week_compile, "_intro_offset", return_value=0.0),
            patch.object(video.week_compile, "_channel_name", return_value="TapIn"),
            patch.object(video.week_compile, "_with_disclosure", side_effect=lambda _c, d: d),
            patch("core.spaced_queue._channel_tz", return_value=UTC),
        ]
        for item in self.patches:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in self.patches])

    def test_last_month_in_the_channels_zone(self):
        start, end = video.week_compile.last_month(
            "tapin", now=datetime(2026, 11, 1, 10, tzinfo=UTC)
        )
        self.assertEqual(
            (start.date().isoformat(), end.date().isoformat()), ("2026-10-01", "2026-11-01")
        )
        start, _end = video.week_compile.last_month(
            "tapin", now=datetime(2027, 1, 1, 10, tzinfo=UTC)
        )
        self.assertEqual(start.date().isoformat(), "2026-12-01")

    def test_the_ten_best_counted_down_in_five_to_eight_minutes(self):
        shorts = [_short(i, views=100 * (i + 1)) for i in range(12)]
        with patch.object(video.week_compile, "_public_shorts", return_value=shorts) as found:
            plan = video.week_compile.plan_month("tapin", now=datetime(2026, 11, 1, 10, tzinfo=UTC))
        self.assertTrue(found.call_args.kwargs["lifetime"])
        self.assertEqual((plan.kind, plan.week, len(plan.items)), ("month", "2026-10", 10))
        self.assertEqual([i["rank"] for i in plan.items], list(range(10, 0, -1)))
        self.assertEqual([i["run_id"] for i in plan.items if i["deep"]], [309, 310, 311])
        self.assertTrue(all(i["clip"] is None for i in plan.items if i["deep"]))
        self.assertTrue(300 <= plan.seconds <= 480, plan.seconds)
        self.assertTrue(plan.title.endswith("TapIn Best of October 2026"), plan.title)
        self.assertIn("0:00 #10: Short 2 about GTA 6", plan.description)

    def test_a_thin_month_makes_none(self):
        with patch.object(video.week_compile, "_public_shorts", return_value=[_short(1, 9)] * 4):
            self.assertIsNone(video.week_compile.plan_month("tapin", now=NOW))

    def test_ranked_by_organic_views_to_date(self):
        asked = {**RUN170, "lifetime_paid_views": 37100, "lifetime_paid_at": NOW.isoformat()}
        self.assertEqual(video.week_compile._organic_views(json.dumps(asked), lifetime=True), 502)
        self.assertEqual(video.week_compile._organic_views(json.dumps(RUN170), lifetime=True), 325)
        self.assertEqual(video.week_compile._organic_views(json.dumps(asked)), 325)  # the week's

    def test_recorded_as_the_months_and_made_once(self):
        plan = video.week_compile.WeekPlan("tapin", "2026-10", "Best of October", "d", kind="month")
        with patch("core.run_recorder.record_content_run", return_value=9) as record:
            video.week_compile._record(plan, "m.mp4")
        features = record.call_args.kwargs["features"]
        self.assertEqual(features["compilation"]["month"], "2026-10")
        self.assertNotIn("week", features["compilation"])
        runs = [SimpleNamespace(features_json=json.dumps(features))]
        with patch("storage.repositories.content_runs.get_content_run_repository",
                   return_value=SimpleNamespace(list_for_channel=lambda _c: runs)):  # fmt: skip
            self.assertTrue(video.week_compile.week_done("tapin", "2026-10", kind="month"))
            self.assertFalse(video.week_compile.week_done("tapin", "2026-10"))
        self.assertTrue(video.week_compile._out_path("tapin", "2026-10", kind="month")
                        .endswith("month_2026-10.mp4"))  # fmt: skip

    def test_the_dry_run_says_what_it_would_make(self):
        plan = video.week_compile.WeekPlan("tapin", "2026-10", "GTA 6 - TapIn Best of October 2026",
                                           "x\n\n0:00 #10: a\n", seconds=400.0, kind="month")  # fmt: skip
        with (
            patch.object(video.week_compile, "plan_month", return_value=plan),
            patch.object(video.week_compile, "week_done", return_value=False),
        ):
            lines = video.week_compile.compile_month("tapin")
        self.assertTrue(lines[0].startswith("  Month compilation: GTA 6 - TapIn Best of October"))
        self.assertIn("    0:00 #10: a", lines)
        self.assertIn("Dry run", lines[-1])

    def test_overnight_makes_it_on_the_first(self):
        result = SimpleNamespace(channel_id="tapin", week_line="  Week compilation: made.")
        with (
            patch.dict(os.environ, {"MONTH_COMPILE": "true"}),
            patch("core.nightly_task.beat_step"),
            patch(
                "video.week_compile.compile_month", return_value=["  Month compilation: x"]
            ) as make,
        ):
            core.overnight._month_compile(result, now=datetime(2026, 12, 1, 10, tzinfo=UTC))
            core.overnight._month_compile(result, now=datetime(2026, 12, 2, 10, tzinfo=UTC))
        make.assert_called_once()
        self.assertEqual(result.week_line, "  Week compilation: made.\n  Month compilation: x")

    def test_the_suite_pins_it_off(self):
        result = SimpleNamespace(channel_id="tapin", week_line="")
        with patch("video.week_compile.compile_month") as make:
            core.overnight._month_compile(result, now=datetime(2026, 12, 1, 10, tzinfo=UTC))
        make.assert_not_called()

    def test_ops_week_compile_month(self):
        from scripts import ops

        args = SimpleNamespace(channel="tapin", apply=False, schedule=False, month=True)
        with (
            patch("video.week_compile.compile_month", return_value=["  m"]) as month,
            patch("video.week_compile.compile_week", return_value=["  w"]) as week,
            patch("builtins.print"),
        ):
            ops.cmd_week_compile(args)
        month.assert_called_once()
        week.assert_not_called()


# ---- #1740: a long video on a Short past 1,000 organic views --------------------------------------


def _row(run_id: int, days_ago: float, metrics: dict) -> SimpleNamespace:
    return SimpleNamespace(content_run_id=run_id, youtube_video_id=f"v{run_id}",
                           published_at=NOW - timedelta(days=days_ago),
                           metrics_json=json.dumps(metrics))  # fmt: skip


class LongBreakoutTests(unittest.TestCase):
    def _found(self, rows: list, features: dict | None = None) -> list[dict]:
        run = SimpleNamespace(features_json=json.dumps(features or {"entity_research": {"names": ["GTA 6"]}}),
                              domain="gaming")  # fmt: skip
        with (
            patch("storage.repositories.publish_log.get_publish_log_repository",
                  return_value=SimpleNamespace(list_uploaded_for_channel=lambda _c: rows)),
            patch("storage.repositories.content_runs.get_content_run_repository",
                  return_value=SimpleNamespace(get=lambda _i: run)),
            patch("storage.repositories.publish_log.video_title",
                  side_effect=lambda r, fallback="": f"Short {r.content_run_id}"),
        ):  # fmt: skip
            return core.batch_generation.long_breakouts("tapin", now=NOW)

    def test_a_short_past_1000_organic_views_in_five_days(self):
        found = self._found([_row(191, 2, {"views": 1091, "paid_views": 0})])
        self.assertEqual([(f["title"], f["views"], f["names"]) for f in found],
                         [("Short 191", 1091, ["GTA 6"])])  # fmt: skip

    def test_not_older_not_fewer_not_paid_not_a_compilation(self):
        self.assertEqual(self._found([_row(1, 6, {"views": 5000})]), [])
        self.assertEqual(self._found([_row(2, 1, {"views": 1400, "paid_views": 500})]), [])
        self.assertEqual(self._found([_row(170, 3, RUN170)]), [])  # its ads, not yet asked
        self.assertEqual(
            self._found([_row(3, 1, {"views": 3000})], {"compilation": {"week": "w"}}), []
        )

    def test_one_long_idea_written_from_the_weeks_headlines(self):
        found = [{"title": "GTA 6 online mode may repeat GTA Online's early mistakes",
                  "published": NOW - timedelta(days=2), "views": 1091, "names": ["GTA 6"],
                  "domain": "gaming"}]  # fmt: skip
        lines = [{"title": "GTA 6 preload date confirmed", "source": "IGN",
                  "published": NOW - timedelta(hours=5)},
                 {"title": "Knicks beat the Heat", "source": "ESPN",
                  "published": NOW - timedelta(hours=5)}]  # fmt: skip
        with (
            patch.object(core.batch_generation, "long_breakouts", return_value=found),
            patch.object(core.batch_generation, "series_drafted", return_value=False),
        ):
            ideas = core.batch_generation.long_breakout_ideas(
                "tapin", now=NOW, headlines=lambda *_a: lines
            )
        self.assertEqual(len(ideas), 1)
        idea = ideas[0]
        self.assertEqual((idea.source, idea.draft_kind), ("long", "long"))
        self.assertEqual(idea.topic, f'The full story behind "{found[0]["title"]}"')
        self.assertEqual(idea.facts, ["IGN reported: GTA 6 preload date confirmed"])
        self.assertIn("1,091 organic views", idea.rationale)

    def test_once_and_never_raising(self):
        found = [{"title": "T", "published": NOW, "views": 1500, "names": [], "domain": "gaming"}]
        with (
            patch.object(core.batch_generation, "long_breakouts", return_value=found),
            patch.object(core.batch_generation, "series_drafted", return_value=True),
        ):
            self.assertEqual(core.batch_generation.long_breakout_ideas("tapin", now=NOW), [])
        with patch.object(core.batch_generation, "long_breakouts", side_effect=RuntimeError("db")):
            self.assertEqual(core.batch_generation.long_breakout_ideas("tapin", now=NOW), [])

    def test_the_night_drafts_it_even_with_drafts_waiting(self):
        bet = core.best_bet.BestBetResult(topic='The full story behind "T"', domain="gaming",
                                          avg_engaged_rate=0.0, source="long", supporting_runs=0,
                                          rationale="r", draft_kind="long")  # fmt: skip
        with (
            patch("core.series.countdown.countdown_idea", return_value=None),
            patch("core.series.dated.dated_ideas", return_value=[]),
            patch.object(core.batch_generation, "long_breakout_ideas", return_value=[bet]),
        ):
            picks: dict = {}
            topics = core.batch_generation.collect_topics("tapin", count=0, picks=picks)
        self.assertEqual(topics, ['The full story behind "T"'])
        self.assertEqual(picks[bet.topic]["draft_kind"], "long")


if __name__ == "__main__":
    unittest.main()
