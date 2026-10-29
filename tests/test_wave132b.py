"""Wave 132, the next five (2026-10-28) - decision 81's topics and the GTA 6 window.

#1595 an overnight story needs 3+ outlets or a marquee name; #1593 at most one preview a night,
marquee only; #1594 a headline draft leads with the story and why fans care; #1847 "GTA 6: N days
to launch", a daily countdown (the operator: the stem then the day's story, an extra fourth draft);
#1592 the Week in Review - every topic, then the top 3 in full, 5-8 minutes (rundown first).
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch


def _bet(topic, source="trending", *, outlets=0, kind="", **extra):
    from core.best_bet import BestBetResult

    return BestBetResult(topic=topic, domain="nfl", avg_engaged_rate=0.0, source=source,
                         supporting_runs=0, rationale="why", outlets=outlets, kind=kind,
                         **extra)  # fmt: skip


# The brief's table: tonight's ideas (10-25) and their outlets.
GATE_IDEAS = [
    ("Justin Gaethje gets told Alexander Volkanovski's fight IQ would be 'too much' for him after "
     "UFC 333", 4),
    ("Call Of Duty: Modern Warfare 4's First DLC Is Out Now, Honors A Real Soldier Who Sustained "
     "Gruesome Injuries", 5),
    ("Luka Doncic Scores 52 In Win At Jazz", 2),
    ("Sunday Night Football: Jaxon Smith-Njigba, Seahawks defense dominate Chiefs, win 20-3", 4),
    ("Pokemon's Snorlax and Bewear body pillows designed by sleep therapist signal positive outlook",
     1),
]  # fmt: skip


class TopicGateTests(unittest.TestCase):
    """#1595: one-outlet stories drafted on thin days - Pokémon body pillows 2 views, Star Wars
    Zero Company 11, Larissa Pacheco 16."""

    def test_the_marquee_list_is_the_channels(self):
        from core.batch_generation import story_passes_gate
        from core.best_bet import marquee_names

        names = marquee_names("tapin")
        for name in ("GTA 6", "Luka Doncic", "Mahomes", "Topuria", "Marvel Rivals"):
            self.assertIn(name, names)
        self.assertNotIn("Jason", names)  # would pass a one-outlet Jason Kelce story
        gate = {"source": "trending", "outlets": 1, "names": names}
        self.assertTrue(story_passes_gate("GTA 6 trailer 3 date leaks", **gate))
        self.assertFalse(story_passes_gate("Pokemon's Snorlax body pillows", **gate))
        self.assertEqual(marquee_names("no-such-channel"), [])

    def test_the_briefs_table_holds(self):
        from core.batch_generation import story_passes_gate
        from core.best_bet import marquee_names

        names = marquee_names("tapin")
        got = [story_passes_gate(t, source="trending", outlets=n, names=names)
               for t, n in GATE_IDEAS]  # fmt: skip
        self.assertEqual(got, [True, True, True, True, False])

    def test_only_a_headline_is_gated(self):
        from core.batch_generation import story_passes_gate

        for source in ("analytics", "series", "countdown", "calendar", "mailbag", "arc"):
            self.assertTrue(story_passes_gate("A small thing", source=source, outlets=0, names=[]))

    def test_overnight_holds_the_small_story_back_and_says_so(self):
        from core import batch_generation as bg

        ideas = [_bet(t, outlets=n) for t, n in GATE_IDEAS]
        held: list[str] = []
        with patch("core.best_bet.get_idea_menu", return_value=(ideas, [])):
            topics = bg.collect_topics("tapin", count=5, held_back=held)
        self.assertEqual(len(topics), 4)  # a thin night drafts fewer - no padding
        self.assertNotIn(GATE_IDEAS[4][0], topics)
        self.assertEqual(held, [GATE_IDEAS[4][0]])
        line = bg.topic_gate_line(held)
        self.assertIn("held back 1 story", line)
        self.assertIn("#1595", line)
        self.assertEqual(bg.topic_gate_line([]), "")

    def test_the_gate_line_reaches_the_overnight_report(self):
        from core.overnight import OvernightResult, render_overnight

        result = OvernightResult(channel_id="tapin", requested=1, drafted=1,
                                 gate_line="The topic gate held back 2 stories")  # fmt: skip
        self.assertIn("The topic gate held back 2 stories", render_overnight(result))

    def test_a_trending_idea_carries_its_outlet_count(self):
        import inspect

        from core import best_bet

        self.assertIn('outlets=len(c.get("outlets") or [])', inspect.getsource(best_bet))


def _board_previews(previews=8):
    from tests.test_idea_menu import FRESH, _menu

    return _menu(fresh=FRESH, previews=previews)[1]


class OnePreviewTests(unittest.TestCase):
    """#1593: 11 previews went public, median 48 organic views against the stories' 63; a 1 PM CBS
    Bengals-Ravens game came in on "a team you made videos about" (run 193)."""

    def test_each_preview_says_what_kind_it_is(self):
        kinds = {b.topic: b.kind for b in _board_previews()}
        self.assertEqual(kinds["Dallas Cowboys at Green Bay Packers"], "national")  # NBC
        self.assertEqual(kinds["Denver Nuggets at Los Angeles Lakers"], "national")  # ESPN
        self.assertEqual(kinds["UFC 335: Nickal vs. Pyfer"], "ufc_numbered")
        self.assertEqual(kinds["Ballon d'Or 2026"], "award")
        self.assertEqual(kinds["New Orleans Saints at New York Giants"], "other")  # Fox

    def test_the_marquee_reason_is_one_rule(self):
        from core.best_bet import marquee_reason

        nbc = {"league": "nfl", "broadcasts": ["NBC"], "notes": []}
        london = {"league": "nfl", "broadcasts": ["Fox"], "notes": ["NFL London Games"]}
        cbs = {"league": "nfl", "broadcasts": ["CBS"], "notes": []}
        bengals = "Cincinnati Bengals at Baltimore Ravens"
        self.assertEqual(marquee_reason(bengals, nbc, set()), ("national", "NBC"))
        self.assertEqual(marquee_reason(bengals, london, set()), ("league", "NFL London Games"))
        self.assertEqual(marquee_reason(bengals, cbs, {"Cincinnati Bengals"})[0], "team")
        self.assertEqual(marquee_reason(bengals, cbs, set()), ("", ""))

    def test_a_ufc_card_is_numbered_or_a_fight_night(self):
        from core.best_bet import card_kind

        self.assertEqual(card_kind("UFC 334: Topuria vs. Holloway"), "ufc_numbered")
        self.assertEqual(card_kind("UFC Fight Night: Bonfim vs. Brady"), "ufc")

    def test_three_slots_take_two_ideas_and_cowboys_eagles(self):
        from core import batch_generation as bg

        ideas = [_bet(f"idea {i}", outlets=4) for i in range(5)]
        previews = [
            _bet("Dallas Cowboys at Philadelphia Eagles", "schedule", kind="national"),
            _bet("UFC Fight Night: Bonfim vs. Brady", "schedule", kind="ufc"),
            _bet("Ballon d'Or 2026", "schedule", kind="award"),
            _bet("UFC Fight Night: Moicano vs. Nolan", "schedule", kind="ufc"),
            _bet("Cincinnati Bengals at Baltimore Ravens", "schedule", kind="team"),
        ]
        with patch("core.best_bet.get_idea_menu", return_value=(ideas, previews)):
            topics = bg.collect_topics("tapin", count=3)
        self.assertEqual(topics, ["idea 0", "Dallas Cowboys at Philadelphia Eagles", "idea 1"])

    def test_with_no_qualifying_preview_the_slot_is_an_idea(self):
        from core import batch_generation as bg

        ideas = [_bet(f"idea {i}", outlets=4) for i in range(5)]
        previews = [_bet("UFC Fight Night: Bonfim vs. Brady", "schedule", kind="ufc"),
                    _bet("Cincinnati Bengals at Baltimore Ravens", "schedule", kind="team")]  # fmt: skip
        with patch("core.best_bet.get_idea_menu", return_value=(ideas, previews)):
            topics = bg.collect_topics("tapin", count=3)
        self.assertEqual(topics, ["idea 0", "idea 1", "idea 2"])

    def test_the_qualifying_kinds(self):
        from core.batch_generation import preview_qualifies

        self.assertEqual([k for k in ("national", "league", "team", "ufc_numbered", "ufc",
                                      "award", "other", "") if preview_qualifies(k)],
                         ["national", "league", "ufc_numbered"])  # fmt: skip


SNF = "Sunday Night Football: Jaxon Smith-Njigba, Seahawks defense dominate Chiefs, win 20-3"
SNF_ANGLES = [
    "Jaxon Smith-Njigba's breakout game shifts Seahawks WR timeline",
    "Seahawks defense sets tone early against Chiefs offensive struggles",
    "What this win means for Seattle's playoff push moving forward",
    "Smith-Njigba's chemistry with Geno opens new dimension in passing game",
    "How Kansas City adjusts after Sunday Night Football setback",
]
CLASICO = ("Real Madrid finally show their potential under Jose Mourinho in convincing El Clasico "
           "win over Barcelona")  # fmt: skip
CLASICO_ANGLES = [
    "Real Madrid's defensive structure clicks under Mourinho in El Clasico statement",
    "How Real Madrid's midfield control neutralized Barcelona's pressing in El Clasico",
    "What Mourinho's tactical shift means for Real Madrid's Champions League ceiling",
    "The human toll: Real Madrid players speak on Mourinho's trust after El Clasico",
    "Breaking down the set-piece adjustments that won Real Madrid the El Clasico",
]


class NewsAngleTests(unittest.TestCase):
    """#1594: the default frames and the ranker's weight on numbers turned big stories into "How
    Cincinnati's tempo keeps Baltimore's young QB off balance" (193); the best-watched Shorts told
    the story itself."""

    def _order(self, angles, seed, intent):
        from core.angle_ranker import rank_angles

        scores = rank_angles(angles, seed_topic=seed, llm_judge=False, intent=intent)
        return sorted(angles, key=lambda a: -scores[a])

    def test_the_story_ranks_first_under_news(self):
        self.assertEqual(self._order(SNF_ANGLES, SNF, "news")[0], SNF_ANGLES[1])

    def test_the_mechanics_angles_rank_last_under_news(self):
        order = self._order(CLASICO_ANGLES, CLASICO, "news")
        self.assertEqual(set(order[-2:]), {CLASICO_ANGLES[1], CLASICO_ANGLES[4]})

    def test_the_old_ranking_stands_for_other_intents(self):
        # The control: today's ranking had SNF's story angle last.
        self.assertEqual(self._order(SNF_ANGLES, SNF, "")[-1], SNF_ANGLES[1])

    def test_news_is_an_intent_with_its_frames(self):
        from apis.topic_variants import _LENS_EXAMPLES, INTENT_ANGLES
        from core.angle_intent import (
            ALL_INTENTS,
            ANGLE_NEWS,
            BEATS,
            CALM_INTENTS,
            MODE_KEYS,
            stance_rule,
        )

        self.assertIn(ANGLE_NEWS, ALL_INTENTS)
        self.assertIn(ANGLE_NEWS, CALM_INTENTS)
        self.assertEqual(INTENT_ANGLES[ANGLE_NEWS], ["the_story_itself", "why_fans_care",
                         "the_reaction", "what_happens_next", "the_stakes"])  # fmt: skip
        self.assertIn(ANGLE_NEWS, _LENS_EXAMPLES)
        self.assertIn("fans", BEATS[ANGLE_NEWS])
        self.assertEqual(MODE_KEYS["s"][0], ANGLE_NEWS)
        self.assertIn("not a take", stance_rule(ANGLE_NEWS).lower())

    def test_the_angle_prompt_carries_the_news_frames(self):
        from apis import topic_variants

        seen: dict = {}

        def fake(topic, frames, **kwargs):
            seen["frames"] = list(frames)
            return []

        with patch.object(topic_variants, "generate_ai_titles", side_effect=fake):
            topic_variants.generate_variants(SNF, channel_id="tapin", intent="news")
        self.assertEqual(seen["frames"][0], "the_story_itself")
        self.assertNotIn("underrated_angle", seen["frames"])

    def test_the_script_prompt_tells_the_story(self):
        from core.content_engine import _build_prompts

        system, user = _build_prompts(
            topic=SNF, signals={}, min_words=150, max_words=200, today="2026-10-28",
            channel_id="tapin", script_brief="", seo_block="", signal_facts="",
            signal_summary="", brief_block="", length_choice="2", seed_topic=SNF, intent="news",
        )  # fmt: skip
        text = system + user
        self.assertIn("why it matters to the fans", text.lower())
        self.assertNotIn("Explain the mechanism", text)

    def test_a_headline_pick_drafts_as_news(self):
        from core.batch_generation import draft_intent, pick_source

        record = {"offered": [{"topic": SNF, "source": "trending"},
                              {"topic": "Picks, graded", "source": "series"}]}  # fmt: skip
        self.assertEqual(pick_source(SNF, record), "trending")
        self.assertEqual(pick_source("other", record), "")
        self.assertEqual(draft_intent(own_idea=False, preview="", source="trending"), "news")
        self.assertEqual(draft_intent(own_idea=False, preview="", source="series"), "default")
        self.assertEqual(draft_intent(own_idea=False, preview="brief", source="trending"),
                         "preview")  # fmt: skip
        self.assertEqual(draft_intent(own_idea=True, preview="", source="trending"), "")

    def test_an_own_idea_with_no_cue_still_reads_default(self):
        from core.angle_intent import detect_angle_intent

        self.assertEqual(detect_angle_intent("Chargers season so far"), "default")

    def test_the_ranker_hears_the_runs_intent(self):
        import inspect

        from core import pipeline

        source = inspect.getsource(pipeline._editorial_scores)
        self.assertIn("intent=intent", source)


GTA_ROW = {"id": "gta6-countdown", "kind": "countdown", "subject": "GTA 6",
           "names": ["GTA 6", "GTA VI", "Grand Theft Auto VI"],
           "title": "GTA 6: {n} days to launch", "from": "2026-10-29", "until": "2026-11-19",
           "domain": "gaming"}  # fmt: skip


def _at(day: str, hour: int = 15) -> datetime:
    return datetime.fromisoformat(f"{day}T{hour:02d}:00:00+00:00")


class CountdownTests(unittest.TestCase):
    """#1847 (B11.1): a daily countdown Short from 10-29 to 11-18 - one title stem, the GTA
    playlist - modelled on "Picks, graded" (#991)."""

    def _idea(self, day, *, drafted=False, headlines=()):
        from core.series import countdown

        with (
            patch.dict(os.environ, {"SERIES_COUNTDOWN": "true"}),
            patch.object(countdown, "series_rows", return_value=[GTA_ROW]),
            patch("core.batch_generation.series_drafted", return_value=drafted),
            patch.object(countdown, "channel_zone", return_value=timezone.utc),
        ):
            return countdown.countdown_idea("tapin", now=_at(day),
                                            headlines=lambda *_a: list(headlines))  # fmt: skip

    def test_the_four_dates(self):
        self.assertIsNone(self._idea("2026-10-28"))
        self.assertEqual(self._idea("2026-10-29").topic, "GTA 6: 21 days to launch")
        self.assertEqual(self._idea("2026-11-18").topic, "GTA 6: 1 day to launch")
        self.assertIsNone(self._idea("2026-11-19"))  # launch day is #1848's

    def test_once_a_day(self):
        self.assertIsNone(self._idea("2026-10-29", drafted=True))

    def test_the_idea_carries_its_stem_its_deadline_and_its_facts(self):
        when = _at("2026-10-29", 9)
        lines = [
            {"title": "GTA 6 trailer 3 date leaks", "source": "Dexerto", "published": when},
            {"title": "Elden Ring DLC review", "source": "IGN", "published": when},
            {"title": "Grand Theft Auto VI preorders open", "source": "IGN",
             "published": when - timedelta(hours=30)},  # older than a day
        ]  # fmt: skip
        idea = self._idea("2026-10-29", headlines=lines)
        self.assertEqual(idea.source, "countdown")
        self.assertEqual(idea.title_stem, "GTA 6: 21 days to launch")
        self.assertEqual(idea.deadline, "2026-10-30T00:00:00+00:00")
        self.assertEqual(idea.domain, "gaming")
        self.assertIn("November 19, 2026", idea.facts[0])
        self.assertIn("Dexerto reported: GTA 6 trailer 3 date leaks", idea.facts)
        self.assertEqual(len(idea.facts), 2)

    def test_a_day_with_no_headline_still_has_its_date(self):
        idea = self._idea("2026-11-01")
        self.assertEqual(idea.topic, "GTA 6: 18 days to launch")
        self.assertEqual(len(idea.facts), 1)
        self.assertIn("18 days from November 1", idea.facts[0])

    def test_the_suite_keeps_it_off(self):
        from core.series import countdown

        with patch.object(countdown, "series_rows", return_value=[GTA_ROW]):
            self.assertIsNone(countdown.countdown_idea("tapin", now=_at("2026-10-29")))

    def test_the_title_is_the_stem_then_the_story(self):
        from core.series.countdown import series_title

        stem = "GTA 6: 21 days to launch"
        self.assertEqual(series_title(stem, "Trailer 3 leaks a date"),
                         "GTA 6: 21 days to launch - Trailer 3 leaks a date")  # fmt: skip
        self.assertEqual(series_title(stem, "x" * 90), stem)  # over 100 characters
        self.assertEqual(series_title(stem, f"{stem} - already"), f"{stem} - already")
        self.assertEqual(series_title("", "Plain"), "Plain")

    def test_the_topic_rule(self):
        from core.series.countdown import countdown_topic

        args = {"start": "2026-10-29", "until": "2026-11-19"}
        title = GTA_ROW["title"]
        self.assertEqual(
            countdown_topic(title, day="2026-10-30", **args), "GTA 6: 20 days to launch"
        )
        self.assertEqual(countdown_topic(title, day="2026-11-19", **args), "")

    def test_the_menu_leads_with_it_as_an_extra_idea(self):
        from core import best_bet

        countdown = _bet("GTA 6: 21 days to launch", "countdown")
        ideas = [_bet(f"idea {i}", outlets=4) for i in range(5)]
        with (
            patch("core.seasonal_calendar.fetch_week_topics", return_value=[]),
            patch.object(best_bet, "get_best_bets", return_value=list(ideas)),
            patch.object(best_bet, "_series_idea", return_value=None),
            patch("core.series.countdown.countdown_idea", return_value=countdown),
        ):
            got, _previews = best_bet.get_idea_menu("tapin", previews=0)
        self.assertEqual([b.topic for b in got][:2], ["GTA 6: 21 days to launch", "idea 0"])
        self.assertEqual(len(got), 6)

    def test_overnight_drafts_it_as_an_extra_fourth(self):
        from core import batch_generation as bg

        countdown = _bet("GTA 6: 21 days to launch", "countdown", facts=["a fact"],
                         title_stem="GTA 6: 21 days to launch",
                         deadline="2026-10-30T05:00:00+00:00")  # fmt: skip
        ideas = [countdown, *(_bet(f"idea {i}", outlets=4) for i in range(5))]
        picks: dict = {}
        with patch("core.best_bet.get_idea_menu", return_value=(ideas, [])):
            topics = bg.collect_topics("tapin", count=3, picks=picks)
        self.assertEqual(topics, ["GTA 6: 21 days to launch", "idea 0", "idea 1", "idea 2"])
        record = picks["GTA 6: 21 days to launch"]
        self.assertEqual(record["title_stem"], "GTA 6: 21 days to launch")
        self.assertEqual(record["deadline"], "2026-10-30T05:00:00+00:00")
        self.assertEqual(record["facts"], ["a fact"])

    def test_a_full_queue_still_drafts_the_days_countdown(self):
        from core import batch_generation as bg

        countdown = _bet("GTA 6: 21 days to launch", "countdown")
        with (
            patch("core.series.countdown.countdown_idea", return_value=countdown),
            patch("core.best_bet.get_idea_menu") as menu,
        ):
            topics = bg.collect_topics("tapin", count=0)
        self.assertEqual(topics, ["GTA 6: 21 days to launch"])
        menu.assert_not_called()  # no menu, no preview calls, on a night that drafts nothing else

    def test_the_pipeline_puts_the_stem_on_the_title(self):
        import inspect

        from core import pipeline

        self.assertIn('get("title_stem")', inspect.getsource(pipeline.run_pipeline))

    def test_its_day_is_its_deadline(self):
        from core.batch_generation import draft_event_at

        record = {"deadline": "2026-10-30T05:00:00+00:00", "title_stem": "GTA 6: 21 days"}
        self.assertEqual(draft_event_at("", record), "2026-10-30T05:00:00+00:00")
        self.assertEqual(draft_event_at("2026-11-01T17:00Z", record), "2026-11-01T17:00Z")
        self.assertEqual(draft_event_at("", None), "")

    def test_a_late_countdown_says_its_day_has_passed(self):
        from core.batch_review import game_block_reason

        meta = {"event_at": "2026-10-30T05:00:00+00:00", "series": "countdown"}
        now = datetime(2026, 10, 30, 6, tzinfo=timezone.utc)
        self.assertIn("countdown day has passed", game_block_reason(meta, now=now))
        self.assertEqual(game_block_reason(meta, now=now - timedelta(hours=2)), "")

    def test_the_real_config_starts_tomorrow(self):
        from core.series.countdown import series_rows

        rows = series_rows("tapin")
        self.assertEqual([r["id"] for r in rows], ["gta6-countdown"])
        self.assertEqual((rows[0]["from"], rows[0]["until"]), ("2026-10-29", "2026-11-19"))


# The brief's week (10-19 to 10-25): title, organic views, seconds after the offset.
WEEK = [
    ("Modern Warfare 4 campaign praised by Steam players as return to form", 325, 65.3),
    ("Dana White's Post-Fight Reaction to Mike Malott's UFC Edmonton Knockout", 264, 78.9),
    ("Washington vs 49ers preview: San Francisco's 5-0 start faces test", 48, 72.6),
    ("Pokemon's Snorlax and Bewear body pillows designed by sleep therapist", 2, 72.4),
    ("Larissa Pacheco's UFC snub leaves fighter scrambling for new opportunities", 16, 75.3),
    ("Jalen Hurts out for season with blood clots, Eagles' playoff hopes in jeopardy", 63, 72.1),
    ("Fans react to GTA 6 launch trailer with hype and cautious optimism", 305, 68.7),
    ("Star Wars Zero Company's Progression Systems Changed", 11, 74.6),
    ("Coach Conversation: Volkanovski vs Evloev Preview | MMA Analysis", 29, 78.1),
    ("Picks gone wrong: Oct 19 board under fire after 4 of 5 misses", 14, 70.7),
    ("Xbox Game Pass subscribers react to Final Fantasy 7 Remake addition", 7, 64.1),
]
WEEK_NOW = datetime(2026, 10, 26, 10, tzinfo=timezone.utc)


def _week(rows, words=None):
    began = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
    return [{"run_id": 300 + i, "title": t, "path": f"C:/out/run{300 + i}.mp4",
             "published_at": began + timedelta(hours=12 * i), "offset": 0.0, "names": [],
             "views": v, "words": (words or {}).get(i, "")}
            for i, (t, v, _s) in enumerate(rows)]  # fmt: skip


class WeekInReviewTests(unittest.TestCase):
    """#1592 (decision 81): this week's would be 11 whole Shorts, 13:13; the first compilation
    (run 172) has 1 view. The operator: every topic, then a deeper dive on the top 3, 5-8 minutes."""

    def _plan(self, rows, words=None):
        from video import week_compile

        lengths = {f"C:/out/run{300 + i}.mp4": s for i, (_t, _v, s) in enumerate(rows)}
        with (
            patch.object(week_compile, "week_shorts", return_value=_week(rows, words)),
            patch.object(week_compile, "_duration", side_effect=lambda p: lengths.get(p)),
            patch("core.description_extras.ai_disclosure_line", return_value=""),
        ):
            return week_compile.plan_week("tapin", now=WEEK_NOW)

    def test_the_rundown_then_the_top_three_counted_down(self):
        plan = self._plan(WEEK)
        titles = [i["title"] for i in plan.items]
        self.assertEqual(titles[-3:], [WEEK[1][0], WEEK[6][0], WEEK[0][0]])  # 264, 305, 325
        rundown = [t for t, _v, _s in WEEK if t not in titles[-3:]]
        self.assertEqual(titles[:-3], rundown)  # publish order
        self.assertTrue(all(abs(i["seconds"] - 25.0) < 0.01 for i in plan.items[:-3]))
        self.assertEqual([i["seconds"] for i in plan.items[-3:]], [78.9, 68.7, 65.3])
        self.assertTrue(300 <= plan.seconds <= 480)
        self.assertAlmostEqual(plan.seconds, 412.9, places=1)
        self.assertIn("Deep dive #1: " + WEEK[0][0], plan.description)
        self.assertIn("Deep dive #3: " + WEEK[1][0], plan.description)
        self.assertIn("0:25 " + rundown[1], plan.description)
        self.assertTrue(all(i["seconds"] >= 10 for i in plan.items))

    def test_a_rundown_clip_ends_at_a_sentence(self):
        words = [{"word": w, "start": s - 0.3, "end": s} for w, s in
                 (("First.", 9.0), ("second", 15.0), ("ends.", 23.4), ("more", 26.0),
                  ("third.", 31.0))]  # fmt: skip
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.mp3.words.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(words, handle)
            plan = self._plan(WEEK, words={2: path})
        clip = next(i for i in plan.items if i["title"] == WEEK[2][0])
        self.assertLess(abs(clip["seconds"] - 23.7), 0.01)  # 23.4 + the 0.3 s tail
        self.assertEqual(clip["clip"], clip["seconds"])

    def test_the_sentence_cut(self):
        from video.week_compile import sentence_cut

        words = [{"word": "One.", "start": 0, "end": 8.0}, {"word": "two!\"", "start": 9, "end": 19.0},
                 {"word": "three?", "start": 20, "end": 27.0}]  # fmt: skip
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "w.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(words, handle)
            self.assertAlmostEqual(sentence_cut(path, 25.0, 60.0), 27.3)
            self.assertAlmostEqual(sentence_cut(path, 12.0, 60.0), 19.3)  # 8.3 is under 10 s
            self.assertAlmostEqual(sentence_cut(path, 25.0, 22.0), 19.3)  # within the Short
        self.assertEqual(sentence_cut("", 25.0, 60.0), 25.0)  # no sidecar: the target

    def test_a_small_week_grows_its_clips(self):
        plan = self._plan(WEEK[:5])  # deep dives 65.3 + 78.9 + 72.6 = 216.8
        rundown = plan.items[:-3]
        self.assertEqual(len(rundown), 2)
        self.assertTrue(all(25 < i["seconds"] < 72 for i in rundown))  # grown, still a clip
        self.assertAlmostEqual(plan.seconds, 300.0, delta=1.0)
        self.assertEqual(plan.items[-1]["title"], WEEK[0][0])  # #1, the most watched, last

    def test_a_big_week_drops_its_least_watched(self):
        rows = [(f"Short {i}", 100 + i, 60.0) for i in range(40)]  # 37 x 12 s + 180 s is 624 s
        plan = self._plan(rows)
        self.assertLessEqual(plan.seconds, 480.0)
        kept = {i["title"] for i in plan.items}
        self.assertNotIn("Short 0", kept)  # the least watched go first
        self.assertIn("Short 12", kept)
        self.assertEqual(len(plan.items), 28)  # 25 at 12 s and the three deep dives
        self.assertTrue(all(i["seconds"] >= 12.0 - 0.01 for i in plan.items))

    def test_four_shorts_are_still_not_a_week(self):
        self.assertIsNone(self._plan(WEEK[:4]))

    def test_a_clip_is_cut_to_its_length(self):
        from video.week_compile import segment_argv

        argv = segment_argv("C:/in.mp4", "C:/out.mp4", offset=2.0, duration=24.5)
        self.assertEqual(argv[argv.index("-t") + 1], "24.5")
        self.assertNotIn("-t", segment_argv("C:/in.mp4", "C:/out.mp4", offset=2.0))

    def test_the_render_passes_each_clip(self):
        import inspect

        from video import week_compile

        self.assertIn('duration=item.get("clip")', inspect.getsource(week_compile._render))

    def test_a_short_brings_its_words(self):
        import inspect

        from video import week_compile

        self.assertIn(".words.json", inspect.getsource(week_compile.week_shorts))


if __name__ == "__main__":
    unittest.main()
