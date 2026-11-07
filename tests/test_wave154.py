"""Wave 154 (2026-11-06) - the first ten of the operator's "next 20".

#1606 one idea a subject a night; #1607 an idea past 36 hours waits unless 3+ outlets carry it;
#1615 the menu says what the subject earned last time; #1618 the weekly "what worked" note;
#1631 the first sentence under 12 words; #1662 never more than 4 a day, never two within 3 hours;
#1691 + #1698 formats and frames ranked weekly; #1709 the series playlist in a Short's description;
#1802 `ops promotions` suggests nothing - ads stay at $0.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import patch
from zoneinfo import ZoneInfo

# Imported before any patch below (wave 145's reversed-suite failure).
import analytics.promotions
import core.batch_generation
import core.best_bet
import core.content_engine
import core.description_extras
import core.series.worked
import core.spaced_queue
import jobs.fast_lane

UTC = timezone.utc
NOW = datetime(2026, 11, 24, 20, tzinfo=UTC)  # 3 PM ET, past the three-a-day trial
MARQUEE = ["GTA 6", "Chiefs", "Topuria"]


def _bet(topic, *, outlets=3, first="", source="trending", domain="gaming"):
    return core.best_bet.BestBetResult(topic=topic, domain=domain, avg_engaged_rate=0.0,
                                       source=source, supporting_runs=0, rationale="",
                                       outlets=outlets, first=first)  # fmt: skip


def _collect(ideas, *, count=2, held=None, launch=()):
    with (
        patch("core.best_bet.get_idea_menu", return_value=(ideas, [])),
        patch("core.best_bet.marquee_names", return_value=MARQUEE),
        patch("core.series.countdown.countdown_idea", return_value=None),
        patch("core.series.recap.recap_ideas", return_value=[]),
        patch("core.series.recap.matchup_ideas", return_value=[]),
        patch("core.series.last_night.last_night_ideas", return_value=[]),
        patch("core.batch_generation.long_breakout_ideas", return_value=[]),
        patch("core.batch_generation.night_gaming_share"),
        patch("core.batch_generation._swap_holdouts", return_value=set()),
        patch("core.batch_generation._with_follow_up", side_effect=lambda _c, t, *_a: t),
        patch("core.series.dated.launch_names", return_value=list(launch)),
        patch("core.series.recap.fight_week", return_value=[]),
    ):
        return core.batch_generation.collect_topics("tapin", count=count, held_back=held)


# ---- #1606: one idea a subject a night ----------------------------------------------------------


class OneSubjectTests(unittest.TestCase):
    def test_the_second_idea_on_a_subject_waits_for_tomorrow(self):
        held: list[str] = []
        ideas = [_bet("GTA 6 pre-load opens Tuesday"), _bet("GTA 6 map leaks again"),
                 _bet("Chiefs trade for a receiver", domain="nfl")]  # fmt: skip
        self.assertEqual(_collect(ideas, held=held),
                         ["GTA 6 pre-load opens Tuesday", "Chiefs trade for a receiver"])  # fmt: skip
        self.assertIn("GTA 6 map leaks again", held)

    def test_launch_week_keeps_two(self):
        ideas = [_bet("GTA 6 pre-load opens Tuesday"), _bet("GTA 6 map leaks again")]
        self.assertEqual(len(_collect(ideas, launch=["GTA 6"])), 2)


# ---- #1607: an idea past 36 hours waits unless 3+ outlets carry it ---------------------------------


class StaleIdeaTests(unittest.TestCase):
    def test_old_and_thin_waits_old_and_wide_and_fresh_go(self):
        old = (datetime.now(UTC) - timedelta(hours=40)).isoformat()
        fresh = (datetime.now(UTC) - timedelta(hours=5)).isoformat()
        held: list[str] = []
        ideas = [_bet("Topuria answers Makhachev", outlets=1, first=old, domain="ufc"),
                 _bet("GTA 6 pre-load opens Tuesday", outlets=4, first=old),
                 _bet("Chiefs trade for a receiver", outlets=1, first=fresh, domain="nfl")]  # fmt: skip
        topics = _collect(ideas, count=3, held=held)
        self.assertNotIn("Topuria answers Makhachev", topics)
        self.assertIn("Topuria answers Makhachev", held)
        self.assertEqual(
            sorted(topics), ["Chiefs trade for a receiver", "GTA 6 pre-load opens Tuesday"]
        )

    def test_the_menu_keeps_when_the_story_broke(self):
        when = datetime(2026, 11, 5, 9, tzinfo=UTC)
        from tests.test_idea_menu import _menu

        fresh = [{"topic": "Packers sign a new kicker", "domain": "nfl", "source": "ESPN",
                  "published": when, "first": when}]  # fmt: skip
        ideas = _menu(fresh=fresh)[0]
        idea = next(b for b in ideas if b.topic == "Packers sign a new kicker")
        self.assertEqual(idea.first, when.isoformat())


# ---- #1615: what the subject earned last time ------------------------------------------------------


class EarnedTests(unittest.TestCase):
    SHORTS: ClassVar[list[dict]] = [
        {"run_id": 7, "views": 631, "title": "Topuria's jab breaks down Makhachev",
         "subject": "Topuria", "when": NOW - timedelta(days=20)},
        {"run_id": 9, "views": 88, "title": "Topuria books his next fight",
         "subject": "Topuria", "when": NOW - timedelta(days=5)},
    ]  # fmt: skip

    def test_the_last_short_on_the_subject(self):
        from core.best_bet import earned_note

        self.assertEqual(earned_note("Topuria calls out Makhachev", self.SHORTS, MARQUEE),
                         "Topuria: 88 organic views in its first week last time")  # fmt: skip
        self.assertEqual(earned_note("Valve updates Steam", self.SHORTS, MARQUEE), "")

    def test_the_menu_shows_it(self):
        from tests.test_idea_menu import _menu

        fresh = [
            {"topic": "Topuria calls out Makhachev", "domain": "ufc", "source": "MMA Fighting"}
        ]
        with (
            patch("core.best_bet._menu_shorts", return_value=self.SHORTS, create=True),
            patch("core.best_bet.marquee_names", return_value=MARQUEE),
        ):
            ideas = _menu(fresh=fresh)[0]
        idea = next(b for b in ideas if b.topic == "Topuria calls out Makhachev")
        self.assertIn("Topuria: 88 organic views", idea.rationale)


# ---- #1618: the weekly "what worked" note ------------------------------------------------------------


class WhatWorkedTests(unittest.TestCase):
    def test_the_three_best_and_the_three_dead(self):
        from core.series.worked import what_worked_lines

        rows = [("GTA 6", 1091), ("Real Madrid", 91), ("Topuria", 300), ("Steam", 4),
                ("Xbox", 9), ("Roblox", 2), ("Chiefs", 60)]  # fmt: skip
        shorts = [{"run_id": i, "views": v, "subject": s, "title": s, "domain": "x",
                   "when": NOW - timedelta(days=3)} for i, (s, v) in enumerate(rows)]  # fmt: skip
        text = "\n".join(what_worked_lines("tapin", now=NOW, shorts=shorts))
        self.assertIn("GTA 6 1,091", text)
        self.assertLess(text.index("GTA 6"), text.index("Topuria"))
        self.assertIn("dead: Roblox 2", text)
        self.assertIn("leans", text)


# ---- #1631: the first sentence under 12 words -----------------------------------------------------


class ShortHookTests(unittest.TestCase):
    def test_a_long_first_sentence_is_rewritten_under_twelve(self):
        payload = {"openers": [
            "The Chiefs were held to three points in Seattle on Sunday night and nobody saw "
            "it coming at all.",
            "The Chiefs scored 3 points in Seattle.",
        ]}  # fmt: skip
        script = ("Kansas City came into Seattle on Sunday night with the league's best offense and "
                  "left with three points on the board. The line moved twice. The Chiefs host "
                  "Denver next.")  # fmt: skip
        with (
            patch.object(core.content_engine, "_call_content_llm", return_value=payload),
            patch("analytics.hook_learning.regen_guidance", return_value={}),
            patch.object(core.content_engine, "_recent_openers", return_value=[]),
            patch.dict(os.environ, {"HOOK_REGEN_ENABLED": "true"}),
        ):
            new, extra = core.content_engine._hook_variants(script)
        self.assertTrue(new.startswith("The Chiefs scored 3 points in Seattle."), new)
        self.assertTrue(any("words" in p for p in extra.get("problems") or []))
        refused = [v for v in extra["variants"] if "nobody saw" in v["opener"]]
        self.assertIn("words", refused[0].get("refused", ""))


# ---- #1662: never more than 4 a day, never two within 3 hours --------------------------------------


class SpacingTests(unittest.TestCase):
    def test_crowded(self):
        from core.spaced_queue import crowded

        et = ZoneInfo("America/New_York")
        day = [datetime(2026, 11, 25, h, tzinfo=et).astimezone(UTC) for h in (8, 12, 16, 20)]
        self.assertIn("4", crowded(datetime(2026, 11, 25, 23, 30, tzinfo=et), day, "tapin"))
        self.assertIn("3 hours", crowded(datetime(2026, 11, 25, 14, tzinfo=et), day[:2], "tapin"))
        self.assertEqual(crowded(datetime(2026, 11, 25, 19, tzinfo=et), day[:2], "tapin"), "")

    def test_a_slot_two_hours_after_another_moves_to_the_next(self):
        et = ZoneInfo("America/New_York")
        taken = {datetime(2026, 11, 24, 20, 30, tzinfo=et).astimezone(UTC)}
        sq = core.spaced_queue
        with (
            patch.object(sq, "takes_long_slot", return_value=False),
            patch.object(sq, "_window_days", return_value=7.0),
            patch.object(sq, "_age_days", return_value=0.0),
            patch.object(sq, "preview_event", return_value=None),
            patch.object(sq, "_taken_slots", return_value=taken),
            patch.object(sq, "_planned_time", return_value=None),
            patch.object(sq, "_recent_public", return_value=set(), create=True),
            patch.object(sq, "_channel_tz", return_value=et),
        ):
            when, why = sq.slot_for_run("tapin", 300, title="Chiefs trade for a receiver", now=NOW)
        self.assertEqual(why, "")
        self.assertEqual(when, datetime(2026, 11, 25, 12, tzinfo=et).astimezone(UTC))  # not 10 PM

    def test_the_fast_lane_stops_at_four_a_day(self):
        lane = jobs.fast_lane
        with (
            patch.dict(os.environ, {"FAST_LANE": "true"}),
            patch.object(lane, "units_left", return_value=9000),
            patch.object(lane, "on_battery", return_value=False),
            patch.object(lane, "overnight_running", return_value=False),
            patch("core.spaced_queue.day_full", return_value="4 Shorts that day", create=True),
        ):
            self.assertIn("4 Shorts", lane.blocked("tapin", now=NOW, store={}))


# ---- #1691 + #1698: formats and frames ranked weekly -------------------------------------------------


class FormatTests(unittest.TestCase):
    def test_a_runs_format(self):
        from core.success.formats import run_format

        def features(source, intent="news"):
            return {"best_bet": {"offered": [{"topic": "t", "source": source}], "picked": 1},
                    "angle_intent": intent}  # fmt: skip

        self.assertEqual(run_format(features("countdown")), "countdown")
        self.assertEqual(run_format(features("schedule", "preview")), "preview")
        self.assertEqual(run_format(features("result")), "result")
        self.assertEqual(run_format(features("trending", "explainer")), "explainer")
        self.assertEqual(run_format({}), "own idea")

    def test_ranked_by_first_week_views_and_subscribers_per_thousand(self):
        from core.success.formats import format_lines

        when = NOW - timedelta(days=12)
        series = [[(when + timedelta(days=d)).date().isoformat(), v] for d, v in
                  enumerate([100, 50, 20, 10, 5, 5, 10])]  # fmt: skip

        def row(run_id, scale, subs):
            return SimpleNamespace(content_run_id=run_id, published_at=when, privacy_status="public",
                                   metrics_json=json.dumps({"daily_views": [[d, v * scale] for d, v in series],
                                                            "subscribers_gained": subs,
                                                            "lifetime_views": 200 * scale}))  # fmt: skip

        runs = {1: {"best_bet": {"offered": [{"topic": "a", "source": "countdown"}], "picked": 1},
                    "angle": "news"},
                2: {"best_bet": {"offered": [{"topic": "b", "source": "schedule"}], "picked": 1},
                    "angle": "preview"}}  # fmt: skip
        lines = format_lines("tapin", today=NOW.date(), rows=[row(1, 3, 6), row(2, 1, 0)],
                             features=lambda run_id: runs[run_id])  # fmt: skip
        text = "\n".join(lines)
        self.assertLess(text.index("countdown"), text.index("preview"))
        self.assertIn("10.0 subscribers per 1,000", text)  # 6 of 600 organic views
        self.assertIn("By frame", text)


# ---- #1709: the series playlist in a Short's description ----------------------------------------------


class PlaylistLineTests(unittest.TestCase):
    def test_a_short_links_its_series_playlist(self):
        tmp = tempfile.mkdtemp(prefix="w154_pl_")
        store = os.path.join(tmp, "playlists_tapin.json")
        with open(store, "w", encoding="utf-8") as handle:
            json.dump({"ids": {"GTA": "PLFRYN2Iozuwc"}}, handle)
        extras = core.description_extras
        with (
            patch("core.playlists.store_path_for", return_value=store),
            patch("core.playlists.playlists_for", return_value=["GTA", "Gaming"]),
        ):
            short = extras.apply_description_extras("GTA 6 pre-load opens.", "tapin",
                                                    title="GTA 6 pre-load", length_choice="2")  # fmt: skip
            long_ = extras.apply_description_extras("GTA 6 explained.", "tapin",
                                                    title="GTA 6 explained", length_choice="4")  # fmt: skip
        self.assertIn("More GTA: https://www.youtube.com/playlist?list=PLFRYN2Iozuwc", short)
        self.assertNotIn("playlist?list=", long_)


# ---- #1802: ads stay at $0 ----------------------------------------------------------------------------


class PromotionTests(unittest.TestCase):
    def test_nothing_is_suggested(self):
        promotions = analytics.promotions
        picks = {"state": "ready", "picks": [{"title": "Run 191", "video_id": "x", "stayed": 0.6,
                                              "views7": 1091}], "budget": 15.0, "days": 5}  # fmt: skip
        with patch.object(promotions, "candidates", return_value=picks):
            lines = promotions.candidate_lines("tapin")
            line = promotions.candidates_line("tapin")
        self.assertEqual(line, "")
        self.assertIn("decision 82", " ".join(lines))
        self.assertNotIn("Run 191", " ".join(lines))


if __name__ == "__main__":
    unittest.main()
