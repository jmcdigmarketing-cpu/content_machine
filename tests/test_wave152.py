"""Wave 152 (2026-11-06) - the next ten, before W4's freeze.

#1622 a Short ends on its last word; #1599 a marquee competitor breakout first; #1597 the marquee
list learns; #1613 marquee injury news first; #1612 a numbered card's fight week first; #1874
weigh-ins and fight-week drama, #1890 press-conference quotes, through the fast lane; #1648 three
Shorts a day for two weeks; #1653 five drafts a night when five pass the gate; #1892 a numbered
card's main event as a 6-8 minute match-up.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Imported before any patch below (wave 145's reversed-suite failure).
import core.batch_generation
import core.batch_review
import core.best_bet
import core.series.dated
import core.series.long_form
import core.series.recap
import core.series.worked
import video.render_video

UTC = timezone.utc
NOW = datetime(2026, 11, 10, 11, tzinfo=UTC)  # Tuesday's overnight, UFC 334 four days away
CARD = {"label": "UFC 334: Gane vs. Hokit", "startDate": "2026-11-15T01:00Z"}
BOARD = {"leagues": [{"calendar": [
    {"label": "UFC Fight Night: Cortes Acosta vs. Walker", "startDate": "2026-11-08T01:00Z"},
    CARD,
    {"label": "UFC 335: Oliveira vs. Lopes", "startDate": "2026-12-13T01:00Z"},
]}]}  # fmt: skip
MARQUEE = ["GTA 6", "Mahomes", "Topuria", "Dana White", "Jon Jones"]


def _lane():
    import jobs.fast_lane

    return jobs.fast_lane


def _bet(topic, domain="nfl", source="trending", outlets=3, **extra):
    return core.best_bet.BestBetResult(topic=topic, domain=domain, avg_engaged_rate=0.0,
                                       source=source, supporting_runs=0, rationale="",
                                       outlets=outlets, **extra)  # fmt: skip


def _cand(topic, outlets, minutes_ago, domain="ufc", now=NOW):
    first = now - timedelta(minutes=minutes_ago)
    return {"topic": topic, "domain": domain, "published": first, "first": first,
            "outlets": [f"Outlet {i}" for i in range(outlets)]}  # fmt: skip


# ---- #1622: a Short ends on its last word -------------------------------------------------------


class EndCardTests(unittest.TestCase):
    def _render(self, seconds):
        asset = MagicMock(path="C:/tmp/bg.mp4", provider="local", attribution="")
        ok = MagicMock(returncode=0, stderr="")
        card = {"enabled": True, "duration": 1.5, "text": "TAP IN FOR MORE", "bg": "#000000",
                "fg": "#FFFFFF"}  # fmt: skip
        with (
            patch("video.render_video.get_background_asset", return_value=asset),
            patch("video.render_video.generate_subtitle_file", return_value="C:/tmp/s.srt"),
            patch("video.render_video._resolve_music_bed", return_value=None),
            patch("video.render_video._probe_video_duration", return_value=float(seconds)),
            patch("video.render_video._render_extra_formats", return_value=[]),
            patch("video.render_video.os.makedirs"),
            patch("video.render_video.is_render_progress_enabled", return_value=False),
            patch("assets.manager.get_scene_matched_background", return_value=None),
            patch("video.channel_intro.resolve_intro_path", return_value=None),
            patch("video.channel_outro.resolve_end_card", return_value=card),
            patch("video.channel_outro.append_channel_outro") as outro,
            patch("video.render_video.subprocess.run", return_value=ok),
        ):
            video.render_video.render_vertical_video(
                "C:/tmp/a.mp3", "topic", "out.mp4", "script words", channel_id="tapin",
                render_preset="publish",
            )  # fmt: skip
        return outro.called

    def test_a_short_ends_on_its_last_word_and_a_long_video_keeps_its_card(self):
        self.assertFalse(self._render(40))  # every Short ended on 1.5 s of "TAP IN FOR MORE"
        self.assertTrue(self._render(540))

    def test_the_bound_is_the_long_videos(self):
        from core.music import LONG_BED_SECONDS
        from video.render_video import ends_on_card

        self.assertFalse(ends_on_card(LONG_BED_SECONDS))
        self.assertTrue(ends_on_card(LONG_BED_SECONDS + 1))


# ---- #1599: a marquee competitor breakout first ----------------------------------------------------


def _snapshot(ratio_views, hours_before_sync, title="Topuria calls out Makhachev after UFC 333"):
    synced = datetime(2026, 11, 5, 11, tzinfo=UTC)
    videos = [{"title": f"UFC filler video {i}", "views": 10_000, "video_id": f"v{i}",
               "published_at": (synced - timedelta(days=3 + i)).isoformat()} for i in range(7)]  # fmt: skip
    videos.append({"title": title, "views": ratio_views, "video_id": "hot",
                   "published_at": (synced - timedelta(hours=hours_before_sync)).isoformat()})  # fmt: skip
    return {"synced_at": synced.isoformat(),
            "competitors": [{"label": "THE MMA GURU", "recent_videos": videos}]}  # fmt: skip


class OutlierTests(unittest.TestCase):
    def _cands(self, snapshot):
        with (
            patch("analytics.competitor_context.load_competitor_snapshot", return_value=snapshot),
            patch("apis.topic_scorer.infer_topic_domain", return_value="ufc"),
        ):
            return core.best_bet._competitor_outlier_candidates(
                "tapin", allowed={"ufc"}, exclude=set(), seen_local=set()
            )

    def test_five_times_its_median_within_48_hours_is_marked_and_nothing_else(self):
        hot = [c for c in self._cands(_snapshot(60_000, 10)) if "Topuria" in c["topic"]]
        self.assertEqual(hot[0].get("outlier"), 6.0)

        def marked(snapshot):
            return [c for c in self._cands(snapshot) if c.get("outlier")]

        self.assertEqual(marked(_snapshot(40_000, 10)), [])  # 4x: in the pool, not first
        self.assertEqual(marked(_snapshot(60_000, 60)), [])  # 60 hours before the sync

    def test_the_mark_survives_the_story_merge(self):
        when = datetime(2026, 11, 5, 9, tzinfo=UTC)
        pool = [
            {"topic": "Topuria calls out Makhachev for UFC 335", "source": "ESPN MMA",
             "published": when, "domain": "ufc"},
            {"topic": "Topuria calls out Makhachev after UFC 333", "source": "THE MMA GURU",
             "published": when, "domain": "ufc", "outlier": 6.0},
        ]  # fmt: skip
        ranked = core.best_bet.rank_by_coverage(pool, now=when + timedelta(hours=1))
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].get("outlier"), 6.0)

    def test_a_lead_is_kept_past_the_twelve_and_offered_first(self):
        ranked = [{"topic": f"Big story {i} about the Bills", "domain": "nfl",
                   "outlets": ["a", "b", "c"]} for i in range(12)]  # fmt: skip
        ranked += [{"topic": "Topuria calls out Makhachev", "domain": "ufc", "outlier": 6.0},
                   {"topic": "Pereira calls out Ankalaev", "domain": "ufc", "outlier": 7.0},
                   {"topic": "Mahomes ruled out with a torn ACL", "domain": "nfl"}]  # fmt: skip
        kept = core.best_bet._keep_leads(ranked, 12, MARQUEE)
        self.assertEqual([c["topic"] for c in kept[12:]],
                         ["Topuria calls out Makhachev", "Mahomes ruled out with a torn ACL"])  # fmt: skip
        from tests.test_idea_menu import _menu

        fresh = [{"topic": "Raul Rosas Jr. makes RAF debut", "domain": "ufc", "source": "MMA Fighting"},
                 {"topic": "Topuria calls out Makhachev", "domain": "ufc", "source": "THE MMA GURU",
                  "outlier": 6.0},
                 {"topic": "Packers sign a new kicker", "domain": "nfl", "source": "ESPN"}]  # fmt: skip
        topics = [b.topic for b in _menu(fresh=fresh)[0]]
        self.assertIn("Topuria calls out Makhachev", topics)
        if "Raul Rosas Jr. makes RAF debut" in topics:
            self.assertLess(topics.index("Topuria calls out Makhachev"),
                            topics.index("Raul Rosas Jr. makes RAF debut"))  # fmt: skip

    def test_a_marquee_outlier_leads_the_night(self):
        ideas = [_bet("Chiefs look for answers at receiver"),
                 _bet("Topuria calls out Makhachev", domain="ufc", outlets=1, outlier=6.0),
                 _bet("Pereira calls out Ankalaev", domain="ufc", outlets=1, outlier=7.0)]  # fmt: skip
        with (
            patch("core.best_bet.marquee_names", return_value=MARQUEE),
            patch("core.series.dated.launch_names", return_value=[]),
        ):
            led = core.batch_generation.lead_first(ideas, "tapin", now=NOW, week=[])
        # Pereira is not on the marquee list - a breakout of a name the channel does not lead with
        self.assertEqual(led[0].topic, "Topuria calls out Makhachev")


# ---- #1613: marquee injury news first ------------------------------------------------------------------


class InjuryTests(unittest.TestCase):
    def test_an_injury_story_names_a_marquee_player(self):
        from core.best_bet import injury_story

        self.assertTrue(injury_story("Mahomes ruled out for the season with a torn ACL", MARQUEE))
        self.assertTrue(injury_story("Chiefs place Mahomes on IR after ankle surgery", MARQUEE))
        self.assertFalse(injury_story("Mahomes throws four touchdowns in a rout", MARQUEE))
        self.assertFalse(injury_story("Bills tackle ruled out with a knee injury", MARQUEE))
        self.assertFalse(injury_story("Mahomes' grandfather dies after a fall", MARQUEE))  # dec. 97

    def test_it_leads_over_a_breakout(self):
        ideas = [_bet("Topuria calls out Makhachev", domain="ufc", outlier=6.0),
                 _bet("Mahomes ruled out with a torn ACL")]  # fmt: skip
        with (
            patch("core.best_bet.marquee_names", return_value=MARQUEE),
            patch("core.series.dated.launch_names", return_value=[]),
        ):
            led = core.batch_generation.lead_first(ideas, "tapin", now=NOW, week=[])
        self.assertEqual(led[0].topic, "Mahomes ruled out with a torn ACL")

    def test_the_fast_lane_takes_it_at_three_outlets_within_the_hour(self):
        lane = _lane()

        def story(pool):
            with (
                patch("core.best_bet.marquee_names", return_value=MARQUEE),
                patch.object(lane, "_drafted", return_value=False),
                patch.object(lane, "result_story", return_value=None),
            ):
                return lane.next_story("tapin", now=NOW, store={}, pool=lambda _c: pool, week=[])

        found = story([_cand("Mahomes ruled out with a torn ACL", 3, 30, "nfl")])
        self.assertEqual(found["kind"], "injury")
        self.assertIsNone(story([_cand("Mahomes ruled out with a torn ACL", 2, 30, "nfl")]))
        self.assertIsNone(story([_cand("Mahomes ruled out with a torn ACL", 3, 90, "nfl")]))


# ---- #1612: a numbered card's fight week first --------------------------------------------------


class FightWeekTests(unittest.TestCase):
    def test_the_card_names_its_main_event(self):
        from core.series.recap import card_names

        self.assertEqual(card_names("UFC 334: Gane vs. Hokit"), ["UFC 334", "Gane", "Hokit"])
        self.assertEqual(card_names("UFC Fight Night: Moicano vs. Nolan"), [])

    def test_the_week_before_a_numbered_card(self):
        from core.series.recap import fight_week

        with patch.dict(os.environ, {"UFC_FIGHT_WEEK": "true"}):
            week = fight_week(now=NOW, board=BOARD)
            early = fight_week(now=datetime(2026, 11, 7, 11, tzinfo=UTC), board=BOARD)
            after = fight_week(now=datetime(2026, 11, 15, 6, tzinfo=UTC), board=BOARD)
        self.assertEqual(week, ["UFC 334", "Gane", "Hokit"])
        self.assertEqual(early, [])  # eight days out; the Fight Night that week is no card of note
        self.assertEqual(after, [])  # it has started

    def test_a_fight_week_story_leads_the_night(self):
        ideas = [_bet("Chiefs look for answers at receiver"),
                 _bet("Hokit says Gane has never faced his power", domain="ufc", outlets=2)]  # fmt: skip
        with (
            patch("core.best_bet.marquee_names", return_value=MARQUEE),
            patch("core.series.dated.launch_names", return_value=[]),
        ):
            led = core.batch_generation.lead_first(
                ideas, "tapin", now=NOW, week=["UFC 334", "Gane", "Hokit"]
            )
        self.assertEqual(led[0].topic, "Hokit says Gane has never faced his power")

    def test_the_night_is_led_by_it(self):
        ideas = [_bet("Chiefs look for answers at receiver"),
                 _bet("Hokit says Gane has never faced his power", domain="ufc", outlets=3)]  # fmt: skip
        with (
            patch("core.best_bet.get_idea_menu", return_value=(ideas, [])),
            patch("core.best_bet.marquee_names", return_value=[]),
            patch("core.series.countdown.countdown_idea", return_value=None),
            patch("core.series.recap.recap_ideas", return_value=[]),
            patch("core.series.recap.matchup_ideas", return_value=[], create=True),
            patch("core.series.recap.fight_week", return_value=["UFC 334", "Gane", "Hokit"],
                  create=True),
            patch("core.batch_generation.long_breakout_ideas", return_value=[]),
            patch("core.batch_generation.night_gaming_share"),
            patch("core.batch_generation._swap_holdouts", return_value=set()),
            patch("core.batch_generation._with_follow_up", side_effect=lambda _c, t, *_a: t),
            patch("core.series.dated.launch_names", return_value=[]),
        ):  # fmt: skip
            topics = core.batch_generation.collect_topics("tapin", count=1)
        self.assertEqual(topics, ["Hokit says Gane has never faced his power"])


# ---- #1874 + #1890: fight-week drama and press conferences through the fast lane -----------------


class QuickLaneTests(unittest.TestCase):
    def _story(self, pool, week=(), store=None):
        lane = _lane()
        with (
            patch("core.best_bet.marquee_names", return_value=MARQUEE),
            patch.object(lane, "_drafted", return_value=False),
            patch.object(lane, "result_story", return_value=None),
        ):
            return lane.next_story(
                "tapin", now=NOW, store=store or {}, pool=lambda _c: pool, week=list(week)
            )

    def test_a_weigh_in_miss_in_fight_week(self):
        pool = [_cand("Hokit misses weight ahead of UFC 334 main event", 3, 20)]
        found = self._story(pool, week=["UFC 334", "Gane", "Hokit"])
        self.assertEqual(found["kind"], "fight_week")
        self.assertIsNone(self._story(pool))  # not fight week
        self.assertIsNone(self._story([_cand("Gane vs Hokit odds and picks", 3, 20)],
                                      week=["UFC 334", "Gane", "Hokit"]))  # fmt: skip

    def test_a_press_conference_quote(self):
        found = self._story(
            [_cand("Dana White fires back at Jon Jones at press conference", 3, 30)]
        )
        self.assertEqual(found["kind"], "presser")
        self.assertIsNone(self._story([_cand("Mahomes says the Chiefs must start faster", 3, 30,
                                             "nfl")]))  # fmt: skip
        self.assertIsNone(self._story([_cand("Coach blasts referees at press conference", 3, 30,
                                             "nfl")]))  # not a marquee name  # fmt: skip

    def test_they_count_toward_the_news_cap(self):
        day = _lane()._day("tapin", NOW)
        store = {"days": {day: {"injury": 1, "presser": 1}}}
        pool = [_cand("Dana White fires back at Jon Jones at press conference", 3, 30)]
        self.assertIsNone(self._story(pool, store=store))


# ---- #1597: the marquee list learns ----------------------------------------------------------------


def _short(run_id, subject, views, days_ago, title=None):
    return {"run_id": run_id, "subject": subject, "views": views, "title": title or subject,
            "when": NOW - timedelta(days=days_ago), "domain": "ufc"}  # fmt: skip


class MarqueeLearnsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="w152_marquee_")
        self.path = os.path.join(self.tmp, "marquee_learned_tapin.json")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmp, True)

    def _shorts(self):
        rows = [_short(i, "Filler", 40, 30 - i) for i in range(10)]  # the median is 40
        rows += [_short(20, "Real Madrid", 300, 9, "Real Madrid stun Liverpool"),
                 _short(21, "Real Madrid", 220, 3, "Real Madrid's new No. 9")]  # fmt: skip
        rows += [_short(30 + i, "Holloway", 10, 12 - i, f"Holloway story {i}") for i in range(3)]
        rows += [_short(40 + i, "GTA 6", 12, 6 - i, f"GTA 6: {i} days to launch") for i in range(3)]
        return rows

    def test_a_subject_that_beat_the_median_twice_joins_and_one_that_missed_three_leaves(self):
        from core.series.worked import learn_marquee

        learned = learn_marquee("tapin", now=NOW, shorts=self._shorts(),
                                listed=["Holloway", "GTA 6", "Topuria"], keep=["GTA 6"])  # fmt: skip
        self.assertEqual(sorted(learned["joined"]), ["Real Madrid"])
        self.assertEqual(sorted(learned["left"]), ["Holloway"])  # GTA 6 has a series row

    def test_the_names_merge_the_learned_list(self):
        from core.series import worked

        Path(self.path).write_text(json.dumps({"joined": {"Real Madrid": [20, 21]},
                                               "left": {"Holloway": [30, 31, 32]}}),
                                   encoding="utf-8")  # fmt: skip
        with patch.object(worked, "learned_path", return_value=self.path):
            names = core.best_bet.marquee_names("tapin")
        self.assertIn("Real Madrid", names)
        self.assertNotIn("Holloway", names)
        self.assertIn("Topuria", names)  # the operator's list stays

    def test_overnight_refreshes_it_and_says_who_moved(self):
        from core.series import worked

        with (
            patch.dict(os.environ, {"MARQUEE_LEARN": "true"}),
            patch.object(worked, "learned_path", return_value=self.path),
            patch.object(worked, "_measured_shorts", return_value=self._shorts()),
            patch.object(worked, "_series_names", return_value=["GTA 6"]),
            patch("core.best_bet._configured_marquee", return_value=["Holloway", "GTA 6"]),
        ):
            line = worked.refresh_marquee("tapin", now=NOW)
        self.assertIn("Real Madrid", line)
        self.assertIn("Holloway", line)
        self.assertTrue(os.path.exists(self.path))


# ---- #1648: three Shorts a day for two weeks ----------------------------------------------------------


TRIAL = {"id": "three-a-day", "kind": "slots", "all": True, "subject": "three Shorts a day",
         "from": "2026-11-07", "to": "2026-11-20", "extra_hours": [18], "renders": 3}  # fmt: skip


class ThreeADayTests(unittest.TestCase):
    def test_every_title_gets_the_evening_inside_the_window(self):
        with patch("core.series.dated.series_rows", return_value=[TRIAL]):
            inside = core.series.dated.slot_hours("tapin", "Chiefs beat Bills", "2026-11-10")
            after = core.series.dated.slot_hours("tapin", "Chiefs beat Bills", "2026-11-21")
            names = core.series.dated.launch_names("tapin", "2026-11-10")
        self.assertEqual(inside, (12, 18, 22))
        self.assertEqual(after, (12, 22))
        self.assertEqual(names, [])  # the trial names no story to jump the queue

    def test_overnight_renders_for_the_third_slot(self):
        from core.series.dated import slot_renders

        with patch("core.series.dated.series_rows", return_value=[TRIAL]):
            self.assertEqual(slot_renders("tapin", "2026-11-10"), 3)
            self.assertEqual(slot_renders("tapin", "2026-11-21"), 0)
        with (
            patch.object(core.batch_review, "unattended_limit", return_value=2),
            patch.object(core.batch_review, "coming_day_empty", return_value=False),
            patch("core.series.dated.slot_renders", return_value=3),
        ):
            self.assertEqual(core.batch_review.overnight_render_limit("tapin")[0], 3)

    def test_the_trial_is_in_the_calendar(self):
        rows = json.loads(Path("config/series.json").read_text(encoding="utf-8"))["tapin"]
        trial = next(r for r in rows if r.get("id") == "three-a-day")
        self.assertTrue(trial["all"])
        self.assertEqual((trial["from"], trial["to"]), ("2026-11-07", "2026-11-20"))

    def test_the_trial_is_measured_against_the_two_weeks_before(self):
        from core.success.cadence import cadence_lines

        def row(run_id, day, views):
            when = datetime(2026, 11, day, 18, tzinfo=UTC) if day > 0 else datetime(
                2026, 10, 31 + day, 18, tzinfo=UTC)  # fmt: skip
            series = [[(when + timedelta(days=d)).date().isoformat(), views] for d in range(8)]
            return SimpleNamespace(content_run_id=run_id, published_at=when,
                                   privacy_status="public", metrics_json=json.dumps(
                                       {"daily_views": series}), is_seeded=False)  # fmt: skip

        rows = [row(1, -5, 20), row(2, -3, 20), row(3, 7, 30), row(4, 7, 30), row(5, 8, 30)]
        lines = cadence_lines("tapin", today=datetime(2026, 11, 20).date(), rows=rows,
                              trials=[TRIAL], is_long=lambda _run_id: False)  # fmt: skip
        text = "\n".join(lines)
        self.assertIn("Three Shorts a day", text)
        self.assertIn("the 14 days before", text)
        self.assertIn("per Short", text)


# ---- #1653: five drafts a night when five pass the gate -----------------------------------------


class FiveDraftsTests(unittest.TestCase):
    def _topics(self, n, wide):
        ideas = [_bet(f"Story number {i} about the Chiefs") for i in range(n)]
        with (
            patch("core.best_bet.get_idea_menu", return_value=(ideas, [])),
            patch("core.best_bet.marquee_names", return_value=[]),
            patch("core.series.countdown.countdown_idea", return_value=None),
            patch("core.series.recap.recap_ideas", return_value=[]),
            patch("core.series.recap.matchup_ideas", return_value=[], create=True),
            patch("core.batch_generation.long_breakout_ideas", return_value=[]),
            patch("core.batch_generation.night_gaming_share"),
            patch("core.batch_generation._swap_holdouts", return_value=set()),
            patch("core.batch_generation._with_follow_up", side_effect=lambda _c, t, *_a: t),
            patch("core.series.dated.launch_names", return_value=[]),
        ):
            gate: dict = {}
            topics = core.batch_generation.collect_topics("tapin", count=3, wide=wide, gate=gate)
        return topics, gate

    def test_five_when_five_pass_three_otherwise(self):
        topics, gate = self._topics(6, 5)
        self.assertEqual(len(topics), 5)
        self.assertEqual(gate["passed"], 6)
        self.assertEqual(len(self._topics(4, 5)[0]), 3)
        self.assertEqual(len(self._topics(6, 0)[0]), 3)  # a run that asks no wider night

    def test_overnight_asks_for_five_only_when_nothing_cut_tonight(self):
        from core.overnight import night_wide

        self.assertEqual(night_wide(waiting=0, requested=3, want=3), 5)
        self.assertEqual(night_wide(waiting=5, requested=3, want=3), 3)  # the cap of 8
        self.assertEqual(night_wide(waiting=0, requested=3, want=2), 0)  # the quota cut it


# ---- #1892: a numbered card's main event as a 6-8 minute match-up --------------------------------


def _event():
    def side(name, record):
        return {"athlete": {"displayName": name}, "records": [{"summary": record}]}

    bout = {"type": {"abbreviation": "Heavyweight"}, "format": {"regulation": {"periods": 5}},
            "competitors": [side("Ciryl Gane", "13-2-0"), side("Josh Hokit", "9-1-0")],
            "status": {"type": {"completed": False}}}  # fmt: skip
    return {"name": "UFC 334: Gane vs. Hokit", "competitions": [bout]}


class MatchupTests(unittest.TestCase):
    def _ideas(self, now, drafted=False):
        from core.series.recap import matchup_ideas

        with (
            patch.dict(os.environ, {"UFC_MATCHUP": "true"}),
            patch("core.batch_generation.series_drafted", return_value=drafted),
        ):
            return matchup_ideas("tapin", now=now, board=BOARD,
                                 fetch=lambda _league, dates="": {"events": [_event()]},
                                 headlines=lambda *_a: [])  # fmt: skip

    def test_drafted_two_to_five_days_before_the_card(self):
        ideas = self._ideas(NOW)
        self.assertEqual(len(ideas), 1)
        idea = ideas[0]
        self.assertEqual(idea.topic, "UFC 334: Gane vs. Hokit - how they match up")
        self.assertEqual(idea.draft_kind, "long")
        facts = " ".join(idea.facts)
        self.assertIn("Saturday, November 14", facts)
        self.assertIn("13-2-0", facts)
        self.assertIn("five rounds", facts)

    def test_not_too_early_not_too_late_not_twice(self):
        self.assertEqual(self._ideas(datetime(2026, 11, 9, 11, tzinfo=UTC)), [])
        self.assertEqual(self._ideas(datetime(2026, 11, 13, 11, tzinfo=UTC)), [])
        self.assertEqual(self._ideas(NOW, drafted=True), [])

    def test_it_runs_six_to_eight_minutes(self):
        from core.script_length import WORDS_PER_SECOND
        from core.series.long_form import long_format, long_word_range

        topic = "UFC 334: Gane vs. Hokit - how they match up"
        self.assertEqual(long_format(topic), "matchup")
        low, high = long_word_range(topic, 30)
        self.assertLessEqual(high, round(8 * 60 * WORDS_PER_SECOND))
        self.assertGreaterEqual(low, round(4 * 60 * WORDS_PER_SECOND))

    def test_the_night_drafts_it(self):
        idea = _bet("UFC 334: Gane vs. Hokit - how they match up", domain="ufc", source="long")
        with (
            patch("core.series.countdown.countdown_idea", return_value=None),
            patch("core.series.dated.dated_ideas", return_value=[]),
            patch("core.series.recap.recap_ideas", return_value=[]),
            patch("core.series.recap.matchup_ideas", return_value=[idea], create=True),
            patch("core.batch_generation.long_breakout_ideas", return_value=[]),
        ):
            topics = core.batch_generation.collect_topics("tapin", count=0)
        self.assertEqual(topics, ["UFC 334: Gane vs. Hokit - how they match up"])


if __name__ == "__main__":
    unittest.main()
