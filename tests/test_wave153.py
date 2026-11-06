"""Wave 153 (2026-11-06) - the next five, with the preview title run 249 exposed.

#1999 a national final the PC slept through, drafted at overnight; #1877 a marquee player's
40-point night; #1687 a result's next games as its facts; #1623 + #1624 a Short ends on a loop line,
not a sign-off; #1626 the subject in the first three words; #2001 a preview's title says its call
as a call.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

# Imported before any patch below (wave 145's reversed-suite failure).
import core.batch_generation
import core.best_bet
import core.channel_persona
import core.content_engine
import core.script_craft
import core.youtube_meta
import jobs.fast_lane

UTC = timezone.utc
NOW = datetime(2026, 11, 6, 11, tzinfo=UTC)  # 05:00 CST, overnight
MARQUEE = ["Mahomes", "Luka Doncic", "LeBron", "Lakers", "Chiefs"]


def _last_night():
    import core.series.last_night

    return core.series.last_night


def _side(home_away, name, abbr, score, leader=None):
    side = {"homeAway": home_away, "score": str(score),
            "team": {"shortDisplayName": name, "abbreviation": abbr}}  # fmt: skip
    if leader:
        side["leaders"] = [{"name": "points", "leaders": [
            {"value": float(leader[1]), "displayValue": str(leader[1]),
             "athlete": {"displayName": leader[0]}}]}]  # fmt: skip
    return side


def _event(eid, name, start, away, home, tv):
    return {"id": eid, "name": name, "date": start,
            "status": {"type": {"completed": True}},
            "competitions": [{"competitors": [away, home],
                              "broadcasts": [{"names": tv}]}]}  # fmt: skip


TNF = _event("401", "Jacksonville Jaguars at Baltimore Ravens", "2026-11-06T01:15Z",
             _side("away", "Jaguars", "JAX", 17), _side("home", "Ravens", "BAL", 27),
             ["Prime Video"])  # fmt: skip
LUKA = _event("402", "Sacramento Kings at Los Angeles Lakers", "2026-11-06T03:30Z",
              _side("away", "Kings", "SAC", 120, ("Domantas Sabonis", 24)),
              _side("home", "Lakers", "LAL", 128, ("Luka Doncic", 52)), ["Spectrum SportsNet"])  # fmt: skip


def _fetch(boards):
    def fetch(league, dates="", week=None):
        return {"events": boards.get(league, [])}

    return fetch


def _schedule(league, team):
    nxt = {"BAL": ("Chargers", "2026-11-17T01:15Z"), "JAX": ("Texans", "2026-11-15T18:00Z"),
           "LAL": ("Suns", "2026-11-07T03:00Z"), "SAC": ("Jazz", "2026-11-08T02:00Z")}[team]  # fmt: skip
    return {"events": [
        {"date": "2026-11-01T18:00Z", "competitions": [{"competitors": [
            {"team": {"abbreviation": team, "shortDisplayName": "Us"}},
            {"team": {"abbreviation": "OLD", "shortDisplayName": "Old Foes"}}]}]},
        {"date": nxt[1], "competitions": [{"competitors": [
            {"team": {"abbreviation": team, "shortDisplayName": "Us"}},
            {"team": {"abbreviation": "NXT", "shortDisplayName": nxt[0]}}]}]},
    ]}  # fmt: skip


# ---- #1999 / #1877 / #1687: last night's games at overnight -----------------------------------


class LastNightTests(unittest.TestCase):
    def _ideas(self, boards, *, now=NOW, done=(), drafted=False):
        mod = _last_night()
        with (
            patch.dict(os.environ, {"LAST_NIGHT": "true"}),
            patch("core.best_bet.marquee_names", return_value=MARQUEE),
        ):
            return mod.last_night_ideas("tapin", now=now, fetch=_fetch(boards), schedule=_schedule,
                                        done=set(done), drafted=lambda _t: drafted)  # fmt: skip

    def test_a_national_final_the_pc_slept_through_is_drafted_at_overnight(self):
        ideas = self._ideas({"nfl": [TNF]})
        self.assertEqual([i.topic for i in ideas], ["Ravens beat Jaguars 27-17: what it means"])
        self.assertEqual(ideas[0].source, "result")
        self.assertIn("ESPN final: Jaguars 17, Ravens 27", ideas[0].facts[0])

    def test_not_one_the_fast_lane_made_nor_one_drafted_nor_a_stale_one(self):
        self.assertEqual(self._ideas({"nfl": [TNF]}, done=["result:401"]), [])
        self.assertEqual(self._ideas({"nfl": [TNF]}, drafted=True), [])
        self.assertEqual(self._ideas({"nfl": [TNF]}, now=datetime(2026, 11, 7, 11, tzinfo=UTC)), [])

    def test_the_games_own_preview_is_not_its_result(self):
        # Live 11-06: run 242, "Jacksonville Jaguars at Baltimore Ravens", read as the same story,
        # so the TNF final the PC slept through was taken as already drafted.
        from core.series.last_night import result_drafted

        preview = ["Jacksonville Jaguars at Baltimore Ravens"]
        self.assertFalse(result_drafted("tapin", "Ravens beat Jaguars 33-10: what it means",
                                        recent=preview))  # fmt: skip
        self.assertTrue(result_drafted("tapin", "Ravens beat Jaguars 33-10: what it means",
                                       recent=[*preview, "Ravens beat Jaguars 33-10: what it means"]))  # fmt: skip

    def test_a_marquee_players_40_point_night(self):
        ideas = self._ideas({"nba": [LUKA]})
        self.assertEqual([i.topic for i in ideas],
                         ["Luka Doncic scores 52 as the Lakers beat the Kings 128-120: what it means"])  # fmt: skip
        self.assertIn("Luka Doncic scored 52 points", " ".join(ideas[0].facts))
        quiet = _event("403", "Utah Jazz at Phoenix Suns", "2026-11-06T02:00Z",
                       _side("away", "Jazz", "UTA", 101, ("Lauri Markkanen", 41)),
                       _side("home", "Suns", "PHX", 99, ("Devin Booker", 30)), ["KJZZ"])  # fmt: skip
        self.assertEqual(self._ideas({"nba": [quiet]}), [])  # 41, but not a marquee name

    def test_a_results_next_games_ride_along(self):
        facts = " ".join(self._ideas({"nfl": [TNF]})[0].facts)
        self.assertIn("the Ravens play the Chargers next, on Monday, November 16", facts)
        self.assertIn("the Jaguars play the Texans next, on Sunday, November 15", facts)

    def test_the_fast_lanes_result_carries_them_too(self):
        story = jobs.fast_lane.final_of("nfl", TNF, now=datetime(2026, 11, 6, 5, tzinfo=UTC))
        facts = jobs.fast_lane.story_facts("tapin", story, schedule=_schedule)
        self.assertEqual(facts[0], story["final"])
        self.assertTrue(any("Chargers next" in f for f in facts))

    def test_a_result_is_news_and_the_night_drafts_it(self):
        from core.angle_intent import ANGLE_NEWS

        self.assertEqual(core.batch_generation.draft_intent(own_idea=False, preview="",
                                                            source="result"), ANGLE_NEWS)  # fmt: skip
        idea = core.best_bet.BestBetResult(
            topic="Ravens beat Jaguars 27-17: what it means", domain="nfl", avg_engaged_rate=0.0,
            source="result", supporting_runs=0, rationale="")  # fmt: skip
        with (
            patch("core.series.countdown.countdown_idea", return_value=None),
            patch("core.series.dated.dated_ideas", return_value=[]),
            patch("core.series.recap.recap_ideas", return_value=[]),
            patch("core.series.recap.matchup_ideas", return_value=[]),
            patch("core.series.last_night.last_night_ideas", return_value=[idea], create=True),
            patch("core.batch_generation.long_breakout_ideas", return_value=[]),
        ):
            topics = core.batch_generation.collect_topics("tapin", count=0)
        self.assertEqual(topics, ["Ravens beat Jaguars 27-17: what it means"])


# ---- #1623 + #1624: a Short ends on a loop line, not a sign-off ---------------------------------


SCRIPT = ("Mahomes was held to three points in Seattle. The line moved twice. Kansas City needs "
          "answers at receiver. Mahomes gets his chance Sunday. Tap in for more.")  # fmt: skip


class LoopLineTests(unittest.TestCase):
    def test_a_shorts_sign_off_goes_and_its_last_line_is_read(self):
        from core.script_craft import loop_close

        script, verdict = loop_close(SCRIPT)
        self.assertTrue(script.endswith("Mahomes gets his chance Sunday."))
        self.assertEqual(verdict["sign_off_dropped"], 1)
        self.assertTrue(verdict["loops"])  # the last line names the first's subject
        kept, _v = loop_close("Who wins it? Let me know in the comments.")
        self.assertTrue(
            kept.endswith("Let me know in the comments.")
        )  # a question is not a sign-off
        bare, again = loop_close("Mahomes was held to three. The Chiefs fell. Follow for more!")
        self.assertEqual(
            (bare, again["loops"]), ("Mahomes was held to three. The Chiefs fell.", False)
        )

    def test_only_a_short(self):
        self.assertTrue(core.content_engine.short_loop_pass(SCRIPT, "2")[0].endswith("Sunday."))
        self.assertEqual(core.content_engine.short_loop_pass(SCRIPT, "4")[0], SCRIPT)

    def _prompts(self, length):
        system, user = core.content_engine._build_prompts(
            topic="Mahomes held to three in Seattle", signals={}, min_words=120, max_words=160,
            today="2026-11-06", channel_id="tapin", script_brief="", seo_block="",
            signal_facts="- Mahomes was held to three points.", signal_summary="", brief_block="",
            length_choice=length,
        )  # fmt: skip
        return system + "\n" + user

    def test_a_shorts_prompt_asks_for_a_loop_line_not_the_sign_off(self):
        short, long_ = self._prompts("1"), self._prompts("4")
        self.assertNotIn("Tap in for more", short)
        self.assertIn("LOOP:", short)
        self.assertIn("Tap in for more", long_)
        self.assertNotIn("LOOP:", long_)


# ---- #1626: the subject in the first three words ---------------------------------------------------


class SubjectFirstTests(unittest.TestCase):
    def test_the_first_three_words_name_the_subject(self):
        from core.script_craft import subject_first

        self.assertFalse(subject_first("Jamal Murray's 27.3 points a night is the reason Denver wins",
                                       "Denver Nuggets"))  # fmt: skip
        self.assertTrue(subject_first("Denver's Jamal Murray scores 27 a night.", "Denver Nuggets"))
        self.assertTrue(subject_first("The Nuggets will win in Indiana.", "Denver Nuggets"))
        self.assertTrue(subject_first("GTA 6 just got a new trailer.", "GTA 6"))
        self.assertTrue(subject_first("Anything at all.", ""))  # no subject, nothing to check

    def test_the_rewrite_keeps_an_opener_that_names_it(self):
        payload = {"openers": [
            "Jamal Murray scores 27 a night, and Indiana has no answer for him.",
            "The Nuggets will beat Indiana because Jamal Murray scores 27 a night.",
        ]}  # fmt: skip
        script = ("Jamal Murray's 27 points a night is why this one tilts. Indiana allows the most "
                  "points in the league. The Nuggets travel to Indiana on Saturday.")  # fmt: skip
        with (
            patch.object(core.content_engine, "_call_content_llm", return_value=payload),
            patch("analytics.hook_learning.regen_guidance", return_value={}),
            patch.object(core.content_engine, "_recent_openers", return_value=[]),
            patch.dict(os.environ, {"HOOK_REGEN_ENABLED": "true"}),
        ):
            new, extra = core.content_engine._hook_variants(script, subject="Denver Nuggets")
        self.assertTrue(new.startswith("The Nuggets will beat Indiana"), new)
        self.assertTrue(any("first three words" in p for p in extra.get("problems") or []))

    def test_the_subject_comes_from_the_topic(self):
        # Live replay 11-06: `subject_name` made "People", "All" and "Indie" the subjects of 45 of
        # 58 hooks - a game's two teams, or the marquee names a headline names, are the subject.
        hook_subject = core.content_engine.hook_subject
        with patch("core.best_bet.marquee_names", return_value=["GTA 6", "GTA", "Xbox", "Mahomes"]):
            self.assertEqual(hook_subject("Denver Nuggets at Indiana Pacers"),
                             ["Denver Nuggets", "Indiana Pacers"])  # fmt: skip
            self.assertEqual(hook_subject("GTA 6: 15 days to launch"), ["GTA 6", "GTA"])
            self.assertEqual(hook_subject("People are calling AI mods the end of modding"), [])
        from core.script_craft import subject_first

        self.assertTrue(subject_first("Detroit's defense tests Embiid.",
                                      ["Philadelphia 76ers", "Detroit Pistons"]))  # fmt: skip

    def test_an_opener_with_the_prompts_placeholder_is_refused(self):
        # Run 232 (public 11-03): "15 days out, and the wait since 2022 has become <who> can't
        # maintain <what>." - the prompt's own shape hint, kept as the opener.
        payload = {"openers": ["GTA 6 is 15 days out, and <who> will <what> before launch.",
                               "GTA 6 is 15 days out, and Rockstar will show the map first."]}  # fmt: skip
        script = "Fifteen days to launch. Rockstar has shown three trailers. The map is next."
        with (
            patch.object(core.content_engine, "_call_content_llm", return_value=payload),
            patch("analytics.hook_learning.regen_guidance", return_value={}),
            patch.object(core.content_engine, "_recent_openers", return_value=[]),
            patch.dict(os.environ, {"HOOK_REGEN_ENABLED": "true"}),
        ):
            new, extra = core.content_engine._hook_variants(script, subject=["GTA 6"])
        self.assertNotIn("<who>", new)
        refused = [v for v in extra["variants"] if "<who>" in v["opener"]]
        self.assertIn("placeholder", refused[0].get("refused", ""))


# ---- #2001: a preview's title says its call as a call -------------------------------------------


class PreviewTitleTests(unittest.TestCase):
    def test_a_final_shaped_title_becomes_a_call(self):
        from core.youtube_meta import preview_as_call

        self.assertEqual(preview_as_call("Denver Nuggets win: Jamal Murray's form decides it all")[0],
                         "Denver Nuggets will win: Jamal Murray's form decides it all")  # fmt: skip
        self.assertEqual(
            preview_as_call(
                "Detroit Pistons bench outplays Boston Celtics reserves in key stretch"
            )[0],
            "Detroit Pistons bench will outplay Boston Celtics reserves in key stretch",
        )
        for title in ("Lakers to Win vs Warriors: Doncic Leads Points and Assists in Preview",
                      "Why the Nuggets beat the Pacers on Saturday: Jamal Murray's form",
                      "Ravens' Defense Faces Toughest Test Against Improving Jaguars"):  # fmt: skip
            self.assertEqual(preview_as_call(title), (title, ""))

    def test_only_a_preview(self):
        from core.angle_intent import ANGLE_NEWS, ANGLE_PREVIEW
        from core.youtube_meta import preview_title

        title = "Denver Nuggets win: Jamal Murray's form decides it all"
        self.assertTrue(
            preview_title(title, ANGLE_PREVIEW)[0].startswith("Denver Nuggets will win")
        )
        self.assertEqual(preview_title("Ravens beat Jaguars 27-17", ANGLE_NEWS)[0],
                         "Ravens beat Jaguars 27-17")  # fmt: skip


if __name__ == "__main__":
    unittest.main()
