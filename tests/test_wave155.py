"""Wave 155 (2026-11-06) - the other ten of the operator's "next 20".

The bridge's lane numbers, each with the run of weeks its "done" asks for: #1621 the median
Short's first week, #1646 stayed share, #1671 organic views a day, #1696 the best format's share,
#1721 organic subscribers a week, #1771 money outside YouTube; #1668 a Short's all-in cost; #1620
celebrity crossovers lead; #1673 a numbered card's "who wins?" Short, #1642 ending on the honest
question with comments per 1,000 measured.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

# Imported before any patch below (wave 145's reversed-suite failure).
import core.batch_generation
import core.best_bet
import core.series.recap
import core.success.bridge
import core.success.formats
import core.success.scorecard
import core.ypp_readiness

UTC = timezone.utc
TODAY = date(2026, 11, 9)


def _lanes():
    import core.success.lanes

    return core.success.lanes


def _short(day, views, stayed=None, fmt="headline"):
    when = datetime.combine(day, datetime.min.time(), tzinfo=UTC).replace(hour=17)
    return {"when": when, "views7": views, "stayed": stayed, "format": fmt}


def _weeks(medians, **extra):
    """One Short a week, the last one in the week of 11-02."""
    start = date(2026, 11, 2) - timedelta(weeks=len(medians) - 1)
    return [_short(start + timedelta(weeks=i), m, **extra) for i, m in enumerate(medians)]


# ---- the run of weeks ---------------------------------------------------------------------------


class RunTests(unittest.TestCase):
    def test_rising_and_above(self):
        lanes = _lanes()
        self.assertEqual(lanes.rising_run([60, 50, 55, 70, 80]), 3)
        self.assertEqual(lanes.rising_run([80, 70]), 0)
        self.assertEqual(lanes.above_run([0.40, 0.50, 0.46], 0.45), 2)


# ---- #1621 / #1646 / #1671 / #1696: the views lanes ------------------------------------------------


class ViewsLaneTests(unittest.TestCase):
    def test_the_median_short_against_the_30_day_median(self):
        line = _lanes().views_lane(_weeks([60, 50, 55, 70, 80]), today=TODAY)
        self.assertIn("#1621", line)
        self.assertIn("80 organic views", line)
        self.assertIn("rising 3 of 4 weeks", line)

    def test_the_weeks_stayed_share_against_45(self):
        shorts = _weeks([60, 60, 60], stayed=0.5)
        shorts[0]["stayed"] = 0.30
        line = _lanes().stayed_lane(shorts)
        self.assertIn("50%", line)
        self.assertIn("2 of 4 weeks above 45%", line)

    def test_organic_views_a_day_against_250(self):
        when = datetime(2026, 11, 1, 18, tzinfo=UTC)
        series = [[(when + timedelta(days=d)).date().isoformat(), 300] for d in range(8)]
        row = SimpleNamespace(content_run_id=1, published_at=when, privacy_status="public",
                              metrics_json=json.dumps({"daily_views": series}))  # fmt: skip
        line = _lanes().daily_lane([row], today=TODAY)
        self.assertIn("300 organic views a day", line)
        self.assertIn("250", line)

    def test_the_best_formats_share_of_uploads(self):
        shorts = [*_weeks([90, 90, 90], fmt="preview"), *_weeks([40, 40, 40], fmt="headline"),
                  *_weeks([40, 40], fmt="headline")]  # fmt: skip
        line = _lanes().format_lane(shorts)
        self.assertIn("preview", line)
        self.assertIn("share", line)


# ---- #1721: organic subscribers a week -------------------------------------------------------------


class SubscribersLaneTests(unittest.TestCase):
    def test_the_sync_keeps_each_weeks_net_and_the_lane_reads_the_run(self):
        tmp = tempfile.mkdtemp(prefix="w155_ypp_")
        template = os.path.join(tmp, "ypp_{channel}.json")
        ypp = core.ypp_readiness
        with patch.object(ypp, "YPP_TEMPLATE", template):
            for day, gained, lost in (("2026-10-26", 12, 1), ("2026-11-02", 14, 2),
                                      ("2026-11-09", 3, 1)):  # fmt: skip
                ypp.save_ypp_numbers("tapin", {"as_of": day, "subs_gained_7d": gained,
                                               "subs_lost_7d": lost})  # fmt: skip
            numbers = ypp.load_ypp_numbers("tapin")
        self.assertEqual(numbers["subs_weeks"], {"2026-W44": 11, "2026-W45": 12, "2026-W46": 2})
        line = _lanes().subscribers_lane(numbers)
        self.assertIn("+2 subscribers in the last 7 days", line)
        self.assertIn("0 of 4 weeks at +10", line)

    def test_the_scoreboard_prints_it(self):
        numbers = {"subscribers": 189, "subs_gained_7d": 3, "subs_lost_7d": 1,
                   "subs_weeks": {"2026-W46": 2}}  # fmt: skip
        lines = core.success.bridge.scoreboard_lines("tapin", numbers=numbers, entries=[],
                                                     today=TODAY)  # fmt: skip
        self.assertTrue(any("#1721" in line for line in lines))


# ---- #1771: money outside YouTube this month -------------------------------------------------------


class MoneyLaneTests(unittest.TestCase):
    def test_this_months_income_against_zero(self):
        income = [{"amount": 12.0, "date": "2026-11-03", "what": "Amazon"},
                  {"amount": 5.0, "date": "2026-10-20", "what": "Amazon"}]  # fmt: skip
        line = _lanes().money_lane(income, today=TODAY)
        self.assertIn("$12.00 earned outside YouTube this month", line)
        self.assertIn("#1771", line)


# ---- #1668: a Short's all-in cost ----------------------------------------------------------------------


class ShortCostTests(unittest.TestCase):
    def test_the_median_short_and_how_many_under_a_quarter(self):
        rows = [{"cost": c, "views": 50} for c in (0.04, 0.31, 0.29, 0.12, 0.33)]
        line = core.success.scorecard.short_cost_line(rows)
        self.assertIn("$0.29", line)
        self.assertIn("2 of 5 under $0.25", line)


# ---- #1620: celebrity crossovers lead -------------------------------------------------------------------


class CrossoverTests(unittest.TestCase):
    def _bet(self, topic, domain="gaming", outlets=1):
        return core.best_bet.BestBetResult(topic=topic, domain=domain, avg_engaged_rate=0.0,
                                           source="trending", supporting_runs=0, rationale="",
                                           outlets=outlets)  # fmt: skip

    def test_a_known_name_in_a_gaming_story(self):
        from core.best_bet import crossover_story

        names = ["Ben Affleck", "Snoop Dogg"]
        self.assertTrue(crossover_story("Ben Affleck admits he argues with 12-year-olds in Fortnite",
                                        "gaming", names))  # fmt: skip
        self.assertFalse(crossover_story("Ben Affleck's new film opens", "popculture", names))
        self.assertFalse(crossover_story("Fortnite adds a new map", "gaming", names))

    def test_it_passes_the_gate_and_leads_after_the_rest(self):
        # wave 159: not a trade headline - a marquee trade now leads above a crossover (#1614)
        ideas = [self._bet("Chiefs rally past the Bills", "nfl", 3),
                 self._bet("Ben Affleck admits he argues with 12-year-olds in Fortnite")]  # fmt: skip
        with (
            patch("core.best_bet.get_idea_menu", return_value=(ideas, [])),
            patch("core.best_bet.marquee_names", return_value=["Chiefs"]),
            patch("core.best_bet.crossover_names", return_value=["Ben Affleck"], create=True),
            patch("core.series.countdown.countdown_idea", return_value=None),
            patch("core.series.recap.recap_ideas", return_value=[]),
            patch("core.series.recap.matchup_ideas", return_value=[]),
            patch("core.series.recap.debate_ideas", return_value=[], create=True),
            patch("core.series.last_night.last_night_ideas", return_value=[]),
            patch("core.batch_generation.long_breakout_ideas", return_value=[]),
            patch("core.batch_generation.night_gaming_share"),
            patch("core.batch_generation._swap_holdouts", return_value=set()),
            patch("core.batch_generation._with_follow_up", side_effect=lambda _c, t, *_a: t),
            patch("core.series.dated.launch_names", return_value=[]),
            patch("core.series.recap.fight_week", return_value=[]),
        ):
            topics = core.batch_generation.collect_topics("tapin", count=1)
        self.assertEqual(topics, ["Ben Affleck admits he argues with 12-year-olds in Fortnite"])

    def test_a_past_videos_topic_is_not_a_crossover_lead(self):
        # Live 11-06: the menu re-offered run 126's "Ben Affleck ... 12-year-olds" (source
        # "analytics", 411 views on a past video) - leading it would redraft an old story.
        old = core.best_bet.BestBetResult(
            topic="Ben Affleck admits he gets into arguments with 12-year-olds", domain="gaming",
            avg_engaged_rate=0.0, source="analytics", supporting_runs=0, rationale="")  # fmt: skip
        ideas = [self._bet("Chiefs trade for a receiver", "nfl", 3), old]
        with (
            patch("core.best_bet.marquee_names", return_value=[]),
            patch("core.best_bet.crossover_names", return_value=["Ben Affleck"], create=True),
            patch("core.series.dated.launch_names", return_value=[]),
        ):
            led = core.batch_generation.lead_first(ideas, "tapin", week=[])
        self.assertEqual(led[0].topic, "Chiefs trade for a receiver")

    def test_the_operators_list_is_seeded(self):
        from core.best_bet import crossover_names

        self.assertIn("Ben Affleck", crossover_names("tapin"))


# ---- #1673 + #1642: a numbered card's "who wins?" Short ---------------------------------------------


BOARD = {"leagues": [{"calendar": [{"label": "UFC 334: Gane vs. Hokit",
                                    "startDate": "2026-11-15T01:00Z"}]}]}  # fmt: skip


class DebateTests(unittest.TestCase):
    def _ideas(self, now):
        with (
            patch.dict(os.environ, {"UFC_DEBATE": "true"}),
            patch("core.batch_generation.series_drafted", return_value=False),
        ):
            return core.series.recap.debate_ideas("tapin", now=now, board=BOARD,
                                                  fetch=lambda _l, dates="": {"events": []},
                                                  headlines=lambda *_a: [])  # fmt: skip

    def test_one_to_three_days_before_the_card(self):
        ideas = self._ideas(datetime(2026, 11, 12, 11, tzinfo=UTC))
        self.assertEqual([i.topic for i in ideas], ["Gane vs. Hokit: who wins at UFC 334?"])
        self.assertEqual(ideas[0].source, "debate")
        self.assertEqual(self._ideas(datetime(2026, 11, 10, 11, tzinfo=UTC)), [])  # 4.6 days out

    def test_it_is_written_as_both_sides_and_ends_on_the_question(self):
        from core.angle_intent import ANGLE_COMPARISON

        self.assertEqual(core.batch_generation.draft_intent(own_idea=False, preview="",
                                                            source="debate"), ANGLE_COMPARISON)  # fmt: skip
        pick = {"offered": [{"topic": "Gane vs. Hokit: who wins at UFC 334?", "source": "debate"}],
                "picked": 1}  # fmt: skip
        brief = core.batch_generation.follow_brief(pick, channel_id="tapin")
        self.assertIn("question", brief)

    def test_comments_per_thousand_by_format(self):
        when = datetime(2026, 10, 28, 18, tzinfo=UTC)
        series = [[(when + timedelta(days=d)).date().isoformat(), 100] for d in range(7)]
        row = SimpleNamespace(content_run_id=1, published_at=when, privacy_status="public",
                              metrics_json=json.dumps({"daily_views": series, "comments": 7,
                                                       "lifetime_views": 700}))  # fmt: skip
        feats = {"best_bet": {"offered": [{"topic": "a", "source": "debate"}], "picked": 1}}
        lines = core.success.formats.format_lines("tapin", today=TODAY, rows=[row],
                                                  features=lambda _r: feats)  # fmt: skip
        self.assertIn("debate", lines[0])
        self.assertIn("10.0 comments per 1,000", lines[0])


if __name__ == "__main__":
    unittest.main()
