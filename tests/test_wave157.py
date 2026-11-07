"""Wave 157 (2026-11-06) - the next five, before W4's freeze.

#1676 stat-shock Shorts (one surprising number is the whole video); #1674 rankings with an
on-screen countdown; #1645 a re-hook beat at the drop-off second; #1637 length by format as an
experiment; #1688 patch winners and losers for Marvel Rivals and Call of Duty.
"""

from __future__ import annotations

import inspect
import os
import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

# Imported before any patch below (wave 145's reversed-suite failure).
import core.batch_generation
import core.best_bet
import core.retention
import core.series.shapes as shapes
import core.success.formats
import video.subtitles

UTC = timezone.utc
NOW = datetime(2026, 11, 7, 4, 0, tzinfo=UTC)


class StatShockTests(unittest.TestCase):
    """#1676 (B04.5): one surprising number is the whole video."""

    def test_the_number_a_headline_is_built_on(self):
        self.assertEqual(shapes.shock_number(
            "Victor Wembanyama after historic 52-point, 24-rebound night: 'It should be more'"),
            "52-point")  # fmt: skip
        self.assertEqual(shapes.shock_number(
            "NBA Players 30 And Older Fall Below 20 Percent Of Minutes For First Time"),
            "20 Percent")  # fmt: skip
        self.assertEqual(shapes.shock_number("Steveson knocked out in 12 seconds at UFC 331"),
                         "12 seconds")  # fmt: skip

    def test_a_numbered_event_or_a_record_word_alone_is_not_one(self):
        for topic in ("UFC 334: Fight card, date, complete guide",
                      "Week 9 NFL odds, picks, predictions",
                      "Colts rookie LB CJ Allen will start for first time on Sunday",
                      "Rockstar shares new screenshots of Vice City"):  # fmt: skip
            self.assertEqual(shapes.shock_number(topic), "", topic)

    def test_the_brief_makes_the_number_the_video(self):
        topic = "Victor Wembanyama after historic 52-point, 24-rebound night"
        self.assertEqual(shapes.draft_shape(topic, "trending"), "stat_shock")
        brief = shapes.shape_brief("stat_shock", topic)
        self.assertIn("STAT-SHOCK", brief)
        self.assertIn("52-point", brief)


class RankingTests(unittest.TestCase):
    """#1674 (B04.3): rankings with an on-screen countdown."""

    def test_rankings_count_down_from_five_at_most(self):
        count = shapes.ranking_count
        self.assertEqual(count("Every GTA Game, Ranked by Metacritic Score"), 5)
        self.assertEqual(count("NBA relegation zone predictions: Ranking the 7 worst teams"), 5)
        self.assertEqual(count("Top 3 plays of the NFL week"), 3)
        self.assertEqual(count("10 Devastating Game Cancellations That Still Hurt"), 5)

    def test_ranked_mode_and_a_roundup_are_not_rankings(self):
        count = shapes.ranking_count
        self.assertEqual(count("Fortnite ranked mode returns with a new reset"), 0)
        self.assertEqual(count("Miami loses Toney; Week 9 picks and latest NBA Power Rankings"), 0)
        self.assertEqual(count("Mahomes is ranked No. 1 by his peers"), 0)

    def test_the_brief_counts_down_by_number(self):
        brief = shapes.shape_brief("ranking", "Top 3 plays of the NFL week")
        self.assertIn('"Number 3,"', brief)
        self.assertIn('"Number 1,"', brief)
        self.assertEqual(
            shapes.draft_shape("Every GTA Game, Ranked by Metacritic Score"), "ranking"
        )

    def _words(self, *items):
        out, t = [], 0.0
        for text in items:
            out.append({"word": text, "start": t, "end": t + 0.4})
            t += 1.0
        return out

    def test_the_narrations_numbers_are_the_marks(self):
        words = self._words("Number", "3,", "Vice", "City.", "Number", "two,", "Liberty.",
                            "Number", "1,", "San", "Andreas.")  # fmt: skip
        self.assertEqual(video.subtitles.countdown_marks(words), [(3, 0.0), (2, 4.0), (1, 7.0)])
        plain = self._words("He", "was", "the", "number", "one", "pick", "in", "2023.")
        self.assertEqual(video.subtitles.countdown_marks(plain), [])

    def test_each_number_is_on_screen_until_the_next(self):
        words = self._words("Number", "3,", "a.", "Number", "2,", "b.", "Number", "1,", "c.")
        ass = "[V4+ Styles]\nStyle: Default,Arial\n\n[Events]\nFormat: Layer, Start, End\n"
        out = video.subtitles._with_countdown(ass, words, "tapin")
        self.assertIn("Style: Rank,", out)
        rank = [line for line in out.splitlines() if ",Rank,," in line]
        self.assertEqual(len(rank), 3)
        self.assertTrue(rank[0].endswith("#3"))
        self.assertIn("0:00:03.00", rank[0])  # until "Number 2" starts at 3 s
        self.assertEqual(video.subtitles._with_countdown(ass, words[:3], "tapin"), ass)

    def test_the_captions_carry_it(self):
        self.assertIn("_with_countdown(text, words", inspect.getsource(
            video.subtitles.generate_subtitle_file))  # fmt: skip


class PatchTests(unittest.TestCase):
    """#1688 (B04.17): patch winners and losers for Marvel Rivals and Call of Duty."""

    POOL = (
        {
            "topic": "Marvel Rivals Season 5.5 patch notes: Hela buffed, Magik nerfed",
            "outlets": ["Dexerto", "PCGamesN"],
            "first": NOW - timedelta(hours=6),
        },
        {
            "topic": "Black Ops 7 update nerfs the meta SMG",
            "outlets": ["Charlie Intel"],
            "first": NOW - timedelta(hours=100),
        },
        {
            "topic": "Fortnite patch notes for v38.10",
            "outlets": ["Dexerto"],
            "first": NOW - timedelta(hours=2),
        },
    )

    def test_a_patch_headline_names_its_game(self):
        self.assertEqual(shapes.patch_game(self.POOL[0]["topic"]), "Marvel Rivals")
        self.assertEqual(shapes.patch_game(self.POOL[1]["topic"]), "Call of Duty")
        self.assertEqual(shapes.patch_game(self.POOL[2]["topic"]), "")
        self.assertEqual(shapes.patch_game("Marvel Rivals adds a new map"), "")

    def _ideas(self, drafted=False, pool=None):
        with patch.dict(os.environ, {"PATCH_SHORTS": "true"}):
            return shapes.patch_ideas("tapin", now=NOW, pool=list(pool or self.POOL),
                                      drafted=lambda *_a: drafted)  # fmt: skip

    def test_a_fresh_patch_becomes_winners_and_losers_once(self):
        ideas = self._ideas()
        self.assertEqual([i.topic for i in ideas],
                         ["Marvel Rivals Season 5.5 patch: the winners and losers"])  # fmt: skip
        self.assertEqual(ideas[0].source, "patch")
        self.assertIn("Hela buffed", ideas[0].facts[0])
        self.assertEqual(self._ideas(drafted=True), [])

    def test_a_patch_past_three_days_waits_for_the_next(self):
        self.assertEqual(self._ideas(pool=[self.POOL[1]]), [])

    def test_off_in_the_suite(self):
        self.assertEqual(shapes.patch_ideas("tapin", now=NOW, pool=list(self.POOL)), [])

    def test_it_is_news_shaped_winners_and_losers(self):
        from core.angle_intent import ANGLE_NEWS

        self.assertEqual(core.batch_generation.draft_intent(own_idea=False, preview="",
                                                            source="patch"), ANGLE_NEWS)  # fmt: skip
        self.assertEqual(shapes.draft_shape("Marvel Rivals patch: the winners and losers", "patch"),
                         "patch")  # fmt: skip
        self.assertIn("WINNERS AND LOSERS", shapes.shape_brief("patch", ""))

    def test_overnight_takes_it(self):
        bet = core.best_bet.BestBetResult(topic="Marvel Rivals patch: the winners and losers",
                                          domain="gaming", avg_engaged_rate=0.0, source="patch",
                                          supporting_runs=0, rationale="")  # fmt: skip
        with (
            patch("core.series.shapes.patch_ideas", return_value=[bet]),
            patch("core.best_bet.get_idea_menu", return_value=([], [])),
            patch("core.best_bet.marquee_names", return_value=[]),
            patch("core.best_bet.crossover_names", return_value=[]),
            patch("core.series.countdown.countdown_idea", return_value=None),
            patch("core.series.recap.recap_ideas", return_value=[]),
            patch("core.series.recap.matchup_ideas", return_value=[]),
            patch("core.series.recap.debate_ideas", return_value=[]),
            patch("core.series.last_night.last_night_ideas", return_value=[]),
            patch("core.series.profiles.profile_ideas", return_value=[]),
            patch("core.batch_generation.long_breakout_ideas", return_value=[]),
            patch("core.batch_generation.night_gaming_share"),
            patch("core.batch_generation._swap_holdouts", return_value=set()),
            patch("core.batch_generation._with_follow_up", side_effect=lambda _c, t, *_a: t),
            patch("core.series.dated.launch_names", return_value=[]),
            patch("core.series.recap.fight_week", return_value=[]),
        ):
            topics = core.batch_generation.collect_topics("tapin", count=1)
        self.assertEqual(topics, ["Marvel Rivals patch: the winners and losers"])


class ShapeRecordTests(unittest.TestCase):
    """Each shape is recorded on the run and ranked as its own format."""

    def test_the_shape_is_the_runs_format(self):
        fmt = core.success.formats.run_format
        self.assertEqual(fmt({"shape": "ranking"}), "ranking")
        self.assertEqual(fmt({"shape": "stat_shock"}), "stat-shock")
        pick = {"offered": [{"topic": "Who is Josh Hokit?", "source": "profile"}], "picked": 1}
        self.assertEqual(fmt({"best_bet": pick}), "who is")

    def test_the_draft_records_its_shape_and_its_beat(self):
        with (
            patch("core.run_features.merge_features") as merged,
            patch("core.retention.rehook_beat_second", return_value=15.0),
        ):
            core.batch_generation._record_draft_features(301, "ranking", "tapin")
            core.batch_generation._record_draft_features(302, "", "tapin", beat=False)
            core.batch_generation._record_draft_features(0, "ranking", "tapin")
        self.assertEqual(merged.call_args_list[0].args, (301, {"shape": "ranking",
                                                               "rehook_beat_s": 15.0}))  # fmt: skip
        self.assertEqual(merged.call_count, 1)

    def test_generate_draft_gives_the_brief_and_records_it(self):
        source = inspect.getsource(core.batch_generation.generate_draft)
        self.assertIn("shape_brief(shape, topic)", source)
        self.assertIn("_record_draft_features(result.run_id, shape", source)
        self.assertIn("length_trial_arm(channel_id, machine_intent)", source)


class RehookBeatTests(unittest.TestCase):
    """#1645 (B02.24): a re-hook beat at the drop-off second."""

    def setUp(self):
        core.retention._reset_beat_cache()
        self.addCleanup(core.retention._reset_beat_cache)

    def test_the_median_second_of_the_last_measured_shorts(self):
        with patch.object(core.retention, "drop_off_seconds", return_value=[9.3, 15.0, 16.9, 30.2]):
            self.assertEqual(core.retention.drop_off_second("tapin"), 15.9)
        core.retention._reset_beat_cache()
        with patch.object(core.retention, "drop_off_seconds", return_value=[9.3, 15.0]):
            self.assertIsNone(core.retention.drop_off_second("tapin"))

    def test_the_rule_says_the_second_and_where_the_beat_goes(self):
        with patch.dict(os.environ, {"REHOOK_BEAT": "true"}), \
                patch.object(core.retention, "drop_off_second", return_value=15.0):  # fmt: skip
            rule = core.retention.rehook_beat_rule("tapin")
        self.assertIn("0:15", rule)
        self.assertIn("about 43 words in", rule)
        with patch.dict(os.environ, {"REHOOK_BEAT": "true"}), \
                patch.object(core.retention, "drop_off_second", return_value=4.0):  # fmt: skip
            self.assertEqual(core.retention.rehook_beat_rule("tapin"), "")  # the hook itself
        with patch.object(core.retention, "drop_off_second", return_value=15.0):
            self.assertEqual(core.retention.rehook_beat_rule("tapin"), "")  # off in the suite

    def _prompt(self, length_choice):
        from core.content_engine import _build_prompts

        system, _user = _build_prompts(
            topic="Chiefs trade for a receiver", signals={}, min_words=100, max_words=150,
            today="2026-11-07", channel_id="tapin", script_brief="", seo_block="",
            signal_facts="", signal_summary="", brief_block="", length_choice=length_choice)  # fmt: skip
        return system

    def test_a_shorts_prompt_carries_the_beat(self):
        with patch.dict(os.environ, {"REHOOK_BEAT": "true"}), \
                patch.object(core.retention, "drop_off_second", return_value=15.0):  # fmt: skip
            self.assertIn("RE-HOOK BEAT", self._prompt("1"))
            self.assertIn("RE-HOOK BEAT", self._prompt("2"))
            self.assertNotIn("RE-HOOK BEAT", self._prompt("4"))

    def test_the_weekly_readout_compares_with_and_without(self):
        rows = [(15.0, 0.52), (15.0, 0.48), (None, 0.41), (None, 0.39), (None, 0.45)]
        lines = core.retention.rehook_beat_lines("tapin", rows=rows)
        self.assertEqual(len(lines), 1)
        self.assertIn("50% still watching", lines[0])
        self.assertIn("41% before it", lines[0])
        self.assertEqual(core.retention.rehook_beat_lines("tapin", rows=rows[2:]), [])


class LengthTrialTests(unittest.TestCase):
    """#1637 (B02.16): length by format as an experiment."""

    def test_news_and_previews_have_their_lengths(self):
        from core.angle_intent import ANGLE_DEFAULT, ANGLE_NEWS, ANGLE_PREVIEW

        fl = core.batch_generation.format_length
        self.assertEqual(fl(ANGLE_NEWS), ("1", None))
        self.assertEqual(fl(ANGLE_PREVIEW), ("2", (150, 200)))
        self.assertIsNone(fl(ANGLE_DEFAULT))

    def test_the_arm_with_fewer_drafts_inside_the_window(self):
        from core.angle_intent import ANGLE_DEFAULT, ANGLE_NEWS

        arm = core.batch_generation.length_trial_arm
        rows = [{"arm": "format"}, {"arm": "format"}, {"arm": "learned"}]
        with patch.dict(os.environ, {"LENGTH_TRIAL": "true"}), \
                patch("core.experiments._assignments", return_value=rows):  # fmt: skip
            self.assertEqual(
                arm("tapin", ANGLE_NEWS, today=date(2026, 11, 8)), ("learned", "1", None)
            )
            self.assertIsNone(arm("tapin", ANGLE_NEWS, today=date(2026, 11, 22)))
            self.assertIsNone(arm("tapin", ANGLE_DEFAULT, today=date(2026, 11, 8)))
        self.assertIsNone(arm("tapin", ANGLE_NEWS, today=date(2026, 11, 8)))  # off in the suite

    def test_the_weekly_readout_by_arm(self):
        def row(run_id, views, stayed):
            when = datetime(2026, 11, 9, 17, tzinfo=UTC)
            import json

            metrics = {"lifetime_views": views, "stayed_share": stayed,
                       "daily": [{"day": "2026-11-09", "views": views}]}  # fmt: skip
            return SimpleNamespace(content_run_id=run_id, published_at=when, privacy_status="public",
                                   metrics_json=json.dumps(metrics))  # fmt: skip

        rows = [row(1, 80, 0.5), row(2, 120, 0.6), row(3, 60, 0.4)]
        with patch("core.success.target.views_7d", side_effect=lambda m, _w: m["lifetime_views"]):
            lines = core.success.formats.length_trial_lines(
                "tapin", today=date(2026, 11, 20), rows=rows, features=lambda _r: {},
                arms={1: "format", 2: "format", 3: "learned"})  # fmt: skip
        self.assertEqual(len(lines), 1)
        self.assertIn("format 100 (n=2, stayed 55%)", lines[0])
        self.assertIn("learned 60 (n=1, stayed 40%)", lines[0])

    def test_the_weekly_report_prints_both_readouts(self):
        import analytics.weekly_report as weekly

        source = inspect.getsource(weekly)
        self.assertIn("length_trial_lines(channel_id)", source)
        self.assertIn("rehook_beat_lines(channel_id)", source)


if __name__ == "__main__":
    unittest.main()
